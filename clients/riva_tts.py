import logging
import os
import time
import numpy as np

import riva.client
import riva.client.audio_io

from timeout_function_decorator.timeout_decorator import timeout
from .tts_interface import TTSClient

SAMPLE_RATE = 16000


class RivaTTS(TTSClient):

    def __init__(self, persona, riva_server=None, language_code='en-US', **kwargs):
        """
        The available voices are from:
          https://docs.nvidia.com/deeplearning/riva/user-guide/docs/tts/tts-overview.html#voices

        rate, pitch, and volume are dynamic SSML tags from:
          https://docs.nvidia.com/deeplearning/riva/user-guide/docs/tutorials/tts-basics-customize-ssml.html#customizing-rate-pitch-and-volume-with-the-prosody-tag
        """
        super().__init__(persona)
        self.server = riva_server if riva_server else os.getenv('RIVA_URL')
        self.auth = riva.client.Auth(uri=self.server)
        self.tts_service = riva.client.SpeechSynthesisService(self.auth)

        self.persona = persona
        self.language_code = language_code
        self.sample_rate = SAMPLE_RATE

        self.needs_text_by = 0
        self.text_buffer = ''

        self.interrupted = False

    @timeout(8)
    def get_audio_generator(self, text):
        # text = self.buffer_text(text)
        text = self.filter_text(text)
        text = self.apply_ssml(text)

        if not text or self.interrupted:
            return

        # print(f"generating TTS for '{text}'")

        responses = self.tts_service.synthesize_online(
            text, self.persona.voice_id, self.language_code, sample_rate_hz=self.sample_rate
        )

        for response in responses:
            if self.interrupted:
                logging.debug(f"TTS interrupted, terminating request early:  {text}")
                break

            samples = np.frombuffer(response.audio, dtype=np.int16)

            current_time = time.perf_counter()
            if current_time > self.needs_text_by:
                self.needs_text_by = current_time
            self.needs_text_by += len(samples) / self.sample_rate

            yield samples

    def buffer_text(self, text):
        """
        Wait for punctuation to occur because that sounds better
        """
        self.text_buffer += text

        # always submit on EOS
        if '</s>' in self.text_buffer:
            text = self.text_buffer
            self.text_buffer = ''
            return text

        # look for punctuation
        punc_pos = -1

        for punc in ('. ', ', ', '! ', '? ', ': ', '\n'):  # the space after has fewer non-sentence uses
            punc_pos = max(self.text_buffer.rfind(punc), punc_pos)

        if punc_pos < 0:
            # if len(self.text_buffer.split(' ')) > 6:
            #    punc_pos = len(self.text_buffer) - 1
            # else:
            return None

        # see if input is needed to prevent a gap-out
        timeout = self.needs_text_by - time.perf_counter() - 0.05  # TODO make this RTFX factor adjustable

        if timeout > 0:
            return None  # we can keep accumulating text

        # return the latest phrase/sentence
        text = self.text_buffer[:punc_pos + 1]

        if len(self.text_buffer) > punc_pos + 1:  # save characters after for next request
            self.text_buffer = self.text_buffer[punc_pos + 1:]
        else:
            self.text_buffer = ''

        return text
