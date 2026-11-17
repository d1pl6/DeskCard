"""Anki-style card exercise: show front → reveal back → five self-grade buttons."""

from typing import Any

import tkinter as tk
from tkinter import ttk

WINDOW_SIZE = (650, 700)
WINDOW_MIN = (600, 600)
WINDOW_MARGIN = (60, 100)

class Application:
    def __init__(self, root):
        self.root = root
        root.title("DeskCard - Anki")
        self._fit_window()

    # Header
        self.header = tk.Frame(root, borderwidth=1, relief=tk.GROOVE)
        self.header.pack(fill="x", side="top")
        self.header.rowconfigure(0, weight=1)
        self.header.rowconfigure(1, weight=1)
        self.header.columnconfigure(0, weight=1)
        self.header.columnconfigure(1, weight=3)

        self.header_name = tk.Label(self.header, text="DeskCard - Anki", pady=10, padx=10)
        self.header_name.grid(column=0, row=0, sticky="w")

        self.header_buttons = tk.Frame(self.header, pady=10, padx=10)
        self.header_buttons.grid(column=1, row=0, sticky="e")

        self.header_skip = tk.Button(self.header_buttons, text="Skip", command=self.on_skip)
        self.header_skip.grid(column=0, row=0, padx=10)

        self.header_quit = tk.Button(self.header_buttons, text="Quit", command=self.on_quit)
        self.header_quit.grid(column=1, row=0)

    # Prompt
        self.prompt = tk.Frame(root, borderwidth=1, relief=tk.GROOVE)
        self.prompt.pack(fill="x", pady=5)

        self.prompt_row = tk.Frame(self.prompt)
        self.prompt_row.pack(expand=True)

        self.prompt_text = tk.Label(self.prompt_row, text="Prompt Text")
        self.prompt_text.pack(side="left", padx=5)

        self.prompt_audio = tk.Button(self.prompt_row, text="▶")
        self.prompt_audio.pack(side="left", padx=5)


    # Answer
        self.answer = tk.Frame(root, borderwidth=1, relief=tk.GROOVE)
        self.answer.pack(fill="x", pady=5)

        self.answer_row = tk.Frame(self.answer)

        self.answer_text = tk.Label(self.answer_row, text="Answer Text")

        self.answer_audio = tk.Button(self.answer_row, text="▶")


    # Bottom
        self.bottom = tk.Frame(root, borderwidth=1, relief=tk.GROOVE)
        self.bottom.pack(fill="x", side="bottom")

        self.bottom_button = tk.Button(self.bottom, text="Show Answer", command=self.show_answer)
        self.bottom_button.pack()

        self.bottom_impossible = tk.Button(self.bottom, text="Impossible")
        self.bottom_hard = tk.Button(self.bottom, text="Hard")
        self.bottom_medium = tk.Button(self.bottom, text="Medium")
        self.bottom_easy = tk.Button(self.bottom, text="Easy")

    def show_answer(self):
        self.bottom_button.pack_forget()

        self.answer_row.pack(expand=True)
        self.answer_text.pack(side="left", padx=5, pady=5)
        self.answer_audio.pack(side="left", padx=5, pady=5)

        self.bottom_impossible.pack(expand=True, side="left")
        self.bottom_hard.pack(expand=True, side="left")
        self.bottom_medium.pack(expand=True, side="left")
        self.bottom_easy.pack(expand=True, side="left")


    def _fit_window(self):
        """Size the window to the screen, centre it, and set a sane minimum."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        width = min(WINDOW_SIZE[0], max(WINDOW_MIN[0], screen_w - WINDOW_MARGIN[0]))
        height = min(WINDOW_SIZE[1], max(WINDOW_MIN[1], screen_h - WINDOW_MARGIN[1]))

        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.root.minsize(
            min(WINDOW_MIN[0], width),
            min(WINDOW_MIN[1], height),
        )

    def on_skip(self):
        pass #TODO

    def on_quit(self):
        try:
            self.root.destroy()
        except Exception as e:
            print(f"Couldn't destroy window: {e}")

def main():
    """Create the window and run the app; shared by every entry point."""
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()