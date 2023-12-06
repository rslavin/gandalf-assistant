from abc import ABC, abstractmethod


class LlmClient(ABC):

    def __init__(self, persona):
        self.persona = persona

    @abstractmethod
    def response_generator(self, text):
        raise NotImplementedError(f"TTS Client {type(self)} has not implemented audio_chunk_generator()")
