import os
import queue
import threading
import time
import traceback
import wave

import numpy as np
import pvcobra

import audio_utils as audio
from clients.riva_tts import RivaTTS
from clients.polly_tts import PollyTTS
from gpt_client import GptClient, InvalidInputError
from preprocessing import Action, preprocess
from .state_interface import State
from web.web_service import WebService

VOICE_DETECTION_RATE = 16000  # voice detection rate to be downsampled to
VOICE_DETECTION_THRESHOLD = 0.5  # voice activity sensitivity
MAX_DURATION = 25  # how long to listen for regardless of voice detection
ENDING_PAUSE_TIME = 1  # seconds of pause before listening stops
QUEUE_TIMEOUT = 5  # how long for pipeline to wait for an empty queue
INITIAL_PAUSE_TIME = 4  # time to wait for first words
TRANSCRIPTION_FILE = "tmp_transcription.wav"
MAX_LLM_RETRIES = 2  # max llm timeouts
MAX_TTS_RETRIES = 2  # max tts timeouts
MAX_STT_RETRIES = 2  # max stt timeouts


def initialize_audio_file(mic_rate):
    wf = wave.open(TRANSCRIPTION_FILE, 'wb')
    wf.setnchannels(audio.CHANNELS)
    wf.setsampwidth(2)  # assuming 16-bit samples (2 bytes)
    wf.setframerate(mic_rate)
    return wf


def record_query(audio_stream, audio_file, voice_detected, mic_rate, mic_amplification_factor, vad):
    audio_stream.start_stream()
    frames = []
    buffer = np.array([], dtype=np.int16)
    silence_since = time.time()
    frame_length = vad.frame_length
    start_time = time.time()
    pause_time = INITIAL_PAUSE_TIME
    while time.time() - start_time <= MAX_DURATION:
        audio_data = audio_stream.read(audio.FRAMES_PER_BUFFER, exception_on_overflow=False)
        audio_data = audio.resample_audio(audio_data, mic_rate, VOICE_DETECTION_RATE)

        if audio_data is not None:
            buffer = np.concatenate((buffer, audio_data))
            if silence_since is not None and time.time() - silence_since >= pause_time:
                break

            # take chunks out of size frame_length for voice detection
            while len(buffer) >= frame_length:
                frame = buffer[:frame_length]
                buffer = buffer[frame_length:]
                frame = np.int16(frame * mic_amplification_factor)

                try:
                    if vad.process(frame) > VOICE_DETECTION_THRESHOLD:
                        silence_since = time.time()
                        voice_detected = True
                        pause_time = ENDING_PAUSE_TIME  # reset pause time after first words
                        print("V", end="", flush=True)
                    else:
                        print("-", end="", flush=True)
                except Exception as e:
                    print(f"Error detecting voice: {e}")
                    traceback.print_exc()
                    exit()

        frames.append(audio_data)
    print("")  # newline
    # write audio to the file
    audio_file.writeframes(b''.join(frames))
    return voice_detected


def speech_to_text(file):
    print("Transcribing audio...")
    start_time = time.time()
    retries = 0
    question_text = ""
    while retries < MAX_STT_RETRIES:
        try:
            question_text = audio.transcribe_audio(file)
            break
        except TimeoutError:
            print(f"STT timeout. Retrying {MAX_STT_RETRIES - retries - 1} more times...")
            retries += 1
        except Exception as e:
            print(f"Unknown error when attempting STT: {e}")
            return False
    if not question_text:
        print("Unable to connect to STT service.")
        return False
    question_text = question_text.strip('\n')
    transcribe_time = time.time() - start_time
    print(f"Transcription complete ({transcribe_time:.2f} seconds)")
    print(f"I heard '{question_text}'")
    return question_text


