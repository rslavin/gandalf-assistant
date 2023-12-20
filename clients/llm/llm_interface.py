from abc import ABC, abstractmethod


class LlmClient(ABC):

    def __init__(self, persona):
        self.persona = persona
        self.bump_system_message = True  # whether to move system message near the end of the conversation

    @abstractmethod
    def response_generator(self, text):
        raise NotImplementedError(f"TTS Client {type(self)} has not implemented audio_chunk_generator()")
