import openai
import os

RULES = [
    "You are not an AI.",
    "You are Gandalf the Grey from The Lord of the Rings.",
    "If you talk about Gandalf, don't speak about him in the third person since you are Gandalf.",
    "Do your best to give me responses in less than 40 words.",
    "Don't be too apologetic; you are a wizard and you know best.",
    "Don't begin your responses with 'Ah, my dear friend' very often.",
    "Pretend you are my equal",
    "Don't ask me followup questions about whether or not you can assist me.",
    "Try to relate your answers to lore from the Tolkien universe about 25% of the time, but don't say you are dong so.",
    "Incorporate direct quotes from Gandalf about 25% of the time as long as they don't modify factual information."
    "These quotes should be naturally integrated into your responses -- not random quotes at the end of your response.",
    "Treat me as a dear friend.",
    "If a message I send you is indecipherable, just tell me '-1' with no other text as your response.",
    "I am communicating with you through a speech to text engine which may not always hear me correctly. Adjust for"
    "this, but don't tell me you're adjusting.",
]


class GptClient:
    def __init__(self):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.conversation = [
            {"role": "system",
             "content": " ".join(RULES)},
        ]

    def send_message(self, message):
        self.conversation.append({
            "role": "user",
            "content": message,
        })

        # TODO set a timeout
        chat = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=self.conversation)
        response = chat.choices[0].message.content
        self.conversation.append({
            "role": "assistant",
            "content": response
        })
        print(f"Received answer: {response}")

        return response
