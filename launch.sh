#!/usr/bin/env bash
# Double-click launcher for the Genre Retagger window (Mac and Linux).
# Installs the one dependency (mutagen) on first run, then opens the GUI.
cd "$(dirname "$0")" || exit 1

fail() {
    echo
    echo "$1"
    echo
    read -r -p "Press Enter to close..." _
    exit 1
}

PY=$(command -v python3) || fail "Python 3 is not installed. Download it from https://www.python.org/downloads/"
"$PY" -c "import tkinter" 2>/dev/null || fail "This Python has no Tk (window) support.
  Mac: install Python from https://www.python.org/downloads/ (Homebrew: brew install python-tk)
  Linux: sudo apt install python3-tk"

if ! "$PY" -c "import mutagen" 2>/dev/null; then
    # Prefer a private virtualenv next to the script; fall back to a user install.
    if [ ! -x .venv/bin/python ]; then
        echo "First run: setting up (this only happens once)..."
        "$PY" -m venv .venv >/dev/null 2>&1 || rm -rf .venv
    fi
    if [ -x .venv/bin/python ]; then
        .venv/bin/python -c "import mutagen" 2>/dev/null \
            || .venv/bin/python -m pip install -q mutagen \
            || fail "Could not install mutagen. Check your internet connection and try again."
        PY=.venv/bin/python
    else
        "$PY" -m pip install --user -q mutagen \
            || fail "Could not install mutagen. Run: python3 -m pip install mutagen"
    fi
fi

exec "$PY" retag_gui.py
