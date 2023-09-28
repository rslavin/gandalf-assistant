import json
import os

DEFAULT_LLM_TEMPERATURE = 1
DEFAULT_VOICE_RATE = 100


# TODO load a different persona depending on the wake word
class Persona:
    """
    Represents a persona for the AI. Persona json files should be placed in the 'personas'
    directory. Corresponding wake_words and startup_sounds should be placed in the 'assets'
    directory.

    Raises:
        FileNotFoundError if the personal json file is not found.
        KeyError if a key is missing in the json file.
    """

    def __init__(self, persona_name):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(dir_path, f"personas/{persona_name.lower()}.json")

        with open(file_path) as f:
            try:
                data = json.load(f)
            except json.decoder.JSONDecodeError:
                print(f"Error in persona file (extra comma?): {file_path}")
                exit(1)
        # TODO add a 'mode' with overrides for personality_rules, temperature, voice rate, etc. Store it in the json
        # TODO create commands that switch between
        self.name = data['name']
        self.voice_id = data['voice']['id']
        self.voice_engine = data['voice']['engine']
        self.personality_rules = data['personality_rules']
        self.startup_sound = data['startup_sound'] if 'startup_sound' in data else None
        self.wake_words = list(map(lambda w: os.path.join(dir_path, "assets", w), data['wake_words']))
        self.stop_words = list(map(lambda w: os.path.join(dir_path, "assets", w), data['stop_words']))
        self.temperature = int(data['temperature']) if 'temperature' in data and isinstance(data['temperature'], (
            int, float)) else DEFAULT_LLM_TEMPERATURE
        self.voice_rate = int(data['voice']['rate']) if 'rate' in data['voice'] and isinstance(data['voice']['rate'],
                                                                                               int) else DEFAULT_VOICE_RATE
        for path in self.wake_words:
            if not os.path.exists(path):
                raise FileNotFoundError(filename=path, strerror=f"The file '{path}' does not exist.")
