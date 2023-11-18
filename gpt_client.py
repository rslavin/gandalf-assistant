import json
import os
import shutil
import pickle
import re
from datetime import datetime

import openai
from tiktoken import encoding_for_model
from timeout_function_decorator.timeout_decorator import timeout

# max tokens the model can handle - lowering this can reduce api cost since the entire conversation is sent
# with each request
# TODO pay attention to short replies that occur due to long conversations: https://platform.openai.com/docs/guides/gpt/managing-tokens
# MAX_MODEL_TOKENS = 8192
MAX_MODEL_TOKENS = 3000
# MODEL = "gpt-3.5-turbo-16k"
MODEL = "gpt-4-1106-preview"
# MODEL = "gpt-4"
# TODO set a token threshold where it will switch from gpt4 to gpt3 after using too many tokens
MAX_RESPONSE_TOKENS = 200  # max tokens in response
HISTORY_DIR = "personas"
DIRECTIVES_PATH = "config/gpt_directives.json"


def count_tokens(text) -> int:
    encoding = encoding_for_model(MODEL)
    return len(encoding.encode(text))


def add_timestamp(text) -> str:
    timestamp = datetime.now().strftime("[%B %-d, %Y %-I:%M:%S%p]")
    return f"{timestamp} {text}"


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

        self.system_msg = {
            "role": "system",
            "content": " ".join(persona.personality_rules) + "\n\n" + " ".join(get_system_directives())
        }
        self.total_tokens = count_tokens(self.system_msg['content'])
        self.pkl_file = os.path.join(dir_path, HISTORY_DIR, conv_file)
        self.conversation = []
        self.load_conversation()
        self.make_room()
        # if self.conversation:
        #     pprint(self.conversation)

    def load_conversation(self):
        try:
            with open(self.pkl_file, "rb") as f:
                while True:
                    try:
                        msg = pickle.load(f)
                        # pprint(msg)
                        self.append_message(msg['role'], msg['content'])
                    except EOFError:
                        break
            self.make_room()
            shutil.copy(self.pkl_file, f"{self.pkl_file}.backup")
        except Exception as e:
            print(f"The following exception occurred when trying to load {self.pkl_file}: {e}")
            print("Recovering backup...")
            shutil.copy(f"{self.pkl_file}.backup", self.pkl_file)

        if self.conversation:
            print(f"{self.persona.name}'s conversation history successfully loaded.")
        else:
            print("The conversation was not loaded. A new conversation has been created.")

    @timeout(15)
    def get_response(self, message):
        self.append_message("user", message, to_disk=True)
        self.make_room()

        chat = openai.ChatCompletion.create(
            model=MODEL,
            messages=self.get_conversation(),
            temperature=self.persona.temperature,
            max_tokens=MAX_RESPONSE_TOKENS
        )
        response = chat.choices[0].message.content
        self.append_message("assistant", response, to_disk=True)

        return response

    def get_total_token_count(self):
        total = count_tokens(self.system_msg['content'])
        for message in self.conversation:
            if 'content' in message:
                total += count_tokens(message['content'])
        return total

    @timeout(8)
    def get_response_generator(self, message):
        # TODO make modifications directly to the message to reinforce certain rules
        self.append_message("user", add_timestamp(message), to_disk=True)
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
                if re.search(r"[^\s.\d]{2,}[\.\?!\n]", sentence_buffer):
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
        # TODO if the choices[0].get("finish_reason") is "length", have the system let the user know they've reached
        # TODO the directed maximum token limit and ask if they'd like the system to continue. (will have to allow "yes" and "no" through preprocessing)
        self.append_message("assistant", response, to_disk=True)
        yield None

    def make_room(self):
        """
        Removes older messages from conversation to make room for max token count.
        :return:
        """
        # TODO at fixed intervals, make a separate request to summarize the important parts of the history for long term
        # self.total_tokens includes the system token count
        while self.total_tokens > MAX_MODEL_TOKENS - MAX_RESPONSE_TOKENS:
            # TODO instead of popping one at a time, keep a token count with each message so the messages can be more easily pruned
            removed_message = self.conversation.pop(0)
            removed_token_count = count_tokens(removed_message['content'])
            self.total_tokens -= removed_token_count
            print(f"Pruning history to make room... {removed_token_count} tokens freed.")

    def append_message(self, role, message, to_disk=False):
        message_tokens = count_tokens(message)
        print(f"Message tokens: {message_tokens}")
        self.total_tokens += message_tokens
        print(f"Total tokens: {self.total_tokens} / {MAX_MODEL_TOKENS}")

        message = {
            "role": role,
            "content": message,
            # "origin": "web|voice",
            # "timestamp": "time",
            # "tokens": message_tokens,
            # "model": model,
        }
        # TODO add timestamp
        self.conversation.append(message)
        if to_disk:
            try:
                # store in a tmp file in case the file terminates while writing. This mitigates corruptions.
                with open(self.pkl_file, "ab+") as f:
                    pickle.dump(message, f)
                shutil.copy(self.pkl_file, f"{self.pkl_file}.tmp")
            except Exception as e:
                print(f"Unable to write to {self.pkl_file}: {e}")
                print("Recovering backup...")
                shutil.copy(f"{self.pkl_file}.tmp", self.pkl_file)

    def get_conversation(self):
        conversation = self.conversation[:-3] + [self.system_msg] + self.conversation[-2:]
        # pprint(conversation)
        return conversation


class InvalidInputError(Exception):
    pass
