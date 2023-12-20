import os

from clients.llm.llm_interface import LlmClient
import google.generativeai as genai
from dotenv import load_dotenv
from timeout_function_decorator.timeout_decorator import timeout

MAX_RESPONSE_TOKENS = 600
MAX_CONTEXT_TOKENS = 32768
MODEL = "gemini-pro"

load_dotenv()


class GoogleLlm(LlmClient):

    def __init__(self, persona, max_response_tokens=MAX_RESPONSE_TOKENS, max_context_tokens=MAX_CONTEXT_TOKENS,
                 model=MODEL):
        super().__init__(persona)
        self.bump_system_message = False
        self.max_response_tokens = max_response_tokens
        self.max_context_tokens = max_context_tokens
        self.model = model
        genai.configure(
            api_key=os.getenv('GOOGLE_AI_API_KEY'),
            # max_context_tokens=max_context_tokens,
            # max_response_tokens=max_response_tokens
        )
        self.google_client = genai.GenerativeModel(self.model)
        self.conversation = None  # create in first response_generator

    @timeout(3)
    def response_generator(self, messages):
        """
        Converts openai chat completion generator chunks into text chunks.
        :param messages: List of messages of appropriate dictionaries
        :return:
        """
        messages = update_roles(messages)

        if not self.conversation:
            self.conversation = self.google_client.start_chat(history=messages)

        raw_generator = self.google_client.generate_content(
            messages,
            generation_config=genai.types.GenerationConfig(
                candidate_count=1,
                max_output_tokens=MAX_RESPONSE_TOKENS,
                temperature=self.persona.temperature
            ),
            stream=True
        )

        for chunk in raw_generator:
            if not hasattr(chunk, 'finished_reason') or chunk.finished_reason == "FINISH_REASON_STOP":
                yield chunk.text  # same as chunk.candidates[0].parts[0].text
            else:
                yield ". I'm sorry, but I could not continue generating my response."


# TODO cache this in the object
def update_roles(raw_messages):
    messages = []
    for raw_message in raw_messages:
        if raw_message['role'] == 'system':
            messages.append({'role': 'user', 'parts': [raw_message['content']]})
            messages.append({'role': 'model', 'parts': ['Okay. I will remember these directives forever.']})
        elif raw_message['role'] == 'user':
            messages.append({'role': 'user', 'parts': [raw_message['content']]})
        elif raw_message["role"] == "assistant":
            messages.append({'role': 'model', 'parts': [raw_message['content']]})

    return messages
