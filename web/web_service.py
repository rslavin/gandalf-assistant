import logging
import threading
import time

from flask import Flask, render_template
from flask_socketio import SocketIO

import conversationmanager
from conversationmanager import InvalidInputError
from enums.role_enum import Role


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class WebService(metaclass=SingletonMeta):
    def __init__(self):
        if hasattr(self, "initialized") and self.initialized:
            return

        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app)
        self._setup_routes()
        self._setup_socket_events()
        self.conversation_manager = None
        self.initialized = True

    def _setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

    def _setup_socket_events(self):
        @self.socketio.on("connect")
        def handle_connect():
            if self.conversation_manager:
                messages = self.conversation_manager.conversation
                for message in messages:
                    if message['role'] == Role.ASSISTANT:
                        self.send_new_assistant_msg(message['content'], message['origin'], timestamp=message['timestamp'])
                    else:
                        self.send_new_user_msg(conversationmanager.remove_timestamp(message['content']), message['origin'], timestamp=message['timestamp'])
                logging.info(f"New web client connection. Sending {len(messages)} messages from conversation.")

        @self.socketio.on('client_user_msg')
        def handle_recv_user_msg(message):
            # TODO preprocess!
            # TODO ``code`` and copy
            try:
                gen = self.conversation_manager.get_response(message, origin="web")
                for chunk in gen:
                    pass  # messages are automatically sent by the generator (for centralization)

            except InvalidInputError:
                self.send_new_assistant_msg("<Nonsense detected>", self.conversation_manager.llm_client.model)
            except TimeoutError:
                pass

    def emit_update(self, msg_type, message, origin, timestamp=None):
        """

        :param msg_type: 'user_msg', 'assistant_msg', or 'assistant_append' depending on whether it is a whole user
        messages, the first chunk of an assistant message, or a subsequent chunk of an assistant message
        :param message:
        :param origin:
        :param timestamp:
        :return:
        """

        if timestamp is None:
            timestamp = time.time()
        if message is not None:
            self.socketio.emit('server_chat_msg', {"msg_type": msg_type, "message": message, "origin": origin, "timestamp": timestamp})

    def send_new_user_msg(self, message, origin, timestamp=None):
        self.emit_update('user_msg', message, origin, timestamp=timestamp)

    def send_new_assistant_msg(self, message, origin, timestamp=None):
        self.emit_update('assistant_msg', message, origin, timestamp=timestamp)

    def append_assistant_msg(self, message):
        self.emit_update('assistant_append', message, origin="n/a")

    def run_threaded(self):
        t = threading.Thread(target=self.run)
        t.daemon = True
        t.start()

    def run(self):
        self.socketio.run(self.app, host='0.0.0.0', port=80)


if __name__ == "__main__":
    server = WebService()
    server.run_threaded()
