# Natural Language Interaction Engine (Natalie)
A voice assistant built to run on a Raspberry Pi. It uses the following for real-time voice assistance while following natural language directives and imitating any persona. The following APIs are used.

- Porcupine Wake Word Engine (local) - Wake word 
- OpenAI's Whisper (cloud) - Speech to text
- OpenAI's GPT3.5 or GPT4 (cloud) - Response generation
- AWS Polly (cloud) - Text to speech

# Installation
1. Clone this repository.
2. Install the necessary python modules within your virtual environment using `pip install -r requirements.txt`.
3. Install `xdg-utils` with `sudo apt-get update -y && sudo apt-get install -y xdg-utils`.
4. Create your own `.env` file based on `.env.example` and fill in the necessary API keys.
5. Train your own wake and stop words for [Porcupine](https://console.picovoice.ai/) and place the resulting ppn files in the `assets` directory.
6. Modify or create your own persona json file within the `personas` directory, be sure to register your wake and stop words there.
7. Specify your sound settings in `config/sound.json`
8. Run the program with `sudo natalie.py [personality_name]` where `personality_name` is the name of the personality to load. If left blank, Natalie will be loaded. Note that `sudo` privileges are required because of the GPIO functionality.
