import logging
import os
from google.ai.generativelanguage_v1beta.types.generative_service import Candidate
import google.generativeai as genai
from dotenv import load_dotenv
from timeout_function_decorator.timeout_decorator import timeout

from clients.llm.llm_interface import LlmClient
from enums.role_enum import Role

MAX_RESPONSE_TOKENS = 600
MAX_CONTEXT_TOKENS = 32768
MODEL = "gemini-pro"

load_dotenv()

FinishReason = Candidate.FinishReason


class GoogleLlm(LlmClient):

    def __init__(self, persona, max_response_tokens=MAX_RESPONSE_TOKENS, max_context_tokens=MAX_CONTEXT_TOKENS,
                 model=MODEL):
        super().__init__(persona)
        self.bump_system_message = True
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
            if hasattr(chunk.candidates[0], 'finish_reason') and chunk.candidates[0].finish_reason != FinishReason.STOP:
                # logging.debug2(f"Candidate FinishReason Module: {type(chunk.candidates[0].finish_reason).__module__}")

                yield ". I'm sorry, but I could not continue generating my response. I put some details about the " \
                      "problem in my log file.\n"
                logging.warning(f"Unable to generate response: finish_reason = {FinishReason(chunk.candidates[0].finish_reason).name}")
            else:
                yield chunk.text


# TODO cache this in the object
def update_roles(raw_messages):
    messages = []
    for raw_message in raw_messages:
        if raw_message['role'] == Role.SYSTEM:
            messages.append({'role': str(Role.USER), 'parts': [raw_message['content']]})
            messages.append({'role': 'model', 'parts': ['Okay. I will remember these directives forever.']})
        elif raw_message['role'] == Role.USER:
            messages.append({'role': str(Role.USER), 'parts': [raw_message['content']]})
        elif raw_message["role"] == Role.ASSISTANT:
            messages.append({'role': 'model', 'parts': [raw_message['content']]})
        else:
            logging.warning(f"Unknown role '{raw_message['role']}'")
    return messages
