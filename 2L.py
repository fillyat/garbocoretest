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
spi.max_speed_hz = 1_000_000
spi.mode = 0b00

# -----------------------------------------------------------------------------
# Helpers to hand the OLED pins/SPI bus to the child process and reclaim them
# -----------------------------------------------------------------------------

def release_display_gpio():
    """Free A0, RESN and the SPI handle so another process can own them."""
    spi.close()
    GPIO.cleanup((A0, RESN))


def init_display_gpio():
    """Re‑initialise A0, RESN and the SPI handle after the game returns."""
    global spi
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(A0, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(RESN, GPIO.OUT, initial=GPIO.HIGH)

    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 1_000_000
    spi.mode = 0b00


def run_game(settings):
    """Run 2G.py with the given settings, handing GPIO ownership to it."""
    release_display_gpio()
    subprocess.run([
        "python3",
        "2G.py",
        str(settings[0]),
        str(settings[1]),
        str(settings[2]),
    ])
    init_display_gpio()

# -----------------------------------------------------------------------------
# OLED drawing helpers (unchanged)
# -----------------------------------------------------------------------------

def send_command(cmd_list):
    GPIO.output(A0, 0)
    spi.xfer(cmd_list)


def display_img(image):
    image = image.convert("1").resize((128, 64))
    # Invert so white text appears correctly
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
    display_img(Image.new("1", (128, 64), 0))


def draw_centered(text_top, text_bottom=""):
    img = Image.new("1", (128, 64), 0)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14
        )
    except Exception:
        font = ImageFont.load_default()

    bbox1 = draw.textbbox((0, 0), text_top, font=font)
    x1 = (128 - (bbox1[2] - bbox1[0])) // 2
    draw.text((x1, 10), text_top, font=font, fill=255)

    if text_bottom:
        bbox2 = draw.textbbox((0, 0), text_bottom, font=font)
        x2 = (128 - (bbox2[2] - bbox2[0])) // 2
        draw.text((x2, 35), text_bottom, font=font, fill=255)

    display_img(img)

# -----------------------------------------------------------------------------
# Keyboard helpers (unchanged)
# -----------------------------------------------------------------------------

def getkey():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def wait_for_button(options):
    while True:
        key = getkey().upper()
        if key in options:
            time.sleep(0.3)
            return key

# -----------------------------------------------------------------------------
# Menus (unchanged logic)
# -----------------------------------------------------------------------------

def menu_loop():
    speeds = ["Slow", "Medium", "Fast"]
    speed_values = {"Slow": 15, "Medium": 10, "Fast": 5}
    speed_index = 1
    players = 2
    lives = 3

    # Round Speed
    while True:
        draw_centered("Round Speed", speeds[speed_index])
        key = wait_for_button(["A", "B", "C"])
        if key == "A":
            speed_index = (speed_index - 1) % len(speeds)
        elif key == "C":
            speed_index = (speed_index + 1) % len(speeds)
        elif key == "B":
            break

    # Players
    while True:
        draw_centered("Players", str(players))
        key = wait_for_button(["A", "B", "C"])
        if key == "A" and players > 1:
            players -= 1
        elif key == "C" and players < 10:
            players += 1
        elif key == "B":
            break

    # Lives
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
    draw_centered("Game Over", "A: Again B: Menu C: Off")
    return wait_for_button(["A", "B", "C"])

# -----------------------------------------------------------------------------
# Main launcher logic (now calls run_game)
# -----------------------------------------------------------------------------

def main():
    try:
        settings = menu_loop()
        while True:
            run_game(settings)
            key = post_game_menu()
            if key == "A":
                run_game(settings)
            elif key == "B":
                settings = menu_loop()
            elif key == "C":
                display_clear()
                send_command([0xAE])  # OLED off
                spi.close()
                GPIO.cleanup()
                os.system("sudo halt")
                break
    except Exception as e:
        print("Launcher crashed:", e)
        GPIO.cleanup()


if __name__ == "__main__":
    main()


