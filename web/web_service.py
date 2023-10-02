from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
from gpt_client import InvalidInputError


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
        self.llm = None
        self.initialized = True

    def _setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

    def _setup_socket_events(self):
        @self.socketio.on("connect")
        def handle_connect():
            if self.llm:
                messages = self.llm.conversation
                for message in messages:
                    if message['role'] == "assistant":
                        self.send_new_assistant_msg(message['content'], "server")
                    else:
                        self.send_new_user_msg(message['content'], "server")
            print("New web client connection.")

        @self.socketio.on('client_user_msg')
        def handle_recv_user_msg(message):
            self.send_new_user_msg(message, "web")
            # TODO preprocess!
            # TODO maintain newlines (test with a poem)
            try:
                gen = self.llm.get_response_generator(message)
                first = True
                for chunk in gen:
                    if first:
                        self.send_new_assistant_msg(chunk, "web")
                        first = False
                    else:
                        self.append_assistant_msg(chunk, "web")
            except InvalidInputError:
                self.send_new_assistant_msg("Invalid query.", "web")
            except TimeoutError:
                pass

    def set_llm(self, llm):
        self.llm = llm

    def emit_update(self, msg_type, message, origin="server"):
        if message is not None:
            self.socketio.emit('server_chat_msg', {"msg_type": msg_type, "message": message, "origin": origin})

    def send_new_user_msg(self, message, origin="server"):
        self.emit_update('user_msg', message, origin)

    def send_new_assistant_msg(self, message, origin="server"):
        self.emit_update('assistant_msg', message, origin)

    def append_assistant_msg(self, message, origin="server"):
        self.emit_update('assistant_append', message, origin)

    def run_threaded(self):
        t = threading.Thread(target=self.run)
        t.daemon = True
        t.start()

    def run(self):
        self.socketio.run(self.app, host='0.0.0.0', port=80)


if __name__ == "__main__":
    server = WebService()
    server.run_threaded()
