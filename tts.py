from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import os
import sys
import numpy as np
import sounddevice as sd
from tempfile import gettempdir
from timeout_function_decorator.timeout_decorator import timeout
import time


@timeout(8)
def play_gandalf(text):
    session = Session(aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), region_name='us-east-1')
    polly = session.client("polly")

    try:
        # Request speech synthesis
        response = polly.synthesize_speech(Text=text, OutputFormat="mp3",
                                           VoiceId="Brian", Engine="neural")
    except (BotoCoreError, ClientError) as error:
        # The service returned an error, exit gracefully
        print(error)
        return None

    # Access the audio stream from the response
    if "AudioStream" in response:
        # Note: Closing the stream is important because the service throttles on the
        # number of parallel connections. Here we are using contextlib.closing to
        # ensure the close method of the stream object will be called automatically
        # at the end of the with statement's scope.
        with closing(response["AudioStream"]) as stream:
            output = os.path.join(gettempdir(), "speech.mp3")

            try:
                # Open a file for writing the output as a binary stream
                with open(output, "wb") as file:
                    file.write(stream.read())
            except IOError as error:
                # Could not write to file, exit gracefully
                print(error)
                sys.exit(-1)

    else:
        # The response didn't contain audio data, exit gracefully
        print("Could not stream audio")
        return None
    return output


@timeout(8)
def audio_chunk_generator(text):
    session = Session(aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), region_name='us-east-1')
    polly = session.client("polly")

    try:
        # Request speech synthesis
        response = polly.synthesize_speech(Text=text, OutputFormat="pcm",
                                           VoiceId="Brian", Engine="neural")
    except (BotoCoreError, ClientError) as error:
        print(error)
        return None

    # Access the audio stream from the response
    if "AudioStream" in response:
        chunk_size = 1048576
        with closing(response["AudioStream"]) as stream:
            while True:
                audio_chunk = stream.read(chunk_size)
                if not audio_chunk:
                    break
                yield audio_chunk
    else:
        print("Could not stream audio")
        yield None


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
