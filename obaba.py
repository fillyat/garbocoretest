# cbreak.py
# -*- coding: utf-8 -*-
"""
Combined N-gram Game + SH1106 Display on Raspberry Pi,
with cbreak-based immediate 'O' key interrupt.
"""

import os
import sys
import time
import json
import random
import spidev
import RPi.GPIO as GPIO
from PIL import Image

# For cbreak-based input
import termios
import tty
import select

###############################################################################
# SH1106 / SPI DISPLAY SETUP
###############################################################################
GPIO.setmode(GPIO.BOARD)

# Pin assignments (adjust if needed)
A0   = 22  # GPIO pin for A0 pin : 0 -> command; 1 -> display data RAM
RESN = 18  # GPIO pin for display reset (active low)

GPIO.setup(A0, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(RESN, GPIO.OUT, initial=GPIO.HIGH)

# Initialize SPI interface
spi = spidev.SpiDev()
spi.open(0, 0)            # bus=0, device=0
spi.max_speed_hz = 1000000
spi.mode = 0b00

def send_command(cmd_list):
    """
    Helper to send one or more command bytes with A0=0.
    """
    GPIO.output(A0, 0)
    spi.xfer(cmd_list)

def display_img(image):
    """
    Sends a 128×64, 1-bit PIL image to the SH1106.
    Slices the image into 8 horizontal pages (each 8 pixels tall).
    """
    data_slice = [[] for _ in range(8)]

    # Convert to 1-bit if not already
    if image.mode != '1':
        image = image.convert('1')

    # Ensure the image is 128×64
    if image.size != (128, 64):
        image = image.resize((128, 64))

    # Build the data in 8 pages of 8 pixels high
    for p in range(8):  # pages 0..7
        data_set = []
        for c in range(128):
            b_byte = 0x00
            for b in range(8):
                pixel = image.getpixel((c, p * 8 + b))
                # If pixel == 255, it's white in 1-bit mode; if 0, it's black.
                # Some displays invert this, but let's keep it simple:
                bit_val = 0 if pixel == 255 else 1
                # LSB is top pixel in each byte
                b_byte |= (bit_val << b)
            data_set.append(b_byte)
        data_slice[p] = data_set

    # Turn display ON
    send_command([0xAF])

    # Write each page
    for p in range(8):
        # Set page address, then lower and higher column addresses
        send_command([0xB0 + p, 0x02, 0x10])
        GPIO.output(A0, 1)
        spi.xfer(data_slice[p])

def display_clear():
    """
    Clears the display (filling with '1' => white in 1-bit mode).
    If your display inverts bits, you might set it to 0 for black.
    """
    blank_img = Image.new('1', (128, 64), 1)  # '1' => all pixels white
    display_img(blank_img)

# Hardware reset
GPIO.output(RESN, 0)
time.sleep(0.1)
GPIO.output(RESN, 1)
time.sleep(0.1)

send_command([0xA7])

###############################################################################
# GAME LOGIC
###############################################################################
# Adjust JSON file paths as needed
biFilePath = "top_300_bigrams.json"
triFilePath = "top_300_trigrams.json"

with open(biFilePath, 'r') as file:
    bigrams = json.load(file)

with open(triFilePath, 'r') as file:
    trigrams = json.load(file)

# Dictionary of letter -> image file paths
# Ensure these paths match the real locations of your images
letter_image_paths = {
    "A": "letters/A.jpg",
    "B": "letters/B.jpg",
    "C": "letters/C.jpg",
    "D": "letters/D.jpg",
    "E": "letters/E.jpg",
    "F": "letters/F.jpg",
    "G": "letters/G.jpg",
    "H": "letters/H.jpg",
    "I": "letters/I.jpg",
    "J": "letters/J.jpg",
    "K": "letters/K.jpg",
    "L": "letters/L.jpg",
    "M": "letters/M.jpg",
    "N": "letters/N.jpg",
    "O": "letters/O.jpg",
    "P": "letters/P.jpg",
    "Q": "letters/Q.jpg",
    "R": "letters/R.jpg",
    "S": "letters/S.jpg",
    "T": "letters/T.jpg",
    "U": "letters/U.jpg",
    "V": "letters/V.jpg",
    "W": "letters/W.jpg",
    "X": "letters/X.jpg",
    "Y": "letters/Y.jpg",
    "Z": "letters/Z.jpg",
}

def create_letter_image(ngram):
    """
    Create a side-by-side letter collage from an n-gram (like "TH" or "THE").
    Returns a PIL.Image in RGBA or None if no valid letters.
    """
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
    """Return new list with players who still have > 0 lives."""
    return [i for i in lst if i != 0]

def roundStart(players, roundTime, bigrams_dict, trigrams_dict, useTrigrams):
    """
    One round:
      - pick a random bigram/trigram
      - build the image, display it
      - each player gets a turn to interrupt or lose a life
    """
    if useTrigrams:
        random_ngram = random.choice(trigrams_dict["top_300_trigrams"])
        print(f"Using TRIGRAM: '{random_ngram}'")
    else:
        random_ngram = random.choice(bigrams_dict["top_300_bigrams"])
        print(f"Using BIGRAM: '{random_ngram}'")

    # Create letter image
    combined_img = create_letter_image(random_ngram)
    if combined_img:
        display_img(combined_img)
    else:
        display_clear()

    turnsLeft = len(players)
    print("Turns this round:", turnsLeft)

    for i in range(len(players)):
        interrupted = wait_with_timeout(roundTime)
        if interrupted:
            print("Timer interrupted by your key press!")
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
    """
    Main game loop. Repeats rounds until only 1 player remains.
    """
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

    # Clear display at the end
    display_clear()
    # Optionally turn it off
    send_command([0xAE])  # 0xAE => Display OFF

    print("Press Enter in the console to end.")
    input()

###############################################################################
# WAIT_WITH_TIMEOUT FIX: IMMEDIATE 'O' KEY INTERRUPT
###############################################################################
def wait_with_timeout(timeout):
    """
    Wait up to `timeout` seconds or until the user presses 'O'.
    Returns True if interrupted, False if time expires.
    
    Uses cbreak mode for immediate single-character reading.
    """
    # We only accept uppercase O for interrupt
    allowed_keys = {'O'}

    print(f"Press 'O' within {timeout}s to interrupt (or wait to let time expire).")
    start_time = time.time()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    tty.setcbreak(fd)  # put terminal into cbreak mode

    try:
        while (time.time() - start_time) < timeout:
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            if rlist:
                ch = sys.stdin.read(1)  # read one character
                if ch in allowed_keys:
                    return True
                # Otherwise ignore the character
        return False
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

###############################################################################
# MAIN ENTRY POINT
###############################################################################
if __name__ == "__main__":
    try:
        gameStart(playerCount=5, roundTime=5, lives=3)
    except Exception as e:
        print("Cause of exit:", e)
    finally:
        # Give a brief pause to see the final display state
        time.sleep(1)
        spi.close()
        GPIO.cleanup()
