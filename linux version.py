import time
import json
import random
import msvcrt
from PIL import Image, ImageTk
import tkinter as tk

biFilePath = "C:/Users/ethan/Downloads/top_300_bigrams.json"
triFilePath = "C:/Users/ethan/Downloads/top_300_trigrams.json"

# Load JSON bigrams and trigrams as before
with open(biFilePath, 'r') as file:
    bigrams = json.load(file)

with open(triFilePath, 'r') as file:
    trigrams = json.load(file)

##############  1) Dictionary of Letter -> Image Path ##############
# You must fill this in with valid paths on your system for each letter.
# Example: "A.png", "B.png", etc. (You can also do lowercase if you prefer.)
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

# ---------------------------------------------------------------------
#  3) HELPER: CREATE A COMBINED IMAGE FROM A STRING (E.G. "HE")
# ---------------------------------------------------------------------
def create_letter_image(ngram):
    """
    Takes a string (e.g. "he" or "the"), opens each letter's image,
    and concatenates them side by side into a single PIL image.
    Returns the combined image, or None if no letters were valid.
    """
    letter_imgs = []
    for ch in ngram:
        upper_char = ch.upper()  # if your letter_image_paths are uppercase
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
    combined = Image.new("RGBA", (total_width, max_height))

    # Paste each letter
    x_offset = 0
    for img in letter_imgs:
        combined.paste(img, (x_offset, 0))
        x_offset += img.width

    return combined

# ---------------------------------------------------------------------
#  4) NON-BLOCKING TIMER USING CONSOLE KEYSTROKE (MSVCRT) + TK UPDATE
# ---------------------------------------------------------------------
def timer_with_keystroke_interrupt_nonblocking(timeout, window=None):
    """
    Waits up to `timeout` seconds. If a key is pressed in the console,
    returns True immediately. Else returns False after time expires.
    We call window.update() so tkinter remains responsive.
    """
    end_time = time.time() + timeout
    print(f"Press any key within {round(timeout,2)}s to interrupt...")

    while time.time() < end_time:
        if window:
            window.update()  # keep tkinter GUI alive

        # Check for console keystroke
        if msvcrt.kbhit():
            msvcrt.getch()  # clear buffer
            return True

        time.sleep(0.1)

    return False

# ---------------------------------------------------------------------
#  5) LIFE LOGIC: REMOVE DEAD PLAYERS
# ---------------------------------------------------------------------
def lifeLogic(lst):
    """
    Returns a new list with players who have > 0 lives.
    """
    return [i for i in lst if i != 0]

# ---------------------------------------------------------------------
#  6) ROUND LOGIC
# ---------------------------------------------------------------------
def roundStart(players, roundTime, bigrams_dict, trigrams_dict, useTrigrams,
               window, label):
    """
    Performs one round:
      - Picks a random n-gram (bigram or trigram).
      - Updates the single tkinter label to show the letter images.
      - For each player, runs a timer that can be interrupted by a console key.
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
        # Convert to PhotoImage and display in label
        tk_img = ImageTk.PhotoImage(combined_img)
        label.config(image=tk_img, text="")
        label.image = tk_img  # keep ref to avoid GC
    else:
        # If no valid letters found, clear label
        label.config(image="", text=f"No valid images for '{random_ngram}'")

    turnsLeft = len(players)
    print("Turns this round:", turnsLeft)

    # For each player, run the interruptible timer
    for i in range(len(players)):
        interrupted = timer_with_keystroke_interrupt_nonblocking(roundTime, window)
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

# ---------------------------------------------------------------------
#  7) MAIN GAME LOOP
# ---------------------------------------------------------------------
def gameStart(playerCount, roundTime, lives):
    """
    Creates one tkinter window (secondary display) that stays open.
    - Each round, we update the label with the chosen bigram/trigram letters.
    - Timer speeds up as players are knocked out.
    - We switch to trigrams once a certain fraction of players is lost.
    - We check for console keypress to interrupt each player's turn.
    """

    # 1) Create a single, persistent tkinter window
    window = tk.Tk()
    window.title("Secondary Display")
    # Keep window on top if you want it always visible
    window.attributes("-topmost", True)

    # Label to show the letter images
    display_label = tk.Label(window, text="Starting soon...")
    display_label.pack()

    # 2) Initialize players
    players = [lives] * playerCount
    baseRoundTime = roundTime

    # For example, switch to trigrams after 50% of players are knocked out
    loss_threshold = 0.6

    # 3) Repeat rounds until only 1 player remains
    while len([p for p in players if p != 0]) > 1:
        # Count how many are still alive
        players_remaining = len([p for p in players if p != 0])
        players_lost = playerCount - players_remaining
        loss_ratio = players_lost / playerCount

        # Decide if we should use trigrams or still use bigrams
        useTrigrams = (loss_ratio >= loss_threshold) | players_remaining == 3

        # Speed up round time as players get eliminated
        currentRoundTime = baseRoundTime * (players_remaining / playerCount)

        print(f"Starting a round with {players_remaining} players remaining!")
        print(f"Loss ratio: {round(loss_ratio*100,1)}% lost")
        print(f"Round timer is now {round(currentRoundTime,2)}s.\n")

        if useTrigrams:
            print("Switching to TRIGRAM images!\n")
        else:
            print("Using BIGRAM images.\n")

        # 4) Run one round
        players = roundStart(players,
                             currentRoundTime,
                             bigrams,
                             trigrams,
                             useTrigrams,
                             window,
                             display_label)

        # Remove players at 0
        players = lifeLogic(players)

    # 5) Game Over
    survivors = [p for p in players if p != 0]
    if len(survivors) == 1:
        print(f"\nGame Over! One player remains with {survivors[0]} lives.")
    else:
        print("\nGame Over! No players remain.")

    print("Press Enter in the console to close the secondary display...")
    input()  # Wait for user input so we can see the last screen
    window.destroy()

# Start the game
gameStart(5, 5, 3)