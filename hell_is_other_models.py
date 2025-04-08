import os
import sys
import time
import subprocess
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
import spidev
import tty
import termios

# Use keyboard mode exclusively.
KEYBOARD_MODE = True

# SH1106 Setup
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
    image = Image.eval(image, lambda x: 255 - x)
    data = [[] for _ in range(8)]
    for page in range(8):
        for col in range(128):
            byte = 0x00
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
    from PIL import Image
    display_img(Image.new('1', (128, 64), 0))

def draw_centered(text_top, text_bottom=""):
    img = Image.new("1", (128, 64), 0)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except:
        font = ImageFont.load_default()
    # Compute text widths and center the texts.
    bbox1 = draw.textbbox((0, 0), text_top, font=font)
    text_width1 = bbox1[2] - bbox1[0]
    x1 = (128 - text_width1) // 2
    draw.text((x1, 10), text_top, font=font, fill=255)
    if text_bottom:
        bbox2 = draw.textbbox((0, 0), text_bottom, font=font)
        text_width2 = bbox2[2] - bbox2[0]
        x2 = (128 - text_width2) // 2
        draw.text((x2, 35), text_bottom, font=font, fill=255)
    display_img(img)

def getkey():
    """
    Read a single character from standard input without waiting for Enter.
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
    Listen for a key press from the keyboard. Only 'A', 'B', or 'C' (case-insensitive) are accepted.
    A maps to left (decrease), B to select, and C to right (increase).
    """
    if KEYBOARD_MODE:
        while True:
            key = getkey().upper()
            if key in options:
                time.sleep(0.3)
                return key
    else:
        BUTTONS = {"A": 17, "B": 27, "C": 22}
        for pin in BUTTONS.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        while True:
            for label, pin in BUTTONS.items():
                if GPIO.input(pin) == GPIO.LOW:
                    if label in options:
                        time.sleep(0.3)
                        return label
            time.sleep(0.05)

def menu_loop():
    speeds = ["Slow", "Medium", "Fast"]
    speed_values = {"Slow": 15, "Medium": 10, "Fast": 5}
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

    # Menu 2: Player Count
    while True:
        draw_centered("Players", str(players))
        key = wait_for_button(["A", "B", "C"])
        if key == "A" and players > 1:
            players -= 1
        elif key == "C" and players < 10:
            players += 1
        elif key == "B":
            break

    # Menu 3: Lives
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
    draw_centered("Game Over", "A: Again  B: Menu  C: Off")
    return wait_for_button(["A", "B", "C"])

if __name__ == '__main__':
    try:
        while True:
            settings = menu_loop()
            subprocess.run(["python3", "nugame.py", *map(str, settings)])
            action = post_game_menu()
            if action == "A":
                subprocess.run(["python3", "nugame.py", *map(str, settings)])
            elif action == "B":
                continue  # re-loop to main menu
            elif action == "C":
                display_clear()
                send_command([0xAE])
                spi.close()
                GPIO.cleanup()
                os.system("sudo halt")
                break
    except Exception as e:
        print("Launcher crashed:", e)
        GPIO.cleanup()
