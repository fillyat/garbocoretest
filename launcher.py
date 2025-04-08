# launcher.py
import time
import subprocess
from PIL import Image, ImageDraw, ImageFont
import spidev
import sys
import tty
import termios
import select

# Display setup
display_width = 128
display_height = 64

# SH1106 Display Pins (BCM)
import RPi.GPIO as GPIO
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
    data_slice = [[] for _ in range(8)]
    image = image.convert('1')
    image = image.resize((128, 64))
    image = Image.eval(image, lambda x: 255 - x)

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
    blank_img = Image.new('1', (128, 64), 0)
    display_img(blank_img)

def wait_for_key(keys):
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        while True:
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            if rlist:
                ch = sys.stdin.read(1).lower()
                if ch == 'a' and 'left' in keys:
                    return 'left'
                elif ch == 'b' and 'select' in keys:
                    return 'select'
                elif ch == 'c' and 'right' in keys:
                    return 'right'
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
except:
    font = ImageFont.load_default()

def draw_text_centered(text_top, text_bottom=""):
    img = Image.new("1", (display_width, display_height), 0)
    draw = ImageDraw.Draw(img)

    bbox1 = draw.textbbox((0, 0), text_top, font=font)
    w1, h1 = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
    draw.text(((display_width - w1) // 2, 10), text_top, font=font, fill=1)

    if text_bottom:
        bbox2 = draw.textbbox((0, 0), text_bottom, font=font)
        w2, h2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
        draw.text(((display_width - w2) // 2, 30), text_bottom, font=font, fill=1)

    display_img(img)

# Menu 1: Round Speed
speeds = ["Slow", "Medium", "Fast"]
speed_times = {"Slow": 15, "Medium": 10, "Fast": 5}
speed_index = 1

while True:
    draw_text_centered("Round Speed:", speeds[speed_index])
    key = wait_for_key(['left', 'right', 'select'])
    if key == 'left':
        speed_index = (speed_index - 1) % len(speeds)
    elif key == 'right':
        speed_index = (speed_index + 1) % len(speeds)
    elif key == 'select':
        break

# Menu 2: Player Count
player_count = 2

while True:
    draw_text_centered("Player Count:", str(player_count))
    key = wait_for_key(['left', 'right', 'select'])
    if key == 'left' and player_count > 1:
        player_count -= 1
    elif key == 'right' and player_count < 10:
        player_count += 1
    elif key == 'select':
        break

# Menu 3: Player Lives
player_lives = 3

while True:
    draw_text_centered("Player Lives:", str(player_lives))
    key = wait_for_key(['left', 'right', 'select'])
    if key == 'left' and player_lives > 1:
        player_lives -= 1
    elif key == 'right' and player_lives < 9:
        player_lives += 1
    elif key == 'select':
        break

# Final Confirmation Screen
draw_text_centered(f"Start Game", f"{speeds[speed_index]} | {player_count}P | {player_lives}L")
time.sleep(2)

# Run the game with selected parameters
round_time = speed_times[speeds[speed_index]]
subprocess.run(["python3", "nomusic.py", str(player_count), str(round_time), str(player_lives)])

# Cleanup
display_clear()
send_command([0xAE])
spi.close()
GPIO.cleanup()
