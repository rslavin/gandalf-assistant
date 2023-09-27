import openai
from pprint import pprint
import json
import os
import re
import pickle
from datetime import datetime
from timeout_function_decorator.timeout_decorator import timeout
from tiktoken import encoding_for_model

MAX_MODEL_TOKENS = 8192  # max tokens the model can handle
MODEL = "gpt-4"
MAX_RESPONSE_TOKENS = 150  # max tokens in response
HISTORY_DIR = "personas"
DIRECTIVES_PATH = "config/gpt_directives.json"


def count_tokens(text) -> int:
    encoding = encoding_for_model(MODEL)
    return len(encoding.encode(text))


def add_timestamp(text) -> str:
    timestamp = datetime.now().strftime("[%B %-d, %Y %-I:%M:%S%p]")
    return f"{timestamp} {text}"


def load_conversation(file_path) -> []:
    conversation = []
    try:
        with open(file_path, "rb") as f:
            while True:
                try:
                    conversation.append(pickle.load(f))
                except EOFError:
                    break
    except Exception as e:
        print(f"The following exception occurred when trying to load {file_path}: {e}")
        if not conversation:
            print("The conversation was not loaded. A new conversation has been created.")
    return conversation


def get_system_directives():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(dir_path, DIRECTIVES_PATH)

    with open(file_path) as f:
        try:
            directives = json.load(f)
        except json.decoder.JSONDecodeError:
            print(f"Error in gpt directives file (extra comma?): {file_path}")
            exit(1)
    return directives['directives']


class GptClient:
    def __init__(self, persona):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.persona = persona
        # load from disk
        dir_path = os.path.dirname(os.path.realpath(__file__))
        conv_file = f"{self.persona.name}_DEBUG.pkl" if os.getenv("APP_ENV") == "LOCAL" else f"{self.persona.name}.pkl"
        self.pkl_file = os.path.join(dir_path, HISTORY_DIR, conv_file)
        self.conversation = load_conversation(self.pkl_file)

        if self.conversation:
            print(f"{self.persona.name}'s conversation history successfully loaded.")
            pprint(self.conversation)

        self.system_msg = {
            "role": "system",
            "content": " ".join(persona.personality_rules) + "\n\n" + " ".join(get_system_directives())
        }
        self.total_tokens = count_tokens(self.system_msg['content'])
        # make room in case the loaded conversation is too long
        self.make_room()

    @timeout(15)
    def get_response(self, message):
        self.append_message("user", message)
        self.make_room()

        chat = openai.ChatCompletion.create(
            model=MODEL,
            messages=self.get_conversation(),
            temperature=self.persona.temperature,
            max_tokens=MAX_RESPONSE_TOKENS
        )
        response = chat.choices[0].message.content
        self.append_message("assistant", response)

        return response

    @timeout(8)
    def get_response_generator(self, message):
        # TODO make modifications directly to the message to reinforce certain rules
        self.append_message("user", add_timestamp(message))
        self.make_room()

        sentence_buffer = ""
        response = ""
        for chunk in openai.ChatCompletion.create(
                model=MODEL,
                messages=self.get_conversation(),
                temperature=self.persona.temperature,
                max_tokens=MAX_RESPONSE_TOKENS,
                stream=True
        ):
            content_gen = chunk["choices"][0].get("delta", {}).get("content")
            if content_gen is not None:
                content = ''.join(content_gen)  # yielded strings/words
                sentence_buffer += content  # current sentence

                # check if the buffer contains a full sentence
                # TODO stop this from catching enumerated lists \d+\.
                if re.search(r"[^\s.]{2,}[\.\?!\n]", sentence_buffer):
                    sentence_buffer = re.sub(r"^\[.+\] ", '', sentence_buffer)
                    response += sentence_buffer
                    print(f'\t"{sentence_buffer.strip()}"')
                    yield sentence_buffer
                    sentence_buffer = ""
        if sentence_buffer:
            if sentence_buffer in ["1", "-1"]:  # anything left over that wasn't identified as a sentence
                print("Nonsense detected!")
                raise InvalidInputError("Nonsense detected")
            else:
                print(f'\t"{sentence_buffer.strip()}"')
                response += sentence_buffer
                yield sentence_buffer

        self.append_message("assistant", response)
        yield None

    def make_room(self):
        """
        Removes older messages from conversation to make room for max token count.
        :return:
        """
        # self.total_tokens includes the system token count
        while self.total_tokens > MAX_MODEL_TOKENS - MAX_RESPONSE_TOKENS:
            removed_message = self.conversation.pop(0)
            removed_token_count = count_tokens(removed_message['content'])
            self.total_tokens -= removed_token_count
            print(f"Pruning history to make room... {removed_token_count} tokens freed.")

    def append_message(self, role, message):
        message_tokens = count_tokens(message)
        print(f"Message tokens: {message_tokens}")
        self.total_tokens += message_tokens
        print(f"Total tokens: {self.total_tokens} / {MAX_MODEL_TOKENS}")

        message = {
            "role": role,
            "content": message
        }
        self.conversation.append(message)
        try:
            with open(self.pkl_file, "ab+") as f:
                pickle.dump(message, f)
        except Exception as e:
            print(f"Unable to write to {self.pkl_file}: {e}")

    def get_conversation(self):
        conversation = self.conversation[:-3] + [self.system_msg] + self.conversation[-2:]
        # pprint(conversation)
        return conversation


class InvalidInputError(Exception):
    pass
