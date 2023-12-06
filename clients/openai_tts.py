import os

from openai import OpenAI
from timeout_function_decorator.timeout_decorator import timeout
from .tts_interface import TTSClient
from audio_utils import resample_audio


class OpenAITTS(TTSClient):

    def __init__(self, persona):
        super().__init__(persona)
        self.openai_client = OpenAI(api_key=os.getenv("OPEN_API_KEY"))

    @timeout(8)
    def get_audio_generator(self, text):

        response = self.openai_client.audio.speech.create(
            model='tts-1',
            voice='alloy',
            response_format="opus",
            input=text
        )

        # TODO figure out what frequency the response is in and adjust for it
        for audio_chunk in response.iter_bytes(chunk_size=4096):
            yield audio_chunk
            # yield resample_audio(audio_chunk, 46800, 16000)
