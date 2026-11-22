"""App preferences dialog."""

import tkinter as tk
from tkinter import messagebox, ttk

try:
    from ..app_preferences import (
        DEFAULT_PREFERENCES, DEFAULT_SCORE_DELTAS, GRADES, IMAGE_DISPLAY_MODES,
        STATUS_POSITIONS, clear_remembered_files, load_preferences,
        save_preferences,
    )
    from ..errors import SettingsError
    from ..session import normalize_settings
    from .helpers.theme import (
        THEME_ACCENT, THEME_BG, THEME_FG, THEME_FG_DIM,
        THEME_FONT, THEME_FONT_BOLD, THEME_FONT_SMALL, apply_theme, ui,
    )
except ImportError:  # started as a script from src/ui
    from app_preferences import (
        DEFAULT_PREFERENCES, DEFAULT_SCORE_DELTAS, GRADES, IMAGE_DISPLAY_MODES,
        STATUS_POSITIONS, clear_remembered_files, load_preferences,
        save_preferences,
    )
    from src.errors import SettingsError
    from src.session import normalize_settings
    from helpers.theme import (
        THEME_ACCENT, THEME_BG, THEME_FG, THEME_FG_DIM,
        THEME_FONT, THEME_FONT_BOLD, THEME_FONT_SMALL, apply_theme, ui,
    )


