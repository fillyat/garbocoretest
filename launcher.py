# launcher.py
import time
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
import subprocess

# SH1106 DISPLAY SETUP (same as cbreak.py)
import spidev

display_width = 128
display_height = 64

# GPIO Mappings
KEY_LEFT = 17   # A = Left / -
KEY_SELECT = 27 # B = Select / Progress
KEY_RIGHT = 22  # C = Right / +

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(KEY_LEFT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_RIGHT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# SH1106 Display Pins (BCM)
A0 = 25
RESN = 24
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
    # Invert image colors
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
    blank_img = Image.new('1', (128, 64), 0)  # Inverted: fill with black
    display_img(blank_img)

def wait_for_key(keys):
    while True:
        if GPIO.input(KEY_LEFT) == GPIO.LOW and 'left' in keys:
            return 'left'
        elif GPIO.input(KEY_SELECT) == GPIO.LOW and 'select' in keys:
            return 'select'
        elif GPIO.input(KEY_RIGHT) == GPIO.LOW and 'right' in keys:
            return 'right'
        time.sleep(0.1)

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
except:
    font = ImageFont.load_default()

def draw_text_centered(text_top, text_bottom=""):
    img = Image.new("1", (display_width, display_height), 0)  # Inverted: start with black
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
speed_index = 1  # Default: Medium

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
