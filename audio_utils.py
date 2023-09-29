import math
import os
import struct
import wave

import numpy as np
import openai
import pvporcupine
import pyaudio
import sounddevice as sd
from pydub import AudioSegment
from scipy.signal import resample
from timeout_function_decorator.timeout_decorator import timeout

CHANNELS = 1
FRAMES_PER_BUFFER = 512


def amplify_wav(file_path, amplification_factor):
    with wave.open(file_path, 'rb') as wf:
        params = wf.getparams()
        audio_data = wf.readframes(params.nframes)
        audio_as_np_int16 = np.frombuffer(audio_data, dtype=np.int16)
        audio_as_np_int16 = np.int16(audio_as_np_int16 * amplification_factor)
        amplified_data = audio_as_np_int16.tobytes()

    with wave.open(file_path, 'wb') as wf:
        wf.setparams(params)
        wf.writeframes(amplified_data)


def adjust_volume(file_path, percentage, file_format="mp3"):
    sound = AudioSegment.from_file(file_path, format=file_format)

    # calculate the gain in dB
    gain_db = 20 * math.log10(1 + percentage / 100)

    amplified_sound = sound.apply_gain(gain_db)
    amplified_sound.export(file_path, format=file_format)


def resample_audio(audio_data, from_rate, to_rate):
    # convert to numpy array if audio_data is in bytes
    if isinstance(audio_data, bytes):
        audio_data = np.frombuffer(audio_data, dtype=np.int16)

    audio_data = np.array(audio_data)
    ratio = to_rate / from_rate
    audio_len = len(audio_data)
    new_len = int(audio_len * ratio)
    resampled_audio = resample(audio_data, new_len)
    return np.int16(resampled_audio)


def convert_frame_length(audio_data, target_frame_length):
    audio_data = np.array(audio_data, dtype=np.float32)
    resampled_audio = resample(audio_data, target_frame_length)
    return np.array(resampled_audio, dtype=np.int16)


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


@timeout(6)
def transcribe_audio(file_path):
    with open(file_path, "rb") as audio_file:
        question_text = openai.Audio.transcribe(
            file=audio_file,
            model="whisper-1",
            response_format="text",
            language="en"
        )
    os.remove(file_path)
    return question_text


def stream_audio(audio_chunk, audio_rate, speaker_rate, volume=0.5, device_name=""):
    # make sure the chunk length is a multiple of 2 (for np.int16)
    if len(audio_chunk) % 2 != 0:
        audio_chunk = audio_chunk[:-1]

    audio_chunk = resample_audio(audio_chunk, from_rate=audio_rate, to_rate=speaker_rate)

    audio_array = np.frombuffer(audio_chunk, dtype=np.int16)

    # change volume by scaling amplitude
    audio_array = np.int16(audio_array * volume)

    # play chunk
    if device_name:
        sd.default.device = device_name
    sd.play(audio_array)
    sd.wait()


def wait_for_wake_word(sensitivities, wakewords, mic_rate, stop_flag: dict = {'stop_playback': False}):
    # TODO filter out the system's voice based on its frequency (180 - 300) or only look at my voice's (80 - 120
    # stop_flag must be mutable since it may be shared between threads
    dir_path = os.path.dirname(os.path.realpath(__file__))
    # TODO include sensitivities for wakewords
    file_paths = list(map(lambda file: os.path.join(dir_path, "..", file), wakewords))
    porcupine = pvporcupine.create(
        access_key=os.getenv('PICOVOICE_API_KEY'),
        keyword_paths=file_paths,
        sensitivities=sensitivities
    )

    # calculate the initial frame length based on Porcupine's requirements
    initial_frame_length = int(porcupine.frame_length * (mic_rate / porcupine.sample_rate))
    audio_stream, pa = get_audio_stream(mic_rate, initial_frame_length)

    while not stop_flag['stop_playback']:
        audio = audio_stream.read(initial_frame_length, exception_on_overflow=False)
        audio = struct.unpack_from("h" * initial_frame_length, audio)

        audio_resampled = convert_frame_length(audio, porcupine.frame_length)

        # feed resampled audio into porcupine
        # TODO add keywords. Return value is the one detected
        # TODO dynamically filter them out here based on persona
        if porcupine.process(audio_resampled) >= 0:
            print("Wake word detected!")
            break
    return True


def get_audio_stream(mic_rate, frames_per_buffer=FRAMES_PER_BUFFER):
    return AudioStreamSingleton.get_audio_stream(mic_rate, frames_per_buffer)


def close_audio_stream():
    return AudioStreamSingleton.close_audio()


class AudioStreamSingleton:
    _audio_stream = None
    _pa_instance = None
    _current_mic_rate = -1
    _current_frames_per_buffer = -1

    @classmethod
    def get_audio_stream(cls, mic_rate, frames_per_buffer):
        update_instance = False
        if cls._audio_stream and (
                mic_rate != cls._current_mic_rate or frames_per_buffer != cls._current_frames_per_buffer):
            update_instance = True

        if cls._audio_stream is None or update_instance:
            if update_instance:
                print("New audio parameters requested. Instantiating new singletons.")
            cls._pa_instance = pyaudio.PyAudio()
            cls._audio_stream = cls._pa_instance.open(
                rate=mic_rate,
                channels=CHANNELS,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=frames_per_buffer,
            )
            cls._current_mic_rate = mic_rate
            cls._current_frames_per_buffer = frames_per_buffer

        return cls._audio_stream, cls._pa_instance

    @classmethod
    def close_audio(cls):
        if cls._audio_stream is not None:
            cls._audio_stream.close()
            cls._audio_stream = None
        if cls._pa_instance is not None:
            cls._pa_instance.terminate()
            cls._pa_instance = None
