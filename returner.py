# music.py
# -*- coding: utf-8 -*-
"""
Combined N-gram Game + SH1106 Display on Raspberry Pi,
with button-based immediate interrupt and ticking sound feedback (pygame).
Includes end-game options to return to launcher or shut down.
"""

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

# BUTTON INPUT SETUP
BUTTON_PIN = 17  # BCM pin 17 (physical pin 11)
button_pressed = False

def button_callback(channel):
    global button_pressed
    button_pressed = True
    if pygame.mixer.get_init():
        pygame.mixer.Sound("ding.wav").play()

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)

###############################################################################
# SH1106 / SPI DISPLAY SETUP
###############################################################################
A0   = 25  # BCM pin 25
RESN = 24  # BCM pin 24

GPIO.setup(A0, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(RESN, GPIO.OUT, initial=GPIO.HIGH)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1000000
spi.mode = 0b00

def send_command(cmd_list):
    GPIO.output(A0, 0)
    spi.xfer(cmd_list)

def display_img(image):
    data_slice = [[] for _ in range(8)]
    image = image.convert('1')
    image = image.resize((128, 64))
    image = image.rotate(180)  # Rotate image 180 degrees

    for p in range(8):
        data_set = []
        for c in range(128):
            b_byte = 0x00
            for b in range(8):
                pixel = image.getpixel((c, p * 8 + b))
                bit_val = 0 if pixel == 255 else 1
                b_byte |= (bit_val << b)
            data_set.append(b_byte)
        data_slice[p] = data_set

    send_command([0xAF])
    for p in range(8):
        send_command([0xB0 + p, 0x02, 0x10])
        GPIO.output(A0, 1)
        spi.xfer(data_slice[p])

def display_clear():
    blank_img = Image.new('1', (128, 64), 1)
    display_img(blank_img)

def show_end_options():
    from PIL import ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    except:
        font = ImageFont.load_default()
    img = Image.new("1", (128, 64), 1)
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "A: Reboot Game", font=font, fill=0)
    draw.text((10, 30), "B: Shutdown", font=font, fill=0)
    display_img(img)

    while True:
        if GPIO.input(17) == GPIO.LOW:
            time.sleep(0.5)
            os.execv(sys.executable, ['python3', 'menu_launcher.py'])
        elif GPIO.input(27) == GPIO.LOW:
            time.sleep(0.5)
            os.system("sudo halt")
        time.sleep(0.1)

GPIO.output(RESN, 0)
time.sleep(0.1)
GPIO.output(RESN, 1)
time.sleep(0.1)

###############################################################################
# GAME LOGIC
###############################################################################
biFilePath = "top_300_bigrams.json"
triFilePath = "top_300_trigrams.json"

with open(biFilePath, 'r') as file:
    bigrams = json.load(file)

with open(triFilePath, 'r') as file:
    trigrams = json.load(file)

letter_image_paths = {chr(i): f"letters/{chr(i)}.jpg" for i in range(65, 91)}

def create_letter_image(ngram):
    letter_imgs = []
    for ch in ngram:
        upper_char = ch.upper()
        if upper_char in letter_image_paths:
            path = letter_image_paths[upper_char]
            letter_imgs.append(Image.open(path))
        else:
            print(f"No image mapped for '{ch}'")
    if not letter_imgs:
        return None
    total_width = sum(img.width for img in letter_imgs)
    max_height = max(img.height for img in letter_imgs)
    combined = Image.new("RGBA", (total_width, max_height), (255,255,255,0))
    x_offset = 0
    for img in letter_imgs:
        combined.paste(img, (x_offset, 0))
        x_offset += img.width
    return combined

def lifeLogic(lst):
    return [i for i in lst if i != 0]

def play_ticking(duration):
    pygame.mixer.init()
    tick = pygame.mixer.Sound("tick.wav")
    fast_tick = pygame.mixer.Sound("tick_fast.wav")
    start = time.time()

    while time.time() - start < duration:
        if button_pressed:
            break
        remaining = duration - (time.time() - start)
        if remaining > 2:
            ch = tick.play()
            time.sleep(1)
        else:
            ch = fast_tick.play()
            time.sleep(0.3)

        if button_pressed and ch:
            ch.stop()
            break

def roundStart(players, roundTime, bigrams_dict, trigrams_dict, useTrigrams):
    if useTrigrams:
        random_ngram = random.choice(trigrams_dict["top_300_trigrams"])
        print(f"Using TRIGRAM: '{random_ngram}'")
    else:
        random_ngram = random.choice(bigrams_dict["top_300_bigrams"])
        print(f"Using BIGRAM: '{random_ngram}'")

    combined_img = create_letter_image(random_ngram)
    if combined_img:
        display_img(combined_img)
    else:
        display_clear()

    turnsLeft = len(players)
    print("Turns this round:", turnsLeft)

    for i in range(len(players)):
        tick_thread = threading.Thread(target=play_ticking, args=(roundTime,), daemon=True)
        tick_thread.start()
        interrupted = wait_with_timeout(roundTime)
        if interrupted:
            print("Timer interrupted by button press!")
            turnsLeft -= 1
            print("Turns left:", turnsLeft)
            print("Lives:", players)
        else:
            print("Timer expired! No interruption detected.")
            players[i] -= 1
            turnsLeft -= 1
            print("Turns left:", turnsLeft)
            print("Lives:", players)

    if turnsLeft == 0:
        print("Done with this round.")

    return players

def gameStart(playerCount, roundTime, lives):
    players = [lives] * playerCount
    baseRoundTime = roundTime
    loss_threshold = 0.6

    while len([p for p in players if p != 0]) > 1:
        players_remaining = len([p for p in players if p != 0])
        players_lost = playerCount - players_remaining
        loss_ratio = players_lost / playerCount

        useTrigrams = (loss_ratio >= loss_threshold) or (players_remaining == 3)
        currentRoundTime = baseRoundTime * (players_remaining / playerCount)

        print(f"Starting a round with {players_remaining} players remaining!")
        print(f"Loss ratio: {round(loss_ratio*100,1)}% lost")
        print(f"Round timer is now {round(currentRoundTime,2)}s.\n")

        if useTrigrams:
            print("Switching to TRIGRAM images!\n")
        else:
            print("Using BIGRAM images.\n")

        players = roundStart(players, currentRoundTime, bigrams, trigrams, useTrigrams)
        players = lifeLogic(players)

    survivors = [p for p in players if p != 0]
    if len(survivors) == 1:
        print(f"\nGame Over! One player remains with {survivors[0]} lives.")
    else:
        print("\nGame Over! No players remain.")

    display_clear()
    send_command([0xAE])

    show_end_options()

###############################################################################
# BUTTON-BASED WAIT FUNCTION
###############################################################################
def wait_with_timeout(timeout):
    global button_pressed
    button_pressed = False

    print(f"Press the button within {timeout}s to interrupt (or wait to let time expire).")
    start_time = time.time()

    while (time.time() - start_time) < timeout:
        if button_pressed:
            return True
        time.sleep(0.05)

    return False

###############################################################################
# MAIN ENTRY POINT
###############################################################################
if __name__ == "__main__":
    try:
        playerCount = int(sys.argv[1]) if len(sys.argv) > 1 else 5
        roundTime = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        lives = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        gameStart(playerCount=playerCount, roundTime=roundTime, lives=lives)
    except Exception as e:
        print("Cause of exit:", e)
    finally:
        time.sleep(1)
        spi.close()
        GPIO.cleanup()
