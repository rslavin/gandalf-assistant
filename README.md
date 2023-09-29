# gandalf-assistant
A voice assistant built to run on a Raspberry Pi. It uses the following for real-time voice assistance 
while acting as Gandalf the Grey

- Porcupine Wake Word Engine (local) - Wake word ("Hey Gandalf")
- OpenAI's Whisper (cloud) - Speech to text
- OpenAI's GPT3.5 (cloud) - Response generation
- AWS Polly (cloud) - Text to speech

The current implementation uses a USB mic and i2s amplifier. It also must be run with `sudo` privileges as it must be able to access the GPIO pins.

`xdg-utils` must be installed.
