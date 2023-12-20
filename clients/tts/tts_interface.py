from abc import ABC, abstractmethod

SAMPLE_RATE = 1600

class TTSClient(ABC):

    def __init__(self, persona):
        self.persona = persona
        self.sample_rate = SAMPLE_RATE

    @abstractmethod
    def get_audio_generator(self, text):
        raise NotImplementedError(f"TTS Client {type(self)} has not implemented audio_chunk_generator()")

    def filter_text(self, text):
        if not text:
            return None

        text = text.replace('\n', ' ')

        if len(text.strip()) == 0:
            return None

        return text

    def apply_ssml(self, text):
        """
        Apply SSML tags to text
        """
        if not text:
            return None

        # TODO consider adding pitch and volume
        if self.persona.voice_rate != 'default':
            text = f"<speak><prosody rate='{self.persona.voice_rate}%'>{text}</prosody></speak>"

        return text
