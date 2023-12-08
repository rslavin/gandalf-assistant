import json
import logging
import os
import pickle
import re
import shutil
from datetime import datetime

from tiktoken import encoding_for_model

from clients.gpt_llm import GptLlm as llm_client

# from clients.local_llm import LocalLlm as llm_client

# TODO pay attention to short replies that occur due to long conversations: https://platform.openai.com/docs/guides/gpt/managing-tokens
# TODO set a token threshold where it will switch from gpt4 to gpt3 after using too many tokens
HISTORY_DIR = "personas"
DIRECTIVES_PATH = "config/llm_directives.json"


def count_tokens(text, model=None) -> int:
    model = "gpt-3.5-turbo" if model is None else model
    encoding = encoding_for_model(model)
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
            logging.error(f"Error in gpt directives file (extra comma?): {file_path}")
            exit(1)
    return directives['directives']


class ConversationManager:
    def __init__(self, persona):
        self.persona = persona
        self.llm_client = llm_client(self.persona)
        # load from disk
        dir_path = os.path.dirname(os.path.realpath(__file__))
        conv_file = f"{self.persona.name}_DEBUG.pkl" if os.getenv("APP_ENV") == "LOCAL" else f"{self.persona.name}.pkl"

        self.system_msg = {
            "role": "system",
            "content": " ".join(persona.personality_rules) + "\n\n" + " ".join(get_system_directives())
        }
        self.total_tokens = count_tokens(self.system_msg['content'], self.llm_client.model)
        self.pkl_file = os.path.join(dir_path, HISTORY_DIR, conv_file)
        self.conversation = []
        self.load_conversation()

    def load_conversation(self):
        try:
            with open(self.pkl_file, "rb") as f:
                while True:
                    try:
                        msg = pickle.load(f)
                        # pprint(msg)
                        self.append_message(msg['role'], msg['content'], silent=True)
                    except EOFError:
                        break
            self.make_room(silent=True)
            shutil.copy(self.pkl_file, f"{self.pkl_file}.backup")
        except Exception as e:
            logging.warning(f"The following exception occurred when trying to load {self.pkl_file}: {e}")
            logging.warning("Recovering backup...")
            try:
                shutil.copy(f"{self.pkl_file}.backup", self.pkl_file)
                logging.warning("Success!")
                self.load_conversation()
                return
            except Exception as e2:
                logging.warning("Backup not recoverable")

        if self.conversation:
            logging.info(f"{self.persona.name}'s conversation history successfully loaded.")
        else:
            logging.warning("The conversation was not loaded. A new conversation has been created.")

    def get_total_token_count(self):
        total = count_tokens(self.system_msg['content'], self.llm_client.model)
        for message in self.conversation:
            if 'content' in message:
                total += count_tokens(message['content'], self.llm_client.model)
        return total

    def get_response(self, message):
        # TODO make modifications directly to the message to reinforce certain rules
        self.append_message("user", add_timestamp(message), to_disk=True)
        self.make_room()

        sentence_buffer = ""
        response = ""
        for chunk in self.llm_client.response_generator(self.get_conversation()):
            if chunk is not None:
                sentence_buffer += chunk  # current sentence

                # check if the buffer contains a full sentence
                if re.search(r"[^\s.\d]{2,}[\.\?!\n]", sentence_buffer):
                    sentence_buffer = re.sub(r"^\[.+\] ", '', sentence_buffer)
                    response += sentence_buffer
                    logging.info(f'\t"{sentence_buffer.strip()}"')
                    yield sentence_buffer
                    sentence_buffer = ""
        if sentence_buffer:
            if sentence_buffer in ["1", "-1"]:  # anything left over that wasn't identified as a sentence
                logging.info("Nonsense detected!")
                raise InvalidInputError("Nonsense detected")
            else:
                logging.info(f'\t"{sentence_buffer.strip()}"')
                response += sentence_buffer
                yield sentence_buffer
        # TODO if the choices[0].get("finish_reason") is "length", have the system let the user know they've reached
        # TODO the directed maximum token limit and ask if they'd like the system to continue. (will have to allow "yes" and "no" through preprocessing)
        self.append_message("assistant", response, to_disk=True)
        yield None

    def make_room(self, silent=False):
        """
        Removes older messages from conversation to make room for max token count.
        :return:
        """
        # TODO at fixed intervals, make a separate request to summarize the important parts of the history for long term
        # self.total_tokens includes the system token count
        while len(self.conversation) > 1 and self.total_tokens > self.llm_client.max_context_tokens - self.llm_client.max_response_tokens:
            # TODO instead of popping one at a time, keep a token count with each message so the messages can be more easily pruned
            removed_message = self.conversation.pop(0)
            removed_token_count = count_tokens(removed_message['content'], self.llm_client.model)
            self.total_tokens -= removed_token_count
            if not silent:
                logging.info(f"Pruning history to make room... {removed_token_count} tokens freed.")

    def append_message(self, role, message, to_disk=False, silent=False):
        message_tokens = count_tokens(message, self.llm_client.model)
        if not silent:
            logging.info(f"Message tokens: {message_tokens}")
        self.total_tokens += message_tokens
        if not silent:
            logging.info(f"Total tokens: {self.total_tokens} / {self.llm_client.max_context_tokens}")

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
                logging.warning(f"Unable to write to {self.pkl_file}: {e}")
                logging.warning("Recovering backup...")
                shutil.copy(f"{self.pkl_file}.tmp", self.pkl_file)

    def get_conversation(self):
        # conversation = self.conversation[:-3] + [self.system_msg] + self.conversation[-2:]
        conversation = [self.system_msg] + self.conversation
        # pprint(conversation)
        return conversation


class InvalidInputError(Exception):
    pass
