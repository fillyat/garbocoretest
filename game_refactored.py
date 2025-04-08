# game_refactored.py
# Clean one-shot game execution — no imports from returner5

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

# Game arguments
playerCount = int(sys.argv[1]) if len(sys.argv) > 1 else 5
roundTime = int(sys.argv[2]) if len(sys.argv) > 2 else 5
lives = int(sys.argv[3]) if len(sys.argv) > 3 else 3

# GPIO and display setup
A0 = 25
RESN = 24
BUTTON_PIN = 17
button_pressed = False

GPIO.setmode(GPIO.BCM)
GPIO.setup(A0, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(RESN, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1000000
spi.mode = 0b00

def send_command(cmd_list):
    GPIO.output(A0, 0)
    spi.xfer(cmd_list)

def display_img(image):
    image = image.convert('1').resize((128, 64)).rotate(180)
    slices = [[] for _ in range(8)]
    for page in range(8):
        for col in range(128):
            byte = 0x00
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
    from PIL import Image
    display_img(Image.new('1', (128, 64), 1))

def button_callback(channel):
    global button_pressed
    button_pressed = True

GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)

def wait_with_timeout(timeout):
    global button_pressed
    button_pressed = False
    start = time.time()
    while (time.time() - start) < timeout:
        if button_pressed:
            return True
        time.sleep(0.05)
    return False

def play_ticking(duration):
    pygame.mixer.init()
    tick = pygame.mixer.Sound("tick.wav")
    fast = pygame.mixer.Sound("tick_fast.wav")
    tick_channel = pygame.mixer.find_channel()
    fast_channel = pygame.mixer.find_channel()
    start = time.time()
    while time.time() - start < duration:
        if button_pressed:
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
        if button_pressed and tick_channel:
            tick_channel.stop()
            break

def lifeLogic(lst):
    return [i for i in lst if i != 0]

def create_letter_image(ngram):
    paths = {chr(i): f"letters/{chr(i)}.jpg" for i in range(65, 91)}
    imgs = []
    for ch in ngram:
        up = ch.upper()
        if up in paths:
            imgs.append(Image.open(paths[up]))
    if not imgs:
        return None
    total_w = sum(img.width for img in imgs)
    max_h = max(img.height for img in imgs)
    combo = Image.new("RGBA", (total_w, max_h), (255,255,255,0))
    x = 0
    for img in imgs:
        combo.paste(img, (x, 0))
        x += img.width
    return combo

def roundStart(players, roundTime, bigrams, trigrams, useTri):
    pick = random.choice(trigrams if useTri else bigrams)
    print("Ngram:", pick)
    combo = create_letter_image(pick)
    if combo:
        display_img(combo)
    else:
        display_clear()

    for i in range(len(players)):
        thread = threading.Thread(target=play_ticking, args=(roundTime,), daemon=True)
        thread.start()
        interrupted = wait_with_timeout(roundTime)
        thread.join()
        if not interrupted:
            players[i] -= 1
            try:
                pygame.mixer.Sound("ding.wav").play()
            except: pass
    return players

# Load ngrams
with open("top_300_bigrams.json") as f:
    bigrams = json.load(f)["top_300_bigrams"]
with open("top_300_trigrams.json") as f:
    trigrams = json.load(f)["top_300_trigrams"]

# Main game loop
players = [lives] * playerCount
baseTime = roundTime

while len([p for p in players if p > 0]) > 1:
    alive = [p for p in players if p > 0]
    lost = playerCount - len(alive)
    ratio = lost / playerCount
    useTri = ratio >= 0.6 or len(alive) == 3
    current = baseTime * (len(alive) / playerCount)
    print(f"Round with {len(alive)} players. Time: {round(current,1)}s")
    players = roundStart(players, current, bigrams, trigrams, useTri)
    players = lifeLogic(players)

print("Game over.")
try:
    display_clear()
    send_command([0xAE])
except: pass

time.sleep(1)
spi.close()
GPIO.cleanup()
