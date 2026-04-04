import tkinter as tk

def show_popup():
    root = tk.Tk()
    root.title("Troll Malware Alert")
    root.geometry("400x200")  # Set the size of the window

    label = tk.Label(root, text="You have been infected by a troll malware!", font=("Helvetica", 16))
    label.pack(pady=20)

    # Function to close the window
    def close_window():
        root.destroy()

    # Create a button to close the window
    close_button = tk.Button(root, text="Close", command=close_window)
    close_button.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    show_popup()