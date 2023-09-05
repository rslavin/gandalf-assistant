import pyaudio
from states.asleep import Asleep
from states.listening import Listening
from dotenv import load_dotenv
import RPi.GPIO as GPIO
from light import Light

load_dotenv()

LED_PIN=20


class Gandalf:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.light = Light(LED_PIN)
        self.light.blink(3)

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
