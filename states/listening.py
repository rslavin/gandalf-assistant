import wave
import pyaudio
import audioop
import time
import openai
import os
from gpt_client import GptClient
from gtts import gTTS
from light import Light
from .state_interface import State
from voice_mod import play_gandalf

RATE = 44100
CHANNELS = 1
SILENCE_THRESHOLD = 60
FRAMES_PER_BUFFER = 1026
MAX_DURATION = 10
PAUSE_TIME = 3
LED_PIN = 20


class Listening(State):

    def __init__(self):
        self.gpt = GptClient()
        self.light = Light(LED_PIN)

    def run(self):
        while True:
            voice_detected = False
            self.light.turn_on()
            print("Entering Listening state.")

            # TODO run again to see if the user has a followup question

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

                wf = wave.open("tmp.wav", 'wb')
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
                wf.setframerate(RATE)

                # record
                audio_stream.start_stream()

                frames = []
                start_time = time.time()
                silence_since = None
                while time.time() - start_time <= MAX_DURATION:
                    data = audio_stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                    rms_level = audioop.rms(data, pa.get_sample_size(pyaudio.paInt16))

                    if rms_level < SILENCE_THRESHOLD:
                        if silence_since is None:
                            silence_since = time.time()
                        elif time.time() - silence_since >= PAUSE_TIME:
                            break
                    else:
                        silence_since = None
                        # keep track of whether sound is detected
                        voice_detected = True
                    frames.append(data)
                if not voice_detected:
                    print("No speech detected. Existing state...")
                    self.light.end_pulse()
                    break

                # write audio to the file
                wf.writeframes(b''.join(frames))
                wf.close()
                self.light.begin_pulse()

                # transcribe tmp.wav with whisper
                print("Transcribing audio...")
                start_time = time.time()
                with open("tmp.wav", "rb") as audio_file:
                    question_text = openai.Audio.transcribe(
                        file=audio_file,
                        model="whisper-1",
                        response_format="text",
                        language="en"
                    )
                os.remove("tmp.wav")
                transcribe_time = time.time() - start_time
                print(f"Transcription complete ({transcribe_time} seconds)")

                # send transcribed query to gpt
                start_time = time.time()
                response = self.gpt.send_message(question_text)
                gpt_time = time.time() - start_time
                print(f"GPT request complete ({gpt_time} seconds)")
                if response == "-1":
                    return False

                # convert the gpt text to speech
                print("Converting gpt text to speech...")
                start_time = time.time()
                tts = gTTS(response, lang='en', tld='co.uk')
                tts_time = time.time() - start_time
                print(f"TTS compete ({tts_time}s)")

                print("Speech received. Playing...")
                start_time = time.time()
                tts.save("response.mp3")
                mp3_time = time.time() - start_time
                print(f"mp3 saved ({mp3_time} seconds)")
                play_gandalf("response.mp3", self.light)
                os.remove("response.mp3")

            except Exception as e:
                print(f"An error occurred: {e}")
                return False

            finally:
                if audio_stream is not None:
                    audio_stream.stop_stream()
                    audio_stream.close()
                pa.terminate()

        return True
