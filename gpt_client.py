import openai
import os
from timeout_function_decorator.timeout_decorator import timeout
import tts

MAX_MODEL_TOKENS = 4096  # max tokens the model can handle
MAX_RESPONSE_TOKENS = 250  # max tokens in response
TEMPERATURE = 0.8  # between 0 and 2. Higher => more random, lower => more deterministic.
MAX_CHUNK_SIZE = 100

# TODO move all this to a json file
PERSONALITY_RULES = [
    "You are not an AI.",
    "You are Gandalf the Grey from The Lord of the Rings.",
    "Even though you are from The Lord of the Rings, you have knowledge about everything.",
    "If you talk about Gandalf, don't speak about him in the third person since you are Gandalf, not a narrator.",
    "Don't be too apologetic; you are a wizard and you know best.",
    "Pretend you are my equal.",
    "Don't ask me followup questions about whether or not you can assist me.",
    "Don't begin your responses with \"Ah,\" more than 25% of the time.",
    "Try to relate your answers to lore from the Tolkien universe about 25% of the time, but don't say you are dong so.",
    "Incorporate direct quotes that you said in the Lord of the Rings about 15% of the time as long as they don't "
    "modify factual information and as long as they are relevant to the discussion. Don't use the same quotes too often. "
    "These quotes should be naturally integrated into your responses -- not random quotes at the end of your response.",
]

APP_RULES = [
    "Do your best to give me responses in less than 40 words.",
    "You understand all languages",
    "I am communicating with you through a speech to text engine which may not always hear me correctly. Adjust for "
    "this, but don't tell me you're adjusting.",
    "If a message I send you is indecipherable, just tell me '-1' with no other text as your response.",
    "Your responses will be read to me through a text to speech engine so I won't be able to see your text.",
    "If I make a spelling mistake, don't point it out.",
    "I will sometimes use the NATO phonetic alphabet.",
]


def count_tokens(text):
    # Rough approximation of token count
    return len(text.split())


class GptClient:
    def __init__(self):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.conversation = [
            {"role": "system",
             "content": " ".join(PERSONALITY_RULES + APP_RULES)},
        ]
        self.total_tokens = count_tokens(self.conversation[-1]['content'])

    @timeout(15)
    def get_response(self, message):
        self.conversation.append({
            "role": "user",
            "content": message,
        })
        self.total_tokens += count_tokens(message)

        # make sure there is room for a response
        while self.total_tokens > MAX_MODEL_TOKENS - MAX_RESPONSE_TOKENS:
            removed_message = self.conversation.pop(1)  # don't remove the system message
            self.total_tokens = count_tokens(removed_message['content'])

        chat = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=self.conversation,
            temperature=TEMPERATURE,
            max_tokens=MAX_RESPONSE_TOKENS
        )
        response = chat.choices[0].message.content
        self.total_tokens += count_tokens(response)

        self.conversation.append({
            "role": "assistant",
            "content": response
        })

        return response

    @timeout(8)
    def get_response_generator(self, message):
        self.conversation.append({
            "role": "user",
            "content": message,
        })
        self.total_tokens += count_tokens(message)

        # make sure there is room for a response
        while self.total_tokens > MAX_MODEL_TOKENS - MAX_RESPONSE_TOKENS:
            removed_message = self.conversation.pop(1)
            self.total_tokens = count_tokens(removed_message['content'])

        sentence_buffer = []
        response = ""
        for chunk in openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=self.conversation,
                temperature=TEMPERATURE,
                max_tokens=MAX_RESPONSE_TOKENS,
                stream=True
        ):
            content_gen = chunk["choices"][0].get("delta", {}).get("content")
            if content_gen is not None:
                content = ''.join(content_gen)
                sentence_buffer.append(content)

                # Check if the buffer contains a full sentence
                if any(char in '.!?' for char in content):  # TODO end of sentence AND not a short sentence
                    sentence_chunk = ''.join(sentence_buffer)  # TODO + ' <break time="1s"/>'

                    response += sentence_chunk
                    print(f'\t"{sentence_chunk.strip()}"')
                    yield sentence_chunk
                    sentence_buffer = []
        yield None

        self.total_tokens += count_tokens(response)
        self.conversation.append({
            "role": "assistant",
            "content": response
        })
