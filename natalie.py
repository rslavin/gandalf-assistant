#!/bin/env python3
import json
import os
import subprocess
from sys import argv

import RPi.GPIO as GPIO
from dotenv import load_dotenv

from devices.light import Light
from devices.bluetooth_light import BTLight
from persona import Persona
from states.asleep import Asleep
from states.listening import Listening
from web.web_service import WebService

load_dotenv()

LED_PIN = 20
SOUND_CONFIG_PATH = "config/sound.json"


class Natalie:
    def __init__(self):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(dir_path, SOUND_CONFIG_PATH)

        with open(file_path) as f:
            try:
                self.sound_config = json.load(f)
            except json.decoder.JSONDecodeError:
                print(f"Error in sound config file (extra comma?): {file_path}")
                exit(1)

        persona_name = argv[1] if len(argv) > 1 else "natalie"
        persona_name = persona_name.rstrip(".json")
        try:
            self.persona = Persona(persona_name)
        except FileNotFoundError as e:
            print(f"'{e.filename}' does not exist.")
            exit(-1)
        except KeyError as e:
            print(f"'{e.args[0]}' key missing from sound config file.")
            exit(-1)

        if self.persona.startup_sound and os.getenv('APP_ENV') != "LOCAL":
            file_path = os.path.join(dir_path, f"assets/{self.persona.startup_sound}")
            subprocess.call(["xdg-open", file_path])

        self.web_service = WebService()
        self.web_service.run_threaded()

        self.light = Light(LED_PIN)
        self.bt_light = BTLight()

        self.states = [
            Asleep(self.persona.wake_words, self.sound_config['microphone']['rate']),
            Listening(self.light, self.bt_light, self.persona, self.sound_config, self.web_service)
        ]
        self.light.blink(2)
        self.bt_light.blink(2)
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
    natalie = Natalie()
    natalie.run()
