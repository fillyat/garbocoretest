import os
import sys
import time
import subprocess
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
import spidev
import tty
import termios

# -----------------------------------------------------------------------------
# Display and SPI setup for the OLED (SH1106)
# -----------------------------------------------------------------------------
A0 = 25
RESN = 24
GPIO.setmode(GPIO.BCM)
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
    image = image.convert('1').resize((128, 64))
    # Invert image so that text (white) appears correctly.
    image = Image.eval(image, lambda x: 255 - x)
    data = [[] for _ in range(8)]
    for page in range(8):
        for col in range(128):
            byte = 0
            for bit in range(8):
                pixel = image.getpixel((col, page * 8 + bit))
                byte |= ((0 if pixel else 1) << bit)
            data[page].append(byte)
    send_command([0xAF])
    for page in range(8):
        send_command([0xB0 + page, 0x02, 0x10])
        GPIO.output(A0, 1)
        spi.xfer(data[page])

def display_clear():
    display_img(Image.new('1', (128, 64), 0))

def draw_centered(text_top, text_bottom=""):
    """Draws the provided text lines centered on the OLED display."""
    img = Image.new("1", (128, 64), 0)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except:
        font = ImageFont.load_default()
    # Compute centering for the top text
    bbox1 = draw.textbbox((0, 0), text_top, font=font)
    text_width1 = bbox1[2] - bbox1[0]
    x1 = (128 - text_width1) // 2
    draw.text((x1, 10), text_top, font=font, fill=255)
    # And for the bottom text if provided.
    if text_bottom:
        bbox2 = draw.textbbox((0, 0), text_bottom, font=font)
        text_width2 = bbox2[2] - bbox2[0]
        x2 = (128 - text_width2) // 2
        draw.text((x2, 35), text_bottom, font=font, fill=255)
    display_img(img)

# -----------------------------------------------------------------------------
# Keyboard input functions
# -----------------------------------------------------------------------------
def getkey():
    """
    Reads one character from standard input without waiting for Enter.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def wait_for_button(options):
    """
    Waits for a key press from the keyboard. Allowed keys are specified in the
    options list (e.g., ["A", "B", "C"]). This launcher uses:
      - A: Left/Decrease (or "back" for menu navigation)
      - B: Select
      - C: Right/Increase
    """
    while True:
        key = getkey().upper()
        if key in options:
            time.sleep(0.3)
            return key

# -----------------------------------------------------------------------------
# Launcher menu for setting options and post‑game selections
# -----------------------------------------------------------------------------
def menu_loop():
    """
    Display the options menu for:
      1. Round Speed: Uses "Slow", "Medium", "Fast" (internally mapped to seconds)
      2. Number of Players
      3. Number of Lives per player
    Uses A (decrease), B (select), C (increase) for selection.
    """
    speeds = ["Slow", "Medium", "Fast"]
    speed_values = {"Slow":15, "Medium":10, "Fast":5}  # e.g., these set the round time
    speed_index = 1
    players = 2
    lives = 3

    # Menu 1: Round Speed
    while True:
        draw_centered("Round Speed", speeds[speed_index])
        key = wait_for_button(["A", "B", "C"])
        if key == "A":
            speed_index = (speed_index - 1) % len(speeds)
        elif key == "C":
            speed_index = (speed_index + 1) % len(speeds)
        elif key == "B":
            break

    # Menu 2: Number of Players
    while True:
        draw_centered("Players", str(players))
        key = wait_for_button(["A", "B", "C"])
        if key == "A" and players > 1:
            players -= 1
        elif key == "C" and players < 10:
            players += 1
        elif key == "B":
            break

    # Menu 3: Number of Lives
    while True:
        draw_centered("Lives", str(lives))
        key = wait_for_button(["A", "B", "C"])
        if key == "A" and lives > 1:
            lives -= 1
        elif key == "C" and lives < 9:
            lives += 1
        elif key == "B":
            break

    return players, speed_values[speeds[speed_index]], lives

def post_game_menu():
    """
    After the game finishes, display a menu with three options:
      - A: Play again with the same settings.
      - B: Go back to the options menu.
      - C: Shut down the Raspberry Pi.
    """
    draw_centered("Game Over", "A: Again B: Menu C: Off")
    key = wait_for_button(["A", "B", "C"])
    return key

# -----------------------------------------------------------------------------
# Main launcher logic
# -----------------------------------------------------------------------------
def main():
    try:
        # First, choose game settings via the options menu.
        settings = menu_loop()
        while True:
            # Run the game as a separate process.
            subprocess.run(["python3", "1G.py",
                            str(settings[0]), str(settings[1]), str(settings[2])])
            # When the game finishes, show the post-game menu.
            key = post_game_menu()
            if key == "A":
                # Run the game again with the same settings.
                subprocess.run(["python3", "1G.py",
                                str(settings[0]), str(settings[1]), str(settings[2])])
            elif key == "B":
                # Go back to the options menu and pick new settings.
                settings = menu_loop()
            elif key == "C":
                # Shut down the Raspberry Pi.
                display_clear()
                send_command([0xAE])
                spi.close()
                GPIO.cleanup()
                os.system("sudo halt")
                break
    except Exception as e:
        print("Launcher crashed:", e)
        GPIO.cleanup()

if __name__ == '__main__':
    main()
