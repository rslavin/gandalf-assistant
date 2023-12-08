import json
import os

import requests
from dotenv import load_dotenv
from timeout_function_decorator.timeout_decorator import timeout

from .llm_interface import LlmClient

MAX_RESPONSE_TOKENS = 200
MAX_CONTEXT_TOKENS = 4096

load_dotenv()


class LocalLlm(LlmClient):

    def __init__(self, persona, max_tokens=MAX_RESPONSE_TOKENS):
        super().__init__(persona)
        self.max_response_tokens = max_tokens
        self.model = None
        # self.first_message = True  # the api only requires the most recent message once it has built a cache

    @timeout(8)
    def response_generator(self, messages):
        suffix = "</s>"
        headers = {'Content-Type': 'application/json'}
        # if self.first_message:
        #     self.first_message = False
        # else:
        #     messages = [messages[-1]]
        # uses "bot" instead of "assistant" -- also add the </s> back to bot messages
        messages = [{**message, 'role': 'bot', 'content': message['content'] + "</s>"} if message['role'] == 'assistant' else message for message in messages]
        messages = json.dumps({"messages": messages})

        for chunk in requests.post(os.getenv("LOCAL_LLM_URL"), messages, stream=True, headers=headers):
            if chunk:
                chunk = chunk.decode('utf-8')
                yield chunk[:-len(suffix)] if chunk.endswith("</s>") else chunk

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
