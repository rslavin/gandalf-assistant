from pydub import AudioSegment
from pydub.playback import play
import numpy as np
import librosa
import time


def play_gandalf(mp3, light=None):
    print("Modulating voice...")
    start_time = time.time()
    # Read MP3 file using pydub
    audio = AudioSegment.from_mp3(mp3)
    samples = np.array(audio.get_array_of_samples())
    rate = audio.frame_rate

    # Convert to float32 for librosa, and reshape to be 2D array
    samples = samples.astype(np.float32).reshape(-1, 1)

    # Normalize the audio signal
    samples /= 32767

    # More dramatic pitch shift
    y_shifted = librosa.effects.pitch_shift(samples.T, sr=rate, n_steps=-8)

    # Timber modifications (adding brightness)
    y_bright = librosa.effects.preemphasis(y_shifted, coef=0.57)

    # Time stretch
    y_stretched = librosa.effects.time_stretch(y_bright, rate=1.1)

    # Convert back to int16
    y_stretched *= 32767
    y_stretched = y_stretched.astype(np.int16)

    # Convert back to a pydub AudioSegment object
    modified_audio = AudioSegment(
        y_stretched.tobytes(),
        frame_rate=rate,
        sample_width=2,  # 16 bits = 2 bytes
        channels=1
    )

    # stop light
    if light:
        light.end_pulse()
    print(f"Modulation compete. ({time.time() - start_time} seconds)")
    # Play modified audio
    print("Playing audio...")
    play(modified_audio)
