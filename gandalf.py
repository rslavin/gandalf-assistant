import pyaudio
from states.asleep import Asleep
from states.listening import Listening
from dotenv import load_dotenv
import RPi.GPIO as GPIO

load_dotenv()


class Gandalf:
    def __init__(self):
        self.pa = pyaudio.PyAudio()

        self.states = [
            Asleep(),
            Listening()
        ]
        self.current_state = 0

    def run(self):
        try:
            while True:
                self.states[self.current_state].run()
                self.current_state = (self.current_state + 1) % len(self.states)
        except KeyboardInterrupt:
            print("Cleaning up and exiting...")
            GPIO.cleanup()



if __name__ == "__main__":
    gandalf = Gandalf()
    gandalf.run()
