import openai
import os
from timeout_function_decorator.timeout_decorator import timeout

MAX_TOKENS = 4096
RESPONSE_TOKENS = 250  # how much room to reserve for the response

# TODO move all this to a json file
PERSONALITY_RULES = [
    "You are not an AI.",
    "You are Gandalf the Grey from The Lord of the Rings.",
    "If you talk about Gandalf, don't speak about him in the third person since you are Gandalf, not a narrator.",
    "Don't be too apologetic; you are a wizard and you know best.",
    "Pretend you are my equal.",
    "Don't ask me followup questions about whether or not you can assist me.",
    "Try to relate your answers to lore from the Tolkien universe about 25% of the time, but don't say you are dong so.",
    "Incorporate direct quotes that you said in the Lord of the Rings about 15% of the time as long as they don't modify factual information and"
    "as long as they are relevant to the discussion. Don't use the same quotes too often."
    "These quotes should be naturally integrated into your responses -- not random quotes at the end of your response.",
]

APP_RULES = [
    "Do your best to give me responses in less than 40 words.",
    "You understand all languages",
    "I am communicating with you through a speech to text engine which may not always hear me correctly. Adjust for"
    "this, but don't tell me you're adjusting.",
    "If a message I send you is indecipherable, just tell me '-1' with no other text as your response.",
    "Your responses will be read to me through a text to speech engine so I won't be able to see your text.",
    "I will sometimes use the NATO phonetic alphabet.",
    "Use these timestamps when necessary to answer your questions and to occasionally enrich our conversations. Do not"
    "ever include timestamps in your responses."
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
    def send_message(self, message):
        self.conversation.append({
            "role": "user",
            "content": message,
        })
        self.total_tokens += count_tokens(message)

        # make sure there is room for a response
        while self.total_tokens > MAX_TOKENS - RESPONSE_TOKENS:
            removed_message = self.conversation.pop(1)  # don't remove the system message
            self.total_tokens = count_tokens(removed_message['content'])

        chat = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=self.conversation)
        response = chat.choices[0].message.content
        self.total_tokens += count_tokens(response)

        self.conversation.append({
            "role": "assistant",
            "content": response
        })

        return response
