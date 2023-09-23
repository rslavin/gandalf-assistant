import os
import struct
import pyaudio
import pvporcupine
from audio_utils import convert_frame_length, downsample_audio
from .state_interface import State

MIC_RATE = 44100  # frequency of microphone
VOICE_DETECTION_RATE = 16000  # voice detection rate to be downsampled to
WAKE_SENSITIVITY = [0.6]


class Asleep(State):

    def __init__(self, wakewords):
        self.wakewords = wakewords

    def run(self):
        print("Entering Sleep state.")
        dir_path = os.path.dirname(os.path.realpath(__file__))
        # TODO include sensitivities for wakewords
        file_paths = list(map(lambda file: os.path.join(dir_path, "..", file), self.wakewords))
        porcupine = pvporcupine.create(
            access_key=os.getenv('PICOVOICE_API_KEY'),
            keyword_paths=file_paths,
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
            audio_resampled = convert_frame_length(audio, porcupine.frame_length)

            # feed resampled audio into porcupine
            # TODO add keywords. Return value is the one detected
            # TODO dynamically filter them out here based on persona
            if porcupine.process(audio_resampled) >= 0:
                print("Wake word detected!")
                pa.close(audio_stream)
                return True