class Listening(State):

    def __init__(self, light, bt_light, persona, sound_config, web_service: WebService):
        self.llm_client = GptClient(persona)
        web_service.set_llm(self.llm_client)
        self.web_service = web_service
        self.persona = persona
        self.sound_config = sound_config
        self.light = light
        self.bt_light = bt_light
        self.vad = pvcobra.create(access_key=os.getenv('PICOVOICE_API_KEY'))

        # TODO load appropriate clients depending on config
        # TODO also load appropriate modules based on config

        # self.tts_client = RivaTTS(self.persona, sample_rate=self.sound_config['tts']['rate'])
        self.tts_client = PollyTTS(self.persona)

    def run(self):
        while True:
            voice_detected = False
            self.light.turn_on()
            self.bt_light.turn_on()
            print("Entering Listening state.")

            try:
                # record query
                audio_stream = audio.get_audio_stream(self.sound_config['microphone']['rate'])
                audio_file = initialize_audio_file(self.sound_config['microphone']['rate'])
                voice_detected = record_query(audio_stream, audio_file, voice_detected,
                                              self.sound_config['microphone']['rate'],
                                              self.sound_config['microphone']['amplification'],
                                              self.vad)
                audio_file.close()

                if not voice_detected:
                    print("No speech detected. Exiting state...")
                    self.light.turn_off()
                    self.bt_light.turn_off()
                    break

                # begin processing
                proc_start_time = time.time()
                self.light.begin_pulse()
                self.bt_light.begin_pulse()

                # transcribe
                # TODO add this to streaming pipeline
                question_text = speech_to_text(TRANSCRIPTION_FILE)
                if not question_text:
                    print("Unable to convert speech to text...")
                    break

                # process answer
                action, response = self.preprocess_text(question_text)

                if action == Action.DROP:
                    break

                # begin pipeline to play response
                # self.light.turn_off()
                # self.bt_light.turn_off()
                if response is not None:
                    self.web_service.send_new_user_msg(question_text)
                else:
                    self.web_service.send_new_user_msg(question_text)

                timeout_flag, continue_conversation = self.run_response_pipeline(response, question_text,
                                                                                 proc_start_time)

                if timeout_flag or not continue_conversation:
                    return False

                time.sleep(0.5)

            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()
                return False

            finally:
                try:
                    os.remove(TRANSCRIPTION_FILE)
                except OSError:
                    pass
                self.light.turn_off()
                self.bt_light.turn_off()
        time.sleep(0.5)
        self.light.blink(1)
        self.bt_light.blink(1)

        return True

    def run_response_pipeline(self, response, question_text, proc_start_time):
        text_queue = queue.Queue(maxsize=50)
        voice_queue = queue.Queue(maxsize=50)
        # using a dictionary as a mutable container to share between threads
        shared_vars = {
            'timeout_flag': False,
            'text_received_time': 0.0,
            'audio_received_time': 0.0,
            "continue_conversation": True,
            "stop_playback": False
        }
        start_time = time.time()

        # thread functions
        def enqueue_text():
            if response is not None:
                text_queue.put(response)
                text_queue.put(None)
                self.web_service.send_new_assistant_msg(response)
            else:  # ask LLM
                retries = 0
                while retries < MAX_LLM_RETRIES:
                    try:
                        response_generator = self.llm_client.get_response_generator(question_text)
                        first_chunk = True
                        for response_chunk in response_generator:
                            if shared_vars['stop_playback']:
                                # stop word detected
                                break
                            text_queue.put(response_chunk)
                            if response_chunk is None:
                                break

                            if first_chunk:
                                first_chunk = False
                                self.web_service.send_new_assistant_msg(response_chunk)
                            else:
                                self.web_service.append_assistant_msg(response_chunk)
                        break  # generator has been fully consumed, so exit the loop
                    except InvalidInputError:
                        self.web_service.send_new_assistant_msg("Invalid query.")
                        shared_vars['continue_conversation'] = False
                        break
                    except TimeoutError:
                        print(f"LLM timeout. Retrying {MAX_LLM_RETRIES - retries - 1} more times...")
                        retries += 1
                    except Exception as e:
                        print(f"Unknown error when attempting LLM request: {e}")
                        traceback.print_exc()
                        retries += 1
                    finally:
                        text_queue.put(None)
                if retries > MAX_LLM_RETRIES:
                    shared_vars['timeout_flag'] = True

        def enqueue_audio():
            if not shared_vars['timeout_flag']:
                retries = 0
                first_chunk = True
                while retries < MAX_TTS_RETRIES:
                    try:
                        if shared_vars['stop_playback']:
                            break
                        response_chunk = text_queue.get(timeout=QUEUE_TIMEOUT)
                        if response_chunk is not None:
                            if first_chunk:
                                shared_vars['text_received_time'] = time.time()
                                print(
                                    f"First text chunk received ({shared_vars['text_received_time'] - start_time:.2f} seconds)")
                                first_chunk = False
                        else:
                            break
                        for audio_chunk in self.tts_client.audio_chunk_generator(response_chunk):
                            if shared_vars['stop_playback']:
                                # stop word detected
                                while not text_queue.empty():
                                    text_queue.get()
                                break
                            voice_queue.put(audio_chunk)
                    except TimeoutError:
                        print(f"TTS timeout. Retrying {MAX_LLM_RETRIES - retries - 1} more times...")
                        retries += 1
                    except queue.Empty:
                        # check if there was a timeout and, if so, terminate
                        if shared_vars['timeout_flag']:
                            break
                    except Exception as e:
                        print(f"Unknown error when attempting TTS request: {e}")
                        retries += 1

                voice_queue.put(None)
                if retries > MAX_TTS_RETRIES:
                    shared_vars['timeout_flag'] = True
            else:
                print("Skipping audio enqueue due to LLM timeout.")

        def stream_audio_chunks():
            first_chunk = True
            if not shared_vars['timeout_flag']:
                while True:
                    if shared_vars['stop_playback']:
                        # stop word detected
                        while not voice_queue.empty():
                            voice_queue.get()
                        break
                    try:
                        audio_chunk = voice_queue.get(timeout=QUEUE_TIMEOUT)
                        if audio_chunk is None:
                            break
                        else:
                            if first_chunk:
                                self.light.turn_off()
                                self.bt_light.turn_off()
                                shared_vars['audio_received_time'] = time.time()
                                print(
                                    f"First audio chunk received ({shared_vars['audio_received_time'] - shared_vars['text_received_time']:.2f} seconds)")
                                print(
                                    f"Total time since query: {shared_vars['audio_received_time'] - proc_start_time:.2f} seconds")
                                first_chunk = False
                            audio.stream_audio(audio_chunk, self.sound_config['tts']['rate'],
                                               self.sound_config['speaker']['rate'],
                                               volume=self.sound_config['speaker']['volume'],
                                               device_name=self.sound_config['speaker']['device_name'])
                    except queue.Empty:
                        if shared_vars['timeout_flag']:
                            break
                    finally:
                        self.light.turn_off()
                        self.bt_light.turn_off()
            else:
                print("Skipping audio stream due to timeout.")
            shared_vars['stop_playback'] = True

        def monitor_stop_word():
            # TODO get wakeword sensitivities from persona
            shared_vars['stop_playback'] = audio.wait_for_wake_word(self.persona.stop_words,
                                                                    self.sound_config['microphone']['rate'],
                                                                    shared_vars)

        # create threads
        text_thread = threading.Thread(target=enqueue_text)
        audio_thread = threading.Thread(target=enqueue_audio)
        stream_thread = threading.Thread(target=stream_audio_chunks)
        stop_word_thread = threading.Thread(target=monitor_stop_word)

        # set threads to terminate with main program
        audio_thread.daemon = True
        text_thread.daemon = True
        stream_thread.daemon = True
        stop_word_thread.daemon = True

        # start threads
        text_thread.start()
        audio_thread.start()
        stream_thread.start()
        stop_word_thread.start()

        # wait for threads to finish
        text_thread.join()
        audio_thread.join()
        stream_thread.join()
        stop_word_thread.join()

        return shared_vars['timeout_flag'], shared_vars['continue_conversation']

    def preprocess_text(self, question_text):
        print("Preprocessing query...")
        start_time = time.time()
        response = None
        action, question_text = preprocess(question_text)
        preprocess_time = time.time() - start_time
        print(f"Preprocessing complete ({preprocess_time:.2f} seconds)")
        if action == Action.DROP:
            print("Filtered out locally.")
        elif action == Action.REPLACE:
            response = question_text
            print("Answering locally...")
        elif action == Action.VOLUME_ADJUST:
            response = "Done."
            print(f"Setting volume to {float(question_text) * 100}%.")
            self.sound_config['speaker']['volume'] = question_text
        else:
            print(f'Asking LLM "{question_text}"...')

        return action, response
