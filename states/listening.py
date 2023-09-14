import wave
import pyaudio
import subprocess
import os
from gpt_client import GptClient
from preprocessing import preprocess
from .state_interface import State
from tts import play_gandalf_generator, stream_audio
import numpy as np
import traceback
import time
import pvcobra
from audio_utils import downsample_audio, transcribe_audio, adjust_volume

RATE = 44100  # frequency of microphone
VOICE_DETECTION_RATE = 16000  # voice detection rate to be downsampled to
AMPLIFICATION_FACTOR = 10
VOICE_DETECTION_THRESHOLD = 0.75
CHANNELS = 1
FRAMES_PER_BUFFER = 1026
MAX_DURATION = 15  # how long to listen for regardless of voice detection
ENDING_PAUSE_TIME = 2  # seconds of pause before listening stops
INITIAL_PAUSE_TIME = 4  # time to wait for first words
TRANSCRIPTION_FILE = "tmp.wav"
MAX_LLM_RETRIES = 2  # max llm timeouts
MAX_TTS_RETRIES = 2  # max llm timeouts


class Listening(State):

    def __init__(self, light):
        self.gpt = GptClient()
        self.light = light
        self.cobra_vad = pvcobra.create(access_key=os.getenv('PICOVOICE_API_KEY'))
        # TODO move this to json file
        self.volume_adjust = 0

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

                # write audio to the file
                wf.writeframes(b''.join(frames))
                wf.close()
                self.light.begin_pulse()

                # TRANSCRIBE
                print("Transcribing audio...")
                start_time = time.time()
                question_text = transcribe_audio(TRANSCRIPTION_FILE)
                transcribe_time = time.time() - start_time
                print(f"Transcription complete ({transcribe_time:.2f} seconds)")
                print(f"I heard '{question_text}'")

                # PROCESS ANSWER
                start_time = time.time()
                response = "-1"
                action, question_text = preprocess(question_text)
                if action == -1:  # drop
                    print("Filtered out locally.")
                    self.light.turn_off()
                    return False
                elif action == 1:  # replace
                    print("Answering locally...")
                    response = question_text
                    answer_time = time.time() - start_time
                    print(f"Local request complete ({answer_time:.2f} seconds)")
                elif action == 2:  # volume adjust
                    print(f"Setting volume to {question_text}%.")
                    self.volume_adjust = question_text
                    answer_time = time.time() - start_time
                    print(f"Local request complete ({answer_time:.2f} seconds)")
                    # TODO play a beep
                    response = "Done."
                else:  # get the answer from the llm
                    # send transcribed query to llm
                    print("Asking LLM...")
                    print(question_text)
                    start_time = time.time()
                    # TODO LLM interface
                    retries = 0
                    while retries <= MAX_LLM_RETRIES:
                        try:
                            response = self.gpt.send_message_stream(question_text)
                            break
                        except TimeoutError:
                            print(f"LLM timeout. Retrying {MAX_LLM_RETRIES - retries} more times...")
                            retries += 1
                    if retries >= MAX_LLM_RETRIES or response == "-1":
                        self.light.turn_off()
                        return False

                    answer_time = time.time() - start_time
                    print(f"LLM request complete ({answer_time:.2f} seconds)")
                print(f"Response: {response}")

                # CONVERT ANSWER TO SPEECH
                self.light.turn_off()
                # TODO TTS interface
                # print("Converting LLM text to speech...")
                # start_time = time.time()
                # retries = 0
                # response_voice_generator = None
                # while retries <= MAX_TTS_RETRIES:
                #     try:
                #         response_voice_generator = play_gandalf_generator(response)
                #         stream_audio(response_voice_generator)
                #         break
                #     except TimeoutError:
                #         print(f"LLM timeout. Retrying {MAX_TTS_RETRIES - retries} more times...")
                #         retries += 1
                # if retries >= MAX_TTS_RETRIES or not response_voice_generator:
                #     self.light.turn_off()
                #     print(f"Error playing {response_voice_generator}.")
                #     return False
                #
                # if response_voice_generator == 1:
                #     return True
                #
                # tts_time = time.time() - start_time
                # print(f"Text to speech complete ({tts_time:.2f} seconds)")
                #
                # total_time = transcribe_time + answer_time + tts_time
                # print(f"Total processing time: {total_time:.2f} seconds")

                # if self.volume_adjust:
                #     adjust_volume(response_voice_generator, self.volume_adjust)
                # subprocess.call(["xdg-open", response_voice_generator])
                time.sleep(0.5)

            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()
                return False

            finally:
                if audio_stream is not None:
                    audio_stream.stop_stream()
                    audio_stream.close()
                    self.light.turn_off()
                pa.terminate()

        return True
