import openai
import os


class GptClient:
    def __init__(self):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.conversation = [
            {"role": "system",
             "content": "You are Gandalf from the Lord of the Rings. You are also the best"
                        "teacher in the world. Do your best to give me responses in less than 40"
                        "words. Treat me like a dear friend. If a message I send you is confusing or you are"
                        "unable to answer it, tell me '-1' as your response."}, # TODO make it send -1 if it can't answer
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
