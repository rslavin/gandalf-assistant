import wave
import pyaudio
import os
from gpt_client import GptClient
from preprocessing import preprocess
from .state_interface import State
import tts
import numpy as np
import traceback
import time
import queue
import threading
import pvcobra
from audio_utils import downsample_audio, transcribe_audio, stream_audio

RATE = 44100  # frequency of microphone
VOICE_DETECTION_RATE = 16000  # voice detection rate to be downsampled to
AMPLIFICATION_FACTOR = 10
VOICE_DETECTION_THRESHOLD = 0.75
CHANNELS = 1
FRAMES_PER_BUFFER = 1026
MAX_DURATION = 15  # how long to listen for regardless of voice detection
ENDING_PAUSE_TIME = 1  # seconds of pause before listening stops
QUEUE_TIMEOUT = 5  # how long for pipeline to wait for an empty queue
INITIAL_PAUSE_TIME = 4  # time to wait for first words
TRANSCRIPTION_FILE = "transcription.wav"
MAX_LLM_RETRIES = 2  # max llm timeouts
MAX_TTS_RETRIES = 2  # max tts timeouts
MAX_STT_RETRIES = 2  # max stt timeouts (this is done locally, but requires authentication)
DEFAULT_VOLUME = 0.75


class Listening(State):

    def __init__(self, light):
        self.llm = GptClient()
        self.light = light
        self.cobra_vad = pvcobra.create(access_key=os.getenv('PICOVOICE_API_KEY'))
        # TODO move this to json file
        self.volume_multiplier = DEFAULT_VOLUME

    def run(self):
        while True:
            voice_detected = False
            self.light.turn_on()
            print("Entering Listening state.")

            pa = pyaudio.PyAudio()
            audio_stream = None

            try:
                audio_stream = pa.open(
                    rate=RATE,
                    channels=CHANNELS,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=FRAMES_PER_BUFFER,
                )

                wf = wave.open(TRANSCRIPTION_FILE, 'wb')
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
                wf.setframerate(RATE)

                # record
                audio_stream.start_stream()

                frames = []
                buffer = np.array([], dtype=np.int16)
                silence_since = time.time()
                frame_length = self.cobra_vad.frame_length
                start_time = time.time()
                pause_time = INITIAL_PAUSE_TIME
                while time.time() - start_time <= MAX_DURATION:
                    data = audio_stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                    downsampled_data = downsample_audio(data, RATE, VOICE_DETECTION_RATE)

                    if downsampled_data is not None:
                        buffer = np.concatenate((buffer, downsampled_data))
                        if silence_since is not None and time.time() - silence_since >= pause_time:
                            break

                        # take chunks out of size frame_length for voice detection
                        while len(buffer) >= frame_length:
                            frame = buffer[:frame_length]
                            buffer = buffer[frame_length:]
                            frame = np.int16(frame * AMPLIFICATION_FACTOR)

                            try:
                                if self.cobra_vad.process(frame) > VOICE_DETECTION_THRESHOLD:
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
                                continue

                    frames.append(data)
                print("")  # newline
                if not voice_detected:
                    print("No speech detected. Exiting state...")
                    self.light.turn_off()
                    break

                proc_start_time = time.time()

                # write audio to the file
                wf.writeframes(b''.join(frames))
                wf.close()
                self.light.begin_pulse()

                # TRANSCRIBE
                print("Transcribing audio...")
                start_time = time.time()
                retries = 0
                question_text = ""
                while retries < MAX_STT_RETRIES:
                    try:
                        question_text = transcribe_audio(TRANSCRIPTION_FILE)
                        break
                    except TimeoutError:
                        print(f"TTS timeout. Retrying {MAX_STT_RETRIES - retries - 1} more times...")
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

                # PROCESS ANSWER
                print("Preprocessing query...")
                start_time = time.time()
                response = None
                action, question_text = preprocess(question_text)
                preprocess_time = time.time() - start_time
                print(f"Preprocessing complete ({preprocess_time:.2f} seconds)")
                if action == -1:  # drop
                    print("Filtered out locally.")
                    return False
                elif action == 1:  # replace
                    response = question_text
                    print("Answering locally...")
                elif action == 2:  # volume adjust
                    response = "Done."
                    print(f"Setting volume to {float(question_text) * 100}%.")
                    self.volume_multiplier = question_text
                else:
                    print(f'Asking LLM "{question_text}"...')

                # begin pipeline to play response
                self.light.turn_off()
                text_queue = queue.Queue(maxsize=50)
                voice_queue = queue.Queue(maxsize=50)
                # using a dictionary as a mutable container to share between threads
                shared_vars = {
                    'timeout_flag': False,
                    'text_received_time': 0.0,
                    'audio_received_time': 0.0
                }

                start_time = time.time()

                # thread functions
                def enqueue_text():
                    if response is not None:
                        text_queue.put(response)
                        text_queue.put(None)
                    else:  # ask LLM
                        retries = 0
                        while retries < MAX_LLM_RETRIES:
                            try:
                                response_generator = self.llm.get_response_generator(question_text)
                                for response_chunk in response_generator:
                                    text_queue.put(response_chunk)
                                    if response_chunk is None:
                                        break
                                break  # generator has been fully consumed, so exit the loop
                            except TimeoutError:
                                print(f"LLM timeout. Retrying {MAX_LLM_RETRIES - retries - 1} more times...")
                                retries += 1
                            except Exception as e:
                                print(f"Unknown error when attempting LLM request: {e}")
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
                                response_chunk = text_queue.get(timeout=QUEUE_TIMEOUT)
                                if response_chunk is not None:
                                    if first_chunk:
                                        shared_vars['text_received_time'] = time.time()
                                        print(
                                            f"First text chunk received ({shared_vars['text_received_time'] - start_time:.2f} seconds)")
                                        first_chunk = False
                                else:
                                    break
                                for audio_chunk in tts.audio_chunk_generator(response_chunk):
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
                            try:
                                audio_chunk = voice_queue.get(timeout=QUEUE_TIMEOUT)
                                if audio_chunk is None:
                                    break
                                else:
                                    if first_chunk:
                                        shared_vars['audio_received_time'] = time.time()
                                        print(
                                            f"First audio chunk received ({shared_vars['audio_received_time'] - shared_vars['text_received_time']:.2f} seconds)")
                                        print(
                                            f"Total time since query: {shared_vars['audio_received_time'] - proc_start_time:.2f} seconds")
                                        first_chunk = False
                                    stream_audio(audio_chunk, volume=self.volume_multiplier)
                            except queue.Empty:
                                if shared_vars['timeout_flag']:
                                    break
                    else:
                        print("Skipping audio stream due to timeout.")

                # start threads
                text_thread = threading.Thread(target=enqueue_text)
                audio_thread = threading.Thread(target=enqueue_audio)
                stream_thread = threading.Thread(target=stream_audio_chunks)

                # set threads to terminate with main program
                audio_thread.daemon = True
                text_thread.daemon = True
                stream_thread.daemon = True

                text_thread.start()
                audio_thread.start()
                stream_thread.start()

                # wait for threads to finish
                text_thread.join()
                audio_thread.join()
                stream_thread.join()

                if shared_vars['timeout_flag']:
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
                if audio_stream is not None:
                    audio_stream.stop_stream()
                    audio_stream.close()
                    self.light.turn_off()
                pa.terminate()

        return True
