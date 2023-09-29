from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import os
import sys
from tempfile import gettempdir
from timeout_function_decorator.timeout_decorator import timeout


@timeout(8)
def get_audio(persona, text):
    voice_id = persona.voice_id
    voice_engine = persona.voice_engine

    session = Session(aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), region_name='us-east-1')
    polly = session.client("polly")

    try:
        response = polly.synthesize_speech(Text=text, OutputFormat="mp3",
                                           VoiceId=voice_id, Engine=voice_engine)
    except (BotoCoreError, ClientError) as error:
        print(error)
        return None

    # Access the audio stream from the response
    if "AudioStream" in response:
        # closing is important here because the service will throttle based on parallel connections.
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
        print("Could not stream audio")
        return None
    return output


@timeout(8)
def audio_chunk_generator(persona, text):
    voice_id = persona.voice_id
    voice_engine = persona.voice_engine
    voice_rate = persona.voice_rate
    sample_rate = str(persona.sample_rate)

    session = Session(aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), region_name='us-east-1')
    polly = session.client("polly")

    try:
        # Request speech synthesis
        text = f'<speak><prosody rate="{voice_rate}%">{text}</prosody></speak>'
        response = polly.synthesize_speech(Text=text, TextType="ssml", OutputFormat="pcm", SampleRate=sample_rate,
                                           VoiceId=voice_id, Engine=voice_engine)
    except (BotoCoreError, ClientError) as error:
        print(error)
        return None

    if "AudioStream" in response:
        chunk_size = 131072
        # closing is important here because the service will throttle based on parallel connections.
        with closing(response["AudioStream"]) as stream:
            while True:
                audio_chunk = stream.read(chunk_size)
                if not audio_chunk:
                    break
                yield audio_chunk
    else:
        print("Could not stream audio")
        yield None
