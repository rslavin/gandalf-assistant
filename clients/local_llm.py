import requests

from .llm_interface import LlmClient
from openai import OpenAI
from dotenv import load_dotenv
from timeout_function_decorator.timeout_decorator import timeout
import json

MAX_RESPONSE_TOKENS = 200

load_dotenv()


class LocalLlm(LlmClient):

    def __init__(self, persona, max_tokens=MAX_RESPONSE_TOKENS):
        super().__init__(persona)
        self.max_response_tokens = max_tokens
        self.model = None

    @timeout(8)
    def response_generator(self, messages):
        headers = {'Content-Type': 'application/json'}
        # uses "bot" instead of "assistant"
        messages = [{**message, 'role': 'bot'} if message['role'] == 'assistant' else message for message in messages]
        messages = json.dumps({"messages": messages})
        for chunk in requests.post("http://ramza.lan:8050/generate", messages, stream=True, headers=headers):
            if chunk:
                yield chunk.decode('utf-8').rstrip("</s>")

    # @timeout(15)
    # def get_response(self, message):
    #     self.append_message("user", message, to_disk=True)
    #     self.make_room()
    #
    #     chat = self.llm_client.chat.completions.create(
    #         model=MODEL,
    #         messages=self.get_conversation(),
    #         temperature=self.persona.temperature,
    #         max_tokens=MAX_RESPONSE_TOKENS
    #     )
    #     response = chat.choices[0].message.content
    #     self.append_message("assistant", response, to_disk=True)
    #
    #     return response
