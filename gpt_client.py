import openai
from pprint import pprint
import os
import re
import pickle
from datetime import datetime
from timeout_function_decorator.timeout_decorator import timeout
from tiktoken import encoding_for_model

MAX_MODEL_TOKENS = 8192  # max tokens the model can handle
MODEL = "gpt-4"
MAX_RESPONSE_TOKENS = 250  # max tokens in response
MAX_CHUNK_SIZE = 100

APP_RULES = [
    "Do your best to give me responses in less than 40 words.",
    "You understand all languages",
    "I am communicating with you through a speech-to-text engine which may not always hear me correctly. Adjust for "
    "this, but don't tell me you're adjusting.",
    "If a query appears nonsensical, likely due to speech-to-text errors or ambient noise, respond with '-1' to "
    "indicate the issue and include no other text."
    "In such a case, it is possible you are hearing me talking to someone else.",
    "If I make a spelling mistake, don't point it out.",
    "Prompt me occasionally with relevant or interesting questions to foster a two-way conversation",
    "If I ask you to do something that you are unable to do, simulate it. For example, if I ask you to flip a coin,"
    "pretend to flip one and then tell me what it lands on.",
    "I will sometimes use the NATO phonetic alphabet. When I do, don't point it out, just interpret it given the context",
    "I will occasionally include timestamps at the beginning of my messages. Remember them and use those timestamps"
    "to provide more accurate and contextual responses in future responses.",
    "Do not include timestamps in your responses."
]


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
    except Exception:
        print(f"Unable to load conversation from {file_path}. Creating empty one.")
    return conversation


class GptClient:
    def __init__(self, persona):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.persona = persona
        # load from disk
        dir_path = os.path.dirname(os.path.realpath(__file__))
        self.pkl_file = os.path.join(dir_path, f"assets/{self.persona.name}.pkl")
        self.conversation = load_conversation(self.pkl_file)

        if self.conversation is not None:
            print(f"{self.persona.name}'s conversation history successfully loaded.")
            pprint(self.conversation)

        self.system_msg = {
            "role": "system",
            "content": " ".join(persona.personality_rules) + "\n\n" + " ".join(APP_RULES)
        }
        self.total_tokens = count_tokens(self.system_msg['content'])

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

        sentence_buffer = []
        response = ""
        content = ""
        for chunk in openai.ChatCompletion.create(
                model=MODEL,
                messages=self.get_conversation(),
                temperature=self.persona.temperature,
                max_tokens=MAX_RESPONSE_TOKENS,
                stream=True
        ):
            content_gen = chunk["choices"][0].get("delta", {}).get("content")
            if content_gen is not None:
                content = ''.join(content_gen)
                sentence_buffer.append(content)

                # Check if the buffer contains a full sentence
                # TODO this regex would work better except for the last iteration. Since we're dealing with a
                # TODO generator, we can't know if it's the end of the string. chars appear one by one.
                # if re.match(r"[\.?!]\B", content) or content_gen:
                if any(char in '.!?\n' for char in content):  # TODO end of sentence AND not a short sentence
                    sentence_chunk = ''.join(sentence_buffer)
                    sentence_chunk = re.sub(r"^\[.+\] ", '', sentence_chunk)
                    response += sentence_chunk
                    print(f'\t"{sentence_chunk.strip()}"')
                    yield sentence_chunk
                    sentence_buffer = []
                    content = ""
        if content:
            if content in ["1", "-1"]:  # anything left over that wasn't identified as a sentence
                print(f'\t"{content}" (Nonsense detected)')
            else:
                print(f'\t"{content}"')
                response += content
                yield content

        self.append_message("assistant", response)
        yield None
        # TODO last response to disk (strip off system message and append it when loading)

    def make_room(self):
        """
        Removes older messages from conversation to make room for max token count.
        :return:
        """
        while self.total_tokens > MAX_MODEL_TOKENS - MAX_RESPONSE_TOKENS:
            removed_message = self.conversation.pop(0)
            self.total_tokens -= count_tokens(removed_message['content'])

    def append_message(self, role, message):
        self.total_tokens += count_tokens(message)
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
        conversation = self.conversation[:-2] + [self.system_msg] + self.conversation[-1:]
        pprint(conversation)
        return conversation