def show_preferences(parent):
    """Open the app preferences window and wait until it is closed."""
    preferences = load_preferences()

    window = tk.Toplevel(parent)
    window.title("DeskCard - Preferences")
    window.resizable(False, False)
    window.transient(parent)
    apply_theme(window)

    opacity = tk.IntVar(value=preferences["exercise_opacity"])
    show_skip_quit = tk.IntVar(value=int(preferences["show_skip_quit"]))
    restrict_close = tk.IntVar(value=int(preferences["restrict_exercise_close"]))
    confirm_quit_reset = tk.IntVar(value=int(preferences["confirm_quit_reset"]))
    show_time_passed = tk.IntVar(value=int(preferences["show_time_passed"]))
    show_cards_in_batch = tk.IntVar(value=int(preferences["show_cards_in_batch"]))
    show_session_batches = tk.IntVar(value=int(preferences["show_session_batches"]))
    status_position = tk.StringVar(value=preferences["status_position"])
    remember_geometry = tk.IntVar(value=int(preferences["remember_geometry"]))
    remember_position = tk.IntVar(value=int(preferences["remember_position"]))
    always_on_top = tk.IntVar(value=int(preferences["exercise_always_on_top"]))
    auto_deck = tk.IntVar(value=int(preferences["auto_load_last_deck"]))
    auto_settings = tk.IntVar(value=int(preferences["auto_load_last_settings"]))
    image_mode = tk.StringVar(value=preferences["image_display_mode"])
    max_width = tk.StringVar(value=str(preferences["max_image_width"]))
    max_height = tk.StringVar(value=str(preferences["max_image_height"]))
    font_scale = tk.IntVar(value=preferences["font_scale"])
    debug_log = tk.IntVar(value=int(preferences["enable_debug_log"]))
    count_all_directions = tk.IntVar(value=int(preferences["count_all_directions"]))
    default_global_vars = {
        key: tk.StringVar(value=preferences["default_global_settings"][key])
        for key in ("delay", "session", "batch", "jitter")
    }
    last_deck_text = tk.StringVar(value=preferences.get("last_deck") or "(none)")
    last_settings_text = tk.StringVar(value=preferences.get("last_settings") or "(none)")
    recent_decks_text = tk.StringVar(
        value=f"{len(preferences.get('recent_decks', []))} deck(s)")
    score_vars = {
        grade: tk.IntVar(value=preferences["score_deltas"][grade])
        for grade in GRADES
    }

    notebook = ttk.Notebook(window)
    notebook.pack(fill="both", expand=True, padx=ui(20), pady=ui(16))

    check_options = dict(
        bg=THEME_BG, fg=THEME_FG, selectcolor=THEME_BG,
        activebackground=THEME_BG, activeforeground=THEME_FG, anchor="w",
    )

    def make_tab(text):
        frame = tk.Frame(notebook, bg=THEME_BG)
        notebook.add(frame, text=text)
        canvas = tk.Canvas(frame, bg=THEME_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=THEME_BG)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        body.columnconfigure(1, weight=1)
        return body, canvas

    def bind_wheel(widget, canvas):
        # Windows/macOS report delta; X11 reports button 4/5.
        widget.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(-1 if event.delta > 0 else 1, "units"),
        )
        widget.bind(
            "<Button-4>", lambda _event: canvas.yview_scroll(-1, "units"))
        widget.bind(
            "<Button-5>", lambda _event: canvas.yview_scroll(1, "units"))
        for child in widget.winfo_children():
            bind_wheel(child, canvas)

    exercise, exercise_canvas = make_tab("Exercise")
    window_tab, window_canvas = make_tab("Window")
    startup, startup_canvas = make_tab("Startup")
    images, images_canvas = make_tab("Images")
    advanced, advanced_canvas = make_tab("Advanced")

    tk.Label(exercise, text="Exercise window opacity", font=THEME_FONT_BOLD,
             bg=THEME_BG, fg=THEME_FG).grid(
        row=0, column=0, columnspan=2, sticky="w")
    tk.Scale(
        exercise, from_=10, to=100, orient="horizontal", variable=opacity,
        bg=THEME_BG, fg=THEME_FG, highlightbackground=THEME_BG,
        troughcolor=THEME_BG, length=ui(260),
    ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=ui((6, 12)))

    tk.Checkbutton(exercise, text="Show \"Skip\" / \"Quit\"",
                   variable=show_skip_quit, **check_options,
                   ).grid(row=2, column=0, sticky="w", pady=ui(4), padx=ui((0, 12)))
    tk.Checkbutton(exercise, text="Restrict closing exercise",
                   variable=restrict_close, **check_options,
                   ).grid(row=2, column=1, sticky="w", pady=ui(4))
    tk.Checkbutton(exercise, text="Confirm on quit/reset",
                   variable=confirm_quit_reset, **check_options,
                   ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=ui(4))

    tk.Label(exercise, text="Session status", font=THEME_FONT_BOLD,
             bg=THEME_BG, fg=THEME_FG).grid(
        row=4, column=0, columnspan=2, sticky="w", pady=ui((10, 4)))
    tk.Checkbutton(exercise, text="Show \"time passed: \"",
                   variable=show_time_passed, **check_options,
                   ).grid(row=5, column=0, columnspan=2, sticky="ew", pady=ui(2))
    tk.Checkbutton(exercise, text="Show \"cards in batch: \"",
                   variable=show_cards_in_batch, **check_options,
                   ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=ui(2))
    tk.Checkbutton(exercise, text="Show \"session batches: \"",
                   variable=show_session_batches, **check_options,
                   ).grid(row=7, column=0, columnspan=2, sticky="ew", pady=ui(2))
    tk.Label(exercise, text="Position", font=THEME_FONT,
             bg=THEME_BG, fg=THEME_FG_DIM).grid(
        row=8, column=0, sticky="w", pady=ui((6, 0)))
    tk.OptionMenu(exercise, status_position, *STATUS_POSITIONS).grid(
        row=8, column=1, sticky="e", pady=ui((6, 0)))

    score_frame = tk.Frame(exercise, bg=THEME_BG)
    score_frame.grid(row=9, column=0, columnspan=2, sticky="w", pady=ui((10, 4)))
    tk.Label(score_frame, text="Score change", font=THEME_FONT_BOLD,
             bg=THEME_BG, fg=THEME_FG).grid(
        row=0, column=0, columnspan=len(GRADES), sticky="w")
    for column, grade in enumerate(GRADES):
        tk.Label(score_frame, text=grade.title(), font=THEME_FONT_SMALL,
                 bg=THEME_BG, fg=THEME_FG_DIM).grid(
            row=1, column=column, padx=ui((0 if column == 0 else 4, 0)))
        tk.Entry(score_frame, textvariable=score_vars[grade], width=5,
                 justify="center").grid(
            row=2, column=column, padx=ui((0 if column == 0 else 4, 0)),
            pady=ui((2, 0)))

    tk.Checkbutton(window_tab, text="Remember window geometry",
                   variable=remember_geometry, **check_options,
                   ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=ui(4))
    tk.Checkbutton(window_tab, text="Remember window position / monitor",
                   variable=remember_position, **check_options,
                   ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=ui(4))
    tk.Checkbutton(window_tab, text="Always on top during exercises",
                   variable=always_on_top, **check_options,
                   ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=ui(4))
    tk.Label(
        window_tab,
        text="Position is remembered per window on the current desktop layout.",
        font=THEME_FONT, bg=THEME_BG, fg=THEME_FG_DIM,
        wraplength=ui(280), justify="left",
    ).grid(row=3, column=0, columnspan=2, sticky="w", pady=ui((10, 4)))

    def clear_remembered():
        clear_remembered_files(preferences)
        last_deck_text.set("(none)")
        last_settings_text.set("(none)")
        recent_decks_text.set("0 deck(s)")

    tk.Checkbutton(startup, text="Auto-load last deck on startup",
                   variable=auto_deck, **check_options,
                   ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=ui(2))
    tk.Label(startup, textvariable=last_deck_text, font=THEME_FONT_SMALL,
             bg=THEME_BG, fg=THEME_FG_DIM, wraplength=ui(280),
             justify="left").grid(
        row=1, column=0, columnspan=2, sticky="w", padx=ui((20, 0)))
    tk.Checkbutton(startup, text="Auto-load last settings file on startup",
                   variable=auto_settings, **check_options,
                   ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=ui(2))
    tk.Label(startup, textvariable=last_settings_text, font=THEME_FONT_SMALL,
             bg=THEME_BG, fg=THEME_FG_DIM, wraplength=ui(280),
             justify="left").grid(
        row=3, column=0, columnspan=2, sticky="w", padx=ui((20, 0)))

    tk.Label(startup, text="Default global settings", font=THEME_FONT_BOLD,
             bg=THEME_BG, fg=THEME_FG).grid(
        row=4, column=0, columnspan=2, sticky="w", pady=ui((10, 4)))
    for offset, (key, label) in enumerate((
        ("delay", "Delay:"), ("session", "Batches in session:"),
        ("batch", "Cards in batch:"), ("jitter", "Delay Jitter:"),
    )):
        row = 5 + offset
        tk.Label(startup, text=label, font=THEME_FONT_SMALL,
                 bg=THEME_BG, fg=THEME_FG_DIM).grid(
            row=row, column=0, sticky="w")
        tk.Entry(startup, textvariable=default_global_vars[key], width=12).grid(
            row=row, column=1, sticky="e")

    tk.Label(startup, text="Remembered files", font=THEME_FONT_BOLD,
             bg=THEME_BG, fg=THEME_FG).grid(
        row=9, column=0, columnspan=2, sticky="w", pady=ui((10, 4)))
    tk.Label(startup, textvariable=recent_decks_text, font=THEME_FONT_SMALL,
             bg=THEME_BG, fg=THEME_FG_DIM).grid(
        row=10, column=0, sticky="w", pady=ui((4, 0)))
    tk.Button(startup, text="Clear remembered files",
              command=clear_remembered).grid(
        row=10, column=1, sticky="e", pady=ui((4, 0)))

    tk.Label(images, text="Image display mode", font=THEME_FONT,
             bg=THEME_BG, fg=THEME_FG_DIM).grid(
        row=0, column=0, sticky="w", pady=ui((10, 0)))
    tk.OptionMenu(images, image_mode, *IMAGE_DISPLAY_MODES).grid(
        row=0, column=1, sticky="e", pady=ui((10, 0)))
    tk.Label(images, text="Max image size (0 = no limit)", font=THEME_FONT,
             bg=THEME_BG, fg=THEME_FG_DIM).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=ui((8, 0)))
    tk.Label(images, text="Width", font=THEME_FONT_SMALL,
             bg=THEME_BG, fg=THEME_FG).grid(row=2, column=0, sticky="w")
    tk.Entry(images, textvariable=max_width, width=8).grid(
        row=2, column=1, sticky="e")
    tk.Label(images, text="Height", font=THEME_FONT_SMALL,
             bg=THEME_BG, fg=THEME_FG).grid(
        row=3, column=0, sticky="w", pady=ui((2, 0)))
    tk.Entry(images, textvariable=max_height, width=8).grid(
        row=3, column=1, sticky="e", pady=ui((2, 0)))

    tk.Label(images, text="Font scale", font=THEME_FONT,
             bg=THEME_BG, fg=THEME_FG_DIM).grid(
        row=4, column=0, sticky="w", pady=ui((10, 0)))
    tk.Label(images, textvariable=font_scale, font=THEME_FONT_SMALL,
             bg=THEME_BG, fg=THEME_FG).grid(row=4, column=1, sticky="e")
    tk.Scale(
        images, from_=50, to=200, resolution=5, orient="horizontal",
        variable=font_scale, bg=THEME_BG, fg=THEME_FG,
        highlightbackground=THEME_BG, troughcolor=THEME_BG, length=ui(260),
    ).grid(row=5, column=0, columnspan=2, sticky="ew", pady=ui((4, 0)))

    tk.Checkbutton(advanced, text="Enable debug log file",
                   variable=debug_log, **check_options,
                   ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=ui(4))
    tk.Checkbutton(advanced, text="Increase direction counter in normal/reverse modes",
                   variable=count_all_directions, **check_options,
                   ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=ui(4))

    for body, canvas in (
        (exercise, exercise_canvas), (window_tab, window_canvas),
        (startup, startup_canvas), (images, images_canvas),
        (advanced, advanced_canvas),
    ):
        bind_wheel(body, canvas)

    actions = tk.Frame(window, bg=THEME_BG)
    actions.pack(fill="x", padx=ui(20), pady=ui((0, 16)))

    def reset():
        opacity.set(DEFAULT_PREFERENCES["exercise_opacity"])
        show_skip_quit.set(int(DEFAULT_PREFERENCES["show_skip_quit"]))
        restrict_close.set(int(DEFAULT_PREFERENCES["restrict_exercise_close"]))
        confirm_quit_reset.set(int(DEFAULT_PREFERENCES["confirm_quit_reset"]))
        show_time_passed.set(int(DEFAULT_PREFERENCES["show_time_passed"]))
        show_cards_in_batch.set(int(DEFAULT_PREFERENCES["show_cards_in_batch"]))
        show_session_batches.set(int(DEFAULT_PREFERENCES["show_session_batches"]))
        status_position.set(DEFAULT_PREFERENCES["status_position"])
        remember_geometry.set(int(DEFAULT_PREFERENCES["remember_geometry"]))
        remember_position.set(int(DEFAULT_PREFERENCES["remember_position"]))
        always_on_top.set(int(DEFAULT_PREFERENCES["exercise_always_on_top"]))
        auto_deck.set(int(DEFAULT_PREFERENCES["auto_load_last_deck"]))
        auto_settings.set(int(DEFAULT_PREFERENCES["auto_load_last_settings"]))
        image_mode.set(DEFAULT_PREFERENCES["image_display_mode"])
        max_width.set(str(DEFAULT_PREFERENCES["max_image_width"]))
        max_height.set(str(DEFAULT_PREFERENCES["max_image_height"]))
        font_scale.set(DEFAULT_PREFERENCES["font_scale"])
        debug_log.set(int(DEFAULT_PREFERENCES["enable_debug_log"]))
        count_all_directions.set(int(DEFAULT_PREFERENCES["count_all_directions"]))
        for key, variable in default_global_vars.items():
            variable.set(DEFAULT_PREFERENCES["default_global_settings"][key])
        for grade in GRADES:
            score_vars[grade].set(DEFAULT_SCORE_DELTAS[grade])
        preferences["windows"] = {}
        clear_remembered_files(preferences)
        last_deck_text.set("(none)")
        last_settings_text.set("(none)")
        recent_decks_text.set("0 deck(s)")

    def save():
        defaults = {key: variable.get().strip()
                    for key, variable in default_global_vars.items()}
        try:
            normalize_settings({"global": defaults})
        except SettingsError as error:
            messagebox.showerror("Invalid default settings", str(error), parent=window)
            return
        preferences["exercise_opacity"] = opacity.get()
        preferences["show_skip_quit"] = bool(show_skip_quit.get())
        preferences["restrict_exercise_close"] = bool(restrict_close.get())
        preferences["confirm_quit_reset"] = bool(confirm_quit_reset.get())
        preferences["show_time_passed"] = bool(show_time_passed.get())
        preferences["show_cards_in_batch"] = bool(show_cards_in_batch.get())
        preferences["show_session_batches"] = bool(show_session_batches.get())
        preferences["status_position"] = status_position.get()
        preferences["remember_geometry"] = bool(remember_geometry.get())
        preferences["remember_position"] = bool(remember_position.get())
        preferences["exercise_always_on_top"] = bool(always_on_top.get())
        preferences["auto_load_last_deck"] = bool(auto_deck.get())
        preferences["auto_load_last_settings"] = bool(auto_settings.get())
        preferences["image_display_mode"] = image_mode.get()
        for key, variable in (("max_image_width", max_width),
                              ("max_image_height", max_height)):
            try:
                preferences[key] = max(0, min(4096, int(variable.get())))
            except (tk.TclError, ValueError):
                preferences[key] = 0
        try:
            preferences["font_scale"] = max(50, min(200, int(font_scale.get())))
        except (tk.TclError, ValueError):
            preferences["font_scale"] = 100
        preferences["enable_debug_log"] = bool(debug_log.get())
        preferences["count_all_directions"] = bool(count_all_directions.get())
        preferences["default_global_settings"] = defaults
        for grade, variable in score_vars.items():
            try:
                value = int(variable.get())
            except (tk.TclError, ValueError):
                continue
            preferences["score_deltas"][grade] = max(-100, min(100, value))
        save_preferences(preferences)
        window.destroy()

    tk.Button(actions, text="Cancel", command=window.destroy, width=10).pack(
        side="right", padx=ui((8, 0)))
    tk.Button(actions, text="Reset", command=reset, width=10).pack(
        side="right", padx=ui((8, 0)))
    tk.Button(
        actions, text="Save", command=save, width=10,
        bg=THEME_ACCENT, fg=THEME_BG, activebackground=THEME_ACCENT,
    ).pack(side="right")

    width = min(ui(520), parent.winfo_screenwidth() - ui(40))
    height = min(ui(560), parent.winfo_screenheight() - ui(80))
    window.geometry(f"{width}x{height}")
    window.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - window.winfo_width()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - window.winfo_height()) // 2
    window.geometry(f"+{x}+{y}")
    window.grab_set()
    parent.wait_window(window)
