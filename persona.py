import json
import os

DEFAULT_LLM_TEMPERATURE = 1
DEFAULT_VOICE_RATE = 100


def add_wake_word_paths(wake_word_tuple, dir_path):
    file_paths, sensitivities = zip(*wake_word_tuple)
    file_paths = [os.path.join(dir_path, "assets", w) for w in file_paths]
    return [[w, s] for w, s in zip(file_paths, sensitivities)]


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

    def __init__(self, persona_name, sample_rate):
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
        self.wake_words = add_wake_word_paths(data['wake_words'], dir_path)
        self.stop_words = add_wake_word_paths(data['stop_words'], dir_path)
        self.sample_rate = sample_rate
        self.temperature = int(data['temperature']) if 'temperature' in data and isinstance(data['temperature'], (
            int, float)) else DEFAULT_LLM_TEMPERATURE
        self.voice_rate = int(data['voice']['rate']) if 'rate' in data['voice'] and isinstance(data['voice']['rate'],
                                                                                               int) else DEFAULT_VOICE_RATE
        for wake_word in self.wake_words:
            if not os.path.exists(wake_word[0]):
                raise FileNotFoundError()
