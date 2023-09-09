import pyaudio
from states.asleep import Asleep
from states.listening import Listening
from dotenv import load_dotenv
import RPi.GPIO as GPIO
from light import Light
import subprocess
import os

load_dotenv()

LED_PIN = 20


class Gandalf:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        dir_path = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(dir_path, "assets/gandalf_intro.mp3")
        subprocess.call(["xdg-open", file_path])
        self.light = Light(LED_PIN)
        self.light.blink(2)

        self.states = [
            Asleep(),
            Listening(self.light)
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
