# ----------------------------- 1G.py (game) -----------------------------
import os
import sys
import time
import json
import random
import spidev
import RPi.GPIO as GPIO
from PIL import Image
import threading
import pygame
import atexit

# Game arguments from the launcher: playerCount, roundTime, lives
playerCount = int(sys.argv[1]) if len(sys.argv) > 1 else 5
roundTime = int(sys.argv[2]) if len(sys.argv) > 2 else 5
lives = int(sys.argv[3]) if len(sys.argv) > 3 else 3

# GPIO and display setup (shared with the launcher)
A0 = 25
RESN = 24
BUTTON_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(A0, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(RESN, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1_000_000
spi.mode = 0b00

# -----------------------------------------------------------------------------
# Helper to release all resources when the game exits
# -----------------------------------------------------------------------------

def cleanup():
    """Free button interrupt, SPI handle and GPIO lines so the launcher can reuse them."""
    try:
        GPIO.remove_event_detect(BUTTON_PIN)
    except RuntimeError:
        pass

    spi.close()
    GPIO.cleanup((A0, RESN, BUTTON_PIN))

atexit.register(cleanup)

# -----------------------------------------------------------------------------
# Display helpers (unchanged)
# -----------------------------------------------------------------------------

def send_command(cmd_list):
    GPIO.output(A0, 0)
    spi.xfer(cmd_list)


def display_img(image):
    image = image.convert("1").resize((128, 64)).rotate(180)
    slices = [[] for _ in range(8)]
    for page in range(8):
        for col in range(128):
            byte = 0
            for bit in range(8):
                pixel = image.getpixel((col, page * 8 + bit))
                byte |= ((0 if pixel == 255 else 1) << bit)
            slices[page].append(byte)
    send_command([0xAF])
    for page in range(8):
        send_command([0xB0 + page, 0x02, 0x10])
        GPIO.output(A0, 1)
        spi.xfer(slices[page])


def display_clear():
    display_img(Image.new("1", (128, 64), 1))

# -----------------------------------------------------------------------------
# Button + sound helpers (existing logic kept intact)
# -----------------------------------------------------------------------------
button_event = threading.Event()

def button_callback(channel):
    button_event.set()

GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)


def wait_with_timeout(timeout):
    button_event.clear()
    start = time.time()
    while time.time() - start < timeout:
        if button_event.is_set():
            return True
        time.sleep(0.05)
    return False


def play_ticking(duration):
    tick = pygame.mixer.Sound("tick.wav")
    fast = pygame.mixer.Sound("tick_fast.wav")
    tick_channel = pygame.mixer.find_channel()
    fast_channel = pygame.mixer.find_channel()
    start = time.time()
    while time.time() - start < duration:
        if button_event.is_set():
            if tick_channel:
                tick_channel.stop()
            break
        remaining = duration - (time.time() - start)
        if remaining > 2:
            if tick_channel:
                tick_channel.stop()
            tick_channel = tick.play()
            time.sleep(1)
        else:
            if fast_channel:
                fast_channel.stop()
            fast_channel = fast.play()
            time.sleep(0.3)
        if button_event.is_set() and tick_channel:
            tick_channel.stop()
            break

# -----------------------------------------------------------------------------
# Your existing game loop / logic goes below.
# Make sure it eventually returns so that `cleanup()` can run.
# -----------------------------------------------------------------------------

def main():
    # Placeholder for your actual game logic
    display_clear()
    time.sleep(2)  # simulate a short game round


if __name__ == "__main__":
    main()
