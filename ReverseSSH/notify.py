import tkinter as tk
import sys
import random

def create_popup(root, message):
    popup = tk.Toplevel(root)
    popup.title("Red Team says hi!")
    popup.attributes("-topmost", True)

    # Disable close button
    popup.protocol("WM_DELETE_WINDOW", lambda: None)

    # Window size
    window_width = 400
    window_height = 200

    # Screen size
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()

    # Random position
    x = random.randint(0, screen_width - window_width)
    y = random.randint(0, screen_height - window_height)

    popup.geometry(f"{window_width}x{window_height}+{x}+{y}")

    label = tk.Label(popup, text=message, font=("Helvetica", 16), wraplength=360)
    label.pack(pady=20)

    close_button = tk.Button(popup, text="Close")
    close_button.pack(pady=10)


def show_popups(message):
    root = tk.Tk()
    root.attributes("-toolwindow", True)
    root.withdraw()  # hide main window

    # Random number of popups (1–5)
    num_popups = random.randint(1, 5)

    for _ in range(num_popups):
        create_popup(root, message)

    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        message = sys.argv[1]
    else:
        message = "I forgot to pass an argument but I'm sure it would've been funny."

    show_popups(message)