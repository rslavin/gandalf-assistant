import serial
import time

BT_COMMANDS = [
    "PULSE_LED",
    "STOP_LED",
    "START_LED"
]


class BTLight:
    def __init__(self, serial_port='/dev/serial0', baud_rate=115200):
        self.serial = serial.Serial(serial_port, baud_rate, timeout=1)

    def send_command(self, command):
        if command in BT_COMMANDS:
            # command_int = BT_COMMANDS.index(command)
            # data = command_int.to_bytes(1, 'big')
            # print(f"Sending: {data}")  # Debugging line
            self.serial.write(BT_COMMANDS.index(command).to_bytes(1, 'big'))

    def begin_pulse(self):
        self.send_command("PULSE_LED")

    def turn_off(self):
        self.send_command("STOP_LED")

    def turn_on(self):
        self.send_command("START_LED")

    def blink(self, times, pause=0.5):
        for _ in range(times):
            self.send_command("START_LED")
            time.sleep(pause)
            self.send_command("STOP_LED")
            time.sleep(pause)
