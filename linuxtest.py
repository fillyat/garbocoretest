#-*- coding: utf-8 -*-
import time
import json
import random
import sys
import spidev
import RPi.GPIO as GPIO
from PIL import Image, ImageTk  # PIL used for image manipulation; ImageTk won't be used now
# from PIL import ImageDraw  # If you need to test or modify images programmatically

###############################################################################
# SH1106 1.3" SPI Display Setup
###############################################################################

# Setup RPi GPIO
GPIO.setmode(GPIO.BOARD)
A0 = 22    # GPIO pin for A0 pin : 0 -> command; 1 -> display data RAM
RESN = 18  # GPIO pin for display reset (active low)
GPIO.setup(A0, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(RESN, GPIO.OUT, initial=GPIO.HIGH)

# Setup SPI
spi = spidev.SpiDev()
spi.open(0, 0)           # bus=0, device=0
spi.max_speed_hz = 1000000
spi.mode = 0b00

def display_img(image):
    """
    Sends a 128×64, 1-bit PIL image to the SH1106.
    This function slices the image in 8 horizontal bands of 8 pixels high.
    """
    data_slice = [[], [], [], [], [], [], [], []]
    # A0=0 => command mode
    GPIO.output(A0, 0)

    # Convert to 1-bit if not already
    if image.mode != '1':
        image = image.convert('1')

    # The display is 128x64, so ensure we are 128 wide and 64 high
    # If your letter collage is smaller/larger, you can resize or paste it onto a 128×64 background
    if image.size != (128, 64):
        image = image.resize((128, 64))

    # Build the data in 8 horizontal pages
    for p in range(8):  # 8 pages (0–7), each page is 8 pixels high
        data_set = []
        for c in range(128):
            by = 0x00
            for b in range(8):
                # The SH1106 expects each byte to represent 8 vertical pixels (LSB at the top).
                # Here, we'll build up that byte from the image.
                pixel = image.getpixel((c, p * 8 + b))  # returns 0 or 255 in '1' mode
                bit_val = 0 if pixel == 255 else 1   # invert if needed, or keep 0/1 logic
                # Shift and add bits. LSB is the top pixel in the byte.
                by = by | (bit_val << b)
            data_set.append(by)
        data_slice[p] = data_set

    # Turn display ON (0xAF)
    spi.xfer([0xAF])

    # Send each 8-pixel-high page
    for p in range(8):
        GPIO.output(A0, 0)
        # Set page address + column address
        # The typical command sequence for SH1106 horizontal addressing is:
        spi.xfer([0xB0 + p, 0x02, 0x10])  # set page address, then lower and higher column
        GPIO.output(A0, 1)
        # Transfer the entire row (128 bytes)
        spi.xfer(data_slice[p])

def display_clear():
    """
    Clears the display by sending a blank (all 0s) 128x64 page.
    """
    blank_img = Image.new('1', (128, 64), color=1)  # White or black as needed
    display_img(blank_img)

# Perform a hardware reset on the display
GPIO.output(RESN, 0)
time.sleep(0.1)
GPIO.output(RESN, 1)
time.sleep(0.1)

###############################################################################
# The N-gram game logic
###############################################################################

# For demonstration, we assume your bigrams/trigrams JSON files live at:
biFilePath = "top_300_bigrams.json"
triFilePath = "top_300_trigrams.json"

with open(biFilePath, 'r') as file:
    bigrams = json.load(file)

with open(triFilePath, 'r') as file:
    trigrams = json.load(file)

# Dictionary of Letter -> Image Path
# Make sure these letter images exist, and are the correct size or scaleable
letter_image_paths = {
    "A": "/letters/A.jpg",
    "B": "/letters/B.jpg",
    "C": "/letters/C.jpg",
    "D": "/letters/D.jpg",
    "E": "/letters/E.jpg",
    "F": "/letters/F.jpg",
    "G": "/letters/G.jpg",
    "H": "/letters/H.jpg",
    "I": "/letters/I.jpg",
    "J": "/letters/J.jpg",
    "K": "/letters/K.jpg",
    "L": "/letters/L.jpg",
    "M": "/letters/M.jpg",
    "N": "/letters/N.jpg",
    "O": "/letters/O.jpg",
    "P": "/letters/P.jpg",
    "Q": "/letters/Q.jpg",
    "R": "/letters/R.jpg",
    "S": "/letters/S.jpg",
    "T": "/letters/T.jpg",
    "U": "/letters/U.jpg",
    "V": "/letters/V.jpg",
    "W": "/letters/W.jpg",
    "X": "/letters/X.jpg",
    "Y": "/letters/Y.jpg",
    "Z": "/letters/Z.jpg",
    # etc. for punctuation if needed
}

def create_letter_image(ngram):
    """
    Takes a string (e.g. "he" or "the"), opens each letter's image,
    and concatenates them side by side into a single PIL image (RGBA).
    Returns the combined image, or None if no letters were valid.
    """
    letter_imgs = []
    for ch in ngram:
        upper_char = ch.upper()
        if upper_char in letter_image_paths:
            img_path = letter_image_paths[upper_char]
            letter_imgs.append(Image.open(img_path))
        else:
            print(f"No image mapped for '{ch}' (skipping).")

    if not letter_imgs:
        return None

    # Figure out total width & max height
    total_width = sum(img.width for img in letter_imgs)
    max_height = max(img.height for img in letter_imgs)

    # Create a new blank image
    combined = Image.new("RGBA", (total_width, max_height), (255,255,255,0))

    # Paste each letter
    x_offset = 0
    for img in letter_imgs:
        combined.paste(img, (x_offset, 0))
        x_offset += img.width

    return combined

def lifeLogic(lst):
    """
    Returns a new list with players who have > 0 lives.
    """
    return [i for i in lst if i != 0]

def roundStart(players, roundTime, bigrams_dict, trigrams_dict, useTrigrams):
    """
    Performs one round:
      - Picks a random n-gram (bigram or trigram).
      - Creates an image for it, sends to the SH1106 display.
      - For each player, waits roundTime seconds or until user hits Enter.
    """
    # Pick random bigram or trigram text
    if useTrigrams:
        random_ngram = random.choice(trigrams_dict["top_300_trigrams"])
        print(f"Using TRIGRAM: '{random_ngram}'")
    else:
        random_ngram = random.choice(bigrams_dict["top_300_bigrams"])
        print(f"Using BIGRAM: '{random_ngram}'")

    # Create a combined image from letters
    combined_img = create_letter_image(random_ngram)
    if combined_img is not None:
        # Convert to 1-bit, scale to 128×64, and show on display
        # (display_img() will handle any final conversion/resize, but we can do it here if we want)
        display_img(combined_img)
    else:
        # If no valid letters found, clear display or show an error message
        print(f"No valid images for '{random_ngram}'")
        display_clear()

    turnsLeft = len(players)
    print("Turns this round:", turnsLeft)

    # For each player, do a waiting period
    for i in range(len(players)):
        interrupted = wait_with_timeout(roundTime)
        if interrupted:
            print("Timer interrupted by your key press!")
            turnsLeft -= 1
            print("Turns left:", turnsLeft)
            print("Lives:", players)
        else:
            print("Timer expired! No interruption detected.")
            players[i] = players[i] - 1
            turnsLeft -= 1
            print("Turns left:", turnsLeft)
            print("Lives:", players)

    if turnsLeft == 0:
        print("Done with this round.")

    return players

def wait_with_timeout(timeout):
    """
    A simplified approach to wait up to `timeout` seconds or until the user presses Enter.
    Returns True if the user pressed Enter, or False if time expired.
    
    NOTE: This is a blocking approach that will work in a basic console environment on the Pi.
    If you want a truly non-blocking approach, you'll need something more advanced 
    (e.g., a separate thread or select-based I/O).
    """
    print(f"Press Enter within {timeout}s to interrupt (or wait to let time expire).")
    start_time = time.time()

    # We'll poll for input once every 0.1s
    while (time.time() - start_time) < timeout:
        # Because default input() in Python blocks, we'll do a quick check 
        # with sys.stdin and see if there's input available:
        import select
        rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
        if rlist:
            line = sys.stdin.readline()
            if line.strip() != "":
                # user pressed Enter
                return True
    return False

def gameStart(playerCount, roundTime, lives):
    """
    Main game loop:
      - Repeats rounds until only 1 player remains.
      - Switches to trigrams after a certain fraction of players is lost.
      - Speed up round time as players get eliminated.
    """
    players = [lives] * playerCount
    baseRoundTime = roundTime

    # For example, switch to trigrams after 60% of players are knocked out
    loss_threshold = 0.6

    while len([p for p in players if p != 0]) > 1:
        # Count how many are still alive
        players_remaining = len([p for p in players if p != 0])
        players_lost = playerCount - players_remaining
        loss_ratio = players_lost / playerCount

        # Decide if we should use trigrams or still use bigrams
        useTrigrams = (loss_ratio >= loss_threshold) or (players_remaining == 3)

        # Speed up round time as players get eliminated
        currentRoundTime = baseRoundTime * (players_remaining / playerCount)

        print(f"Starting a round with {players_remaining} players remaining!")
        print(f"Loss ratio: {round(loss_ratio*100,1)}% lost")
        print(f"Round timer is now {round(currentRoundTime,2)}s.\n")

        if useTrigrams:
            print("Switching to TRIGRAM images!\n")
        else:
            print("Using BIGRAM images.\n")

        # Run one round
        players = roundStart(players,
                             currentRoundTime,
                             bigrams,
                             trigrams,
                             useTrigrams)

        # Remove players at 0
        players = lifeLogic(players)

    # Game Over
    survivors = [p for p in players if p != 0]
    if len(survivors) == 1:
        print(f"\nGame Over! One player remains with {survivors[0]} lives.")
    else:
        print("\nGame Over! No players remain.")

    # Clear display and close
    display_clear()
    print("Press Enter in the console to end.")
    input()

###############################################################################
# START THE GAME
###############################################################################

if __name__ == "__main__":
    try:
        gameStart(5, 5, 3)
    except:
        print("Cause of exit:", sys.exc_info())
    finally:
        spi.close()
        GPIO.cleanup()
