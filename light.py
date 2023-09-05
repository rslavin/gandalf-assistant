import threading
import RPi.GPIO as GPIO
import time


def pulse_led(p):
    p.start(0)
    while True:
        for i in range(0, 75):
            p.ChangeDutyCycle(i)
            time.sleep(0.01)
        for i in range(74, -1, -1):  # -1 to include 0
            p.ChangeDutyCycle(i)
            time.sleep(0.01)


class Light:

    def __init__(self, pin):
        self.pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        self.p = GPIO.PWM(pin, 50)
        self.pulse_thread = None
        self.stop_event = threading.Event()

    def turn_on(self):
        GPIO.output(self.pin, True)

    def turn_off(self):
        GPIO.output(self.pin, False)

    def begin_pulse(self):
        # Turn on LED and start pulsing in a separate thread
        self.stop_event.clear()
        self.pulse_thread = threading.Thread(target=pulse_led, args=(self.p,))
        self.pulse_thread.daemon = True  # Daemon threads are killed when the program exits
        self.pulse_thread.start()

    def end_pulse(self):
        print("ending pulse")
        if self.pulse_thread is not None:
            self.pulse_thread.join(timeout=1)  # This will block until the thread finishes or timeout occurs
        self.p.stop()
        GPIO.output(self.pin, False)
