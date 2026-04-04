import tkinter as tk
import sys

def show_popup(message):
    root = tk.Tk()
    root.title("Red Team says hi!")
    root.geometry("400x200")  # Set the size of the window

    label = tk.Label(root, text=message, font=("Helvetica", 16), wraplength=360)
    label.pack(pady=20)

    # Function to close the window
    def close_window():
        root.destroy()

    # Create a button to close the window
    close_button = tk.Button(root, text="Close", command=close_window)
    close_button.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        message = sys.argv[1]
    else:
        message = "I forgot to pass an argument but I'm sure it would've been smth funny so feel free to chuckle regardless."
    show_popup(message)