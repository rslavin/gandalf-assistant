from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import os
import sys
from tempfile import gettempdir
from timeout_function_decorator.timeout_decorator import timeout


@timeout(8)
def play_gandalf(voice_id, voice_engine, text):
    session = Session(aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), region_name='us-east-1')
    polly = session.client("polly")

    try:
        # Request speech synthesis
        response = polly.synthesize_speech(Text=text, OutputFormat="mp3",
                                           VoiceId=voice_id, Engine=voice_engine)
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
def audio_chunk_generator(voice_id, voice_engine, text):
    session = Session(aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), region_name='us-east-1')
    polly = session.client("polly")

    try:
        # Request speech synthesis
        response = polly.synthesize_speech(Text=text, OutputFormat="pcm",
                                           VoiceId=voice_id, Engine=voice_engine)
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



