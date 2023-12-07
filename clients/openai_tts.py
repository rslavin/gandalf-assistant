import os
import requests
import subprocess

from openai import OpenAI
from timeout_function_decorator.timeout_decorator import timeout
from .tts_interface import TTSClient

MODEL = 'tts-1'
VOICE = 'shimmer'


def decode_opus_to_pcm(opus_data):
    command = [
        "/usr/bin/ffmpeg",
        "-i", "-",  # Read from stdin
        "-f", "s16le",
        "-ar", "24000", # for some reason, this results in 48000 for the output file
        "-ac", "2",
        "-"  # Output to stdout
    ]

    # run FFmpeg, send opus_data to stdin and get PCM data from stdout
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pcm_data, stderr = process.communicate(input=opus_data)

    # check if FFmpeg command was successful
    if process.returncode != 0:
        print("FFmpeg failed:", stderr.decode())
        return None

    return pcm_data


class OpenAITTS(TTSClient):

    def __init__(self, persona):
        super().__init__(persona)
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @timeout(8)
    def get_audio_generator(self, text, model=MODEL, voice=VOICE):
        # response = self.openai_client.audio.speech.create(
        #     model='tts-1',
        #     voice='alloy',
        #     response_format="opus",
        #     input=text
        # )
        #
        # for audio_chunk in response.iter_bytes(chunk_size=4096):
        #     yield resample_audio(audio_chunk, 24000, 16000)
        #     # yield resample_audio(audio_chunk, 46800, 16000)

        url = "https://api.openai.com/v1/audio/speech"

        headers = {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        }

        data = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": "opus",
        }

        # TODO figure out why this isn't actually streaming. I think the api is messed up.
        with requests.post(url, headers=headers, json=data, stream=True) as response:
            for chunk in response.iter_content(chunk_size=4096):
                # audio_segment = AudioSegment.from_file(BytesIO(chunk), format="opus")
                # pcm_data = audio_segment.raw_data
                if chunk:
                    yield decode_opus_to_pcm(chunk)
            # yield resample_audio(audio_chunk, 46800, 16000)
