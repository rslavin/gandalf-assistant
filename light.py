import threading
import RPi.GPIO as GPIO
import time

MAX_PULSE_BRIGHTNESS = 75
MIN_PULSE_BRIGHTNESS = 5


def pulse_led(p, stop_event):
    p.start(0)
    while not stop_event.is_set():
        for i in range(MIN_PULSE_BRIGHTNESS, MAX_PULSE_BRIGHTNESS + 1):
            if stop_event.is_set():
                break
            p.ChangeDutyCycle(i)
            time.sleep(0.01)
        for i in range(MAX_PULSE_BRIGHTNESS, MIN_PULSE_BRIGHTNESS - 1, -1):
            if stop_event.is_set():
                break
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

    def blink(self, how_many, pause=0.5):
        for i in range(how_many):
            self.turn_on()
            time.sleep(pause)
            self.turn_off()
            time.sleep(pause)

    def turn_on(self):
        GPIO.output(self.pin, True)

    def turn_off(self):
        self.stop_event.set()
        if self.pulse_thread is not None:
            self.pulse_thread.join()
        self.p.stop()
        GPIO.output(self.pin, False)

    def begin_pulse(self):
        # Turn on LED and start pulsing in a separate thread
        self.stop_event.clear()
        self.pulse_thread = threading.Thread(target=pulse_led, args=(self.p, self.stop_event))
        self.pulse_thread.daemon = True
        self.pulse_thread.start()
