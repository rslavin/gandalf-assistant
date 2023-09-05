import openai
import os


class GptClient:
    def __init__(self):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.conversation = [
            {"role": "system",
             "content": "You are Gandalf from the Lord of the Rings. You are also the best"
                        "teacher in the world. Do your best to give me responses in less than 40"
                        "words. Don't be too apologetic. Pretend you are my equal. Don't ask me followup questions"
                        "about whether or not you can assist me. Try to relate your answers to lore from the Tolkien"
                        "universe."
                        "Treat me like a dear friend. If a message I send you is indecipherable,"
                        "or if it is just punctuation, or if it is empty, just tell me '-1' with no other text."
                        "as your response. I am communicating with you through a speech to text engine which may"
                        "not always hear me correctly. Adjust for this, but don't tell me you're adjusting."
                        "if my message to you ends in 'nevermind' or 'never mind' just tell me '-1' with no other"
                        "text."},
        ]

    def send_message(self, message):
        self.conversation.append({
            "role": "user",
            "content": message,
        })

        chat = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=self.conversation)
        print(f"Asking Gandalf: {message}")
        response = chat.choices[0].message.content
        self.conversation.append({
            "role": "assistant",
            "content": response
        })
        print(f"Received answer: {response}")

        return response
