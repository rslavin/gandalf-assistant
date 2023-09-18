import os
import struct
import pyaudio
import pvporcupine
import numpy as np
from scipy.signal import resample
from .state_interface import State

MIC_RATE = 44100  # frequency of microphone
VOICE_DETECTION_RATE = 16000  # voice detection rate to be downsampled to
WAKE_SENSITIVITY = [0.6]


def convert_rate(audio, frame_length):
    audio_np = np.array(audio, dtype=np.float32)
    audio_resampled = resample(audio_np, frame_length)
    return np.array(audio_resampled, dtype=np.int16)


class Asleep(State):

    def run(self):
        print("Entering Sleep state.")
        dir_path = os.path.dirname(os.path.realpath(__file__))
        # TODO loop through wakeword files in json file. associate them with sensitivities
        file_path = os.path.join(dir_path, "..", "assets/wakeword.ppn")
        porcupine = pvporcupine.create(
            access_key=os.getenv('PICOVOICE_API_KEY'),
            keyword_paths=[file_path],
            sensitivities=WAKE_SENSITIVITY
        )

        # Calculate the initial frame length based on Porcupine's requirements
        initial_frame_length = int(porcupine.frame_length * (MIC_RATE / VOICE_DETECTION_RATE))

        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=MIC_RATE,  # porcupine.sample_rate # (16000) is not supported by the mic I'm using
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=initial_frame_length,  # porcupine.frame_length,
        )

        while True:
            audio = audio_stream.read(initial_frame_length, exception_on_overflow=False)
            audio = struct.unpack_from("h" * initial_frame_length, audio)

            # resample to 44100 because of mic I'm using
            # TODO this is duplicated in audio_utils.downsample_audio
            audio_resampled = convert_rate(audio, porcupine.frame_length)

            # feed resampled audio into porcupine
            # TODO add keywords. Return value is the one detected
            # TODO dynamically filter them out here based on persona
            if porcupine.process(audio_resampled) >= 0:
                print("Wake word detected!")
                pa.close(audio_stream)
                return True
