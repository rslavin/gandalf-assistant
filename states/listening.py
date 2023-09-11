import wave
import pyaudio
import subprocess
import openai
import os
from gpt_client import GptClient
from preprocessing import preprocess
from .state_interface import State
from tts import play_gandalf
import webrtcvad
from scipy.signal import resample
import numpy as np
import traceback
import time

RATE = 44100
VOICE_DETECTION_RATE = 32000  # voice detection rate to be downsampled to
CHANNELS = 1
SILENCE_THRESHOLD = 70
VOICE_ACTIVITY_THRESHOLD = 2  # 0 gives more false positives, 3 gives more false negatives
FRAMES_PER_BUFFER = 1026
MAX_DURATION = 15
PAUSE_TIME = 2
TRANSCRIPTION_FILE = "tmp.wav"


def downsample_audio(audio_data, from_rate, to_rate):
    if not audio_data:
        return None

    # Convert to numpy array if audio_data is in bytes
    if isinstance(audio_data, bytes):
        audio_data = np.frombuffer(audio_data, dtype=np.int16)

    audio_data = np.array(audio_data)
    ratio = to_rate / from_rate
    audio_len = len(audio_data)
    new_len = int(audio_len * ratio)
    resampled_audio = resample(audio_data, new_len)
    return np.int16(resampled_audio)


def transcribe_audio(file_path):
    with open(file_path, "rb") as audio_file:
        # TODO TRANSCRIPTION interface
        question_text = openai.Audio.transcribe(
            file=audio_file,
            model="whisper-1",
            response_format="text",
            language="en"
        )
    os.remove(file_path)
    return question_text


def frequency_filter(frame, cutoff_low=15, cutoff_high=250, sample_rate=16000):
    """
    Uses fast fourier transform to filter out frequencies outside of human speech.
    :param frame: Frame to filter
    :param cutoff_low: Lower frequency bound
    :param cutoff_high: Upper frequency bound
    :param sample_rate: Sample rate
    :return: Filtered frame
    """
    amplification_factor = 4.5
    # Perform the FFT
    sp = np.fft.fft(frame)
    freq = np.fft.fftfreq(len(sp), 1 / sample_rate)

    # Zero out frequencies outside the desired cutoff range
    sp[(freq < cutoff_low)] = 0
    sp[(freq > cutoff_high)] = 0

    # Perform the Inverse FFT to get back to time domain
    filtered_frame = np.fft.ifft(sp).real
    filtered_frame *= amplification_factor  # amplify since the filtered audio will no longer be normalized

    return filtered_frame


class Listening(State):

    def __init__(self, light):
        self.gpt = GptClient()
        self.light = light
        self.vad = webrtcvad.Vad(VOICE_ACTIVITY_THRESHOLD)

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
                start_time = time.time()
                silence_since = time.time()
                frame_length = int(VOICE_DETECTION_RATE * 0.01)
                while time.time() - start_time <= MAX_DURATION:
                    data = audio_stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                    downsampled_data = downsample_audio(data, RATE, VOICE_DETECTION_RATE)

                    if downsampled_data is not None:
                        if silence_since is not None and time.time() - silence_since >= PAUSE_TIME:
                            break

                        for i in range(0, len(downsampled_data), frame_length):
                            frame = downsampled_data[i:i + frame_length]

                            if len(frame) == frame_length:
                                try:
                                    # Filter out unwanted frequencies
                                    filtered_frame = frequency_filter(frame, sample_rate=VOICE_DETECTION_RATE)
                                    filtered_frame = np.int16(filtered_frame.real)[:frame_length]

                                    if self.vad.is_speech(filtered_frame.tobytes(), VOICE_DETECTION_RATE):
                                        silence_since = time.time()
                                        voice_detected = True
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
                    print("No speech detected. Existing state...")
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
                else:  # get the answer from the llm
                    # send transcribed query to gpt
                    print("Asking LLM...")
                    print(question_text)
                    start_time = time.time()
                    # TODO LLM interface
                    response = self.gpt.send_message(question_text)
                    if response == "-1":
                        self.light.turn_off()
                        return False
                    answer_time = time.time() - start_time
                    print(f"GPT request complete ({answer_time:.2f} seconds)")
                print(f"Response: {response}")

                # CONVERT ANSWER TO SPEECH
                self.light.turn_off()
                # TODO TTS interface
                print("Converting gpt text to speech...")
                start_time = time.time()
                response_voice = play_gandalf(response)
                tts_time = time.time() - start_time
                print(f"Text to speech complete ({tts_time:.2f} seconds)")

                total_time = transcribe_time + answer_time + tts_time
                print(f"Total processing time: {total_time:.2f} seconds")

                if response_voice:
                    subprocess.call(["xdg-open", response_voice])
                    time.sleep(0.5)
                else:
                    print(f"Error playing {response_voice}.")

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
