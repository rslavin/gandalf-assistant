import os
from contextlib import closing

from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from timeout_function_decorator.timeout_decorator import timeout
from .tts_interface import TTSClient


class PollyTTS(TTSClient):

    def __init__(self, persona):
        super().__init__(persona)

    @timeout(8)
    def get_audio_generator(self, text):

        session = Session(aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
                          aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), region_name='us-east-1')
        polly = session.client("polly")

        try:
            # Request speech synthesis
            text = self.apply_ssml(text)
            response = polly.synthesize_speech(Text=text, TextType="ssml", OutputFormat="pcm",
                                               SampleRate=str(self.persona.sample_rate),
                                               VoiceId=self.persona.voice_id, Engine=self.persona.voice_engine)
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
