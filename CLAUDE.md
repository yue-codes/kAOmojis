# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

kAOmojis: a minimalist, keyboard-first kaomoji picker desktop app. Opens as a
small frameless floating window, lets the user filter kaomojis by typing,
select one with arrow keys or a click, and copies it to the clipboard while
closing the app.

## Commands

```bash
python -m venv venv
source venv/bin/activate        # bash/zsh; use activate.fish for fish shell
pip install -r requirements.txt
python main.py                  # run the app
```

There is no build step, linter, or test suite configured yet — this is a
single-prototype-stage project.

## Architecture

Everything lives in two files:

- `main.py` — all application logic, in one file, split into these pieces:
  - `SearchBar(QLineEdit)` — intercepts arrow keys/Enter/Escape/Tab and turns
    them into Qt signals instead of letting them move the text cursor,
    because keyboard focus stays on the search bar at all times (launcher-style
    UX). Regular typing still falls through to the default `QLineEdit` behavior.
  - `DraggableContainer(QFrame)` — the window is frameless (`Qt.FramelessWindowHint`),
    so this subclass implements click-and-drag-to-move on empty areas. It must be a
    real Python subclass, not an instance-level `mousePressEvent` monkeypatch —
    PySide6 only dispatches virtual event methods to Python for classes actually
    defined in Python, not for attributes patched onto plain `QFrame` instances.
  - `KaomojiButton(QPushButton)` — exists only so QSS can target it by type
    selector (`KaomojiButton { ... }`) without a `class` dynamic-property hack.
  - `KaomojiPicker(QWidget)` — the main window. Holds `self.tabs`, a list of
    `(category_name, [entries])` built by prepending a synthetic "Todos" tab
    (union of all categories) to the categories loaded from JSON. Keyboard
    navigation across the button grid is tracked manually via `self.selected_index`
    and a `selected` dynamic property (not Qt's built-in focus chain), since focus
    never leaves the search bar.
- `kaomojis.json` — the only place kaomoji data lives. Each category is a list
  of `{"kaomoji": str, "tags": [str, ...]}`. Search matches against both the
  literal kaomoji and its `tags`, because matching the raw symbol string
  against typed keywords rarely works — the tags exist specifically to make
  free-text search meaningful.

Search behavior: typing anything hides the tab bar and searches across *all*
categories at once (via `self.categories`, not `self.tabs`, to avoid
duplicating results through the synthetic "Todos" tab); clearing the search
box restores per-tab browsing.

## Key design decisions (don't relitigate without reason)

- **PySide6**, not PyQt6: same Qt6 API, LGPL license instead of GPL/commercial.
- **No `pyclip`/`pyperclip`**: clipboard goes through `QApplication.clipboard()`
  directly. Qt already has a native Wayland clipboard backend; shelling out to
  `xclip`/`wl-clipboard` would add an external dependency that isn't always
  installed, for no benefit.
- **Qt over Tkinter**: Qt has a native Wayland QPA plugin; Tkinter relies on
  XWayland, which is less reliable for a borderless floating window under
  Hyprland/KDE.
- One process per invocation — no system tray/resident background process,
  no global hotkey listener, no cross-session state persistence. These are
  deliberately out of scope for the current prototype stage (see README.md's
  "Pendiente" section).
