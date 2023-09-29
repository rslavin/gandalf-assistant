from audio_utils import wait_for_wake_word
from .state_interface import State


WAKE_SENSITIVITIES = [0.6]


class Asleep(State):

    def __init__(self, wakewords, mic_rate):
        self.wakewords = wakewords
        self.mic_rate = mic_rate

    # TODO add a wake word that simply responds with who the current personality is: "what personality is loaded?"
    def run(self):
        print("Entering Sleep state.")
        return wait_for_wake_word(WAKE_SENSITIVITIES, self.wakewords, self.mic_rate)


