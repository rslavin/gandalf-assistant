import os
import struct
import pyaudio
import pvporcupine
import numpy as np
from scipy.signal import resample

from .state_interface import State


def convert_rate(audio, frame_length):
    # Convert to numpy array for resampling
    audio_np = np.array(audio, dtype=np.float32)
    # Resample down to 16000 Hz
    audio_resampled = resample(audio_np, frame_length)
    # Convert resampled audio back to int16
    audio_resampled = np.array(audio_resampled, dtype=np.int16)
    return audio_resampled


class Asleep(State):

    def run(self):
        print("Entering Sleep state.")
        dir_path = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(dir_path, "..", "assets/Hey-Gandalf_en_raspberry-pi_v2_2_0.ppn")
        porcupine = pvporcupine.create(
            access_key=os.getenv('PORCUPINE_API_KEY'),
            keyword_paths=[file_path]
        )

        # Calculate the initial frame length based on Porcupine's requirements
        initial_frame_length = int(porcupine.frame_length * (44100 / 16000))

        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=44100,  # porcupine.sample_rate (16000) is not supported by the mic I'm using
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=initial_frame_length,  # porcupine.frame_length,
            # input_device_index=self.i2s_index
        )

        while True:
            audio = audio_stream.read(initial_frame_length, exception_on_overflow=False)
            audio = struct.unpack_from("h" * initial_frame_length, audio)

            # resample to 44100 because of mic I'm using
            audio_resampled = convert_rate(audio, porcupine.frame_length)

            # Feed resampled audio into porcupine
            if porcupine.process(audio_resampled) >= 0:
                print("Wake word detected!")
                pa.close(audio_stream)
                return True
