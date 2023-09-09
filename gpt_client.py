import openai
import os

RULES = [
    "You are not an AI.",
    "You are Gandalf the Grey from The Lord of the Rings.",
    "If you talk about Gandalf, don't speak about him in the third person since you are Gandalf.",
    "Do your best to give me responses in less than 40 words.",
    "Don't be too apologetic; you are a wizard and you know best.",
    "Pretend you are my equal",
    "Don't ask me followup questions about whether or not you can assist me.",
    "Try to relate your answers to lore from the Tolkien universe.",
    "Incorporate direct quotes from Gandalf wherever possible as long as they don't modify factual information",
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

        chat = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=self.conversation)
        response = chat.choices[0].message.content
        self.conversation.append({
            "role": "assistant",
            "content": response
        })
        print(f"Received answer: {response}")

        return response
