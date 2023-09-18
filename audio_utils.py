import wave
import numpy as np
from scipy.signal import resample
import os
import openai
import sounddevice as sd
from pydub import AudioSegment
import math
from timeout_function_decorator.timeout_decorator import timeout


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


def downsample_audio(audio_data, from_rate, to_rate):
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


@timeout(3)
def transcribe_audio(file_path):
    with open(file_path, "rb") as audio_file:
        # TODO TRANSCRIPTION interface
        # TODO timeout, try https://pypi.org/project/retry/
        question_text = openai.Audio.transcribe(
            file=audio_file,
            model="whisper-1",
            response_format="text",
            language="en"
        )
    os.remove(file_path)
    return question_text


def stream_audio(audio_chunk, volume=0.5, samplerate=16000):
    # TODO first chunk seems to have a break in it
    # Make sure the chunk length is a multiple of 2 (for np.int16)
    if len(audio_chunk) % 2 != 0:
        audio_chunk = audio_chunk[:-1]

    # Convert byte data to numpy array
    audio_array = np.frombuffer(audio_chunk, dtype=np.int16)

    # Change volume by scaling amplitude
    audio_array = np.int16(audio_array * volume)

    # Play audio chunk
    sd.play(audio_array, samplerate=samplerate)
    sd.wait()
