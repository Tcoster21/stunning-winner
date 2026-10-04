---
name: run-stunning-winner
description: Run, start, launch, drive, smoke-test and screenshot the Genre Retagger (Tkinter GUI + CLI that rewrites music genre tags with mutagen), test genre classifier rules, or check rule ordering. Use when asked to run the app or GUI, take a screenshot, try the retagger on sample files, or verify a change to genre_classifier.py, retag_genres.py, retag_gui.py or launch.sh.
---

The Genre Retagger is a Tkinter window (`retag_gui.py`, started by `launch.sh`) plus a CLI
(`retag_genres.py`), and the genre rules live in `genre_classifier.py`. Drive everything with
`.claude/skills/run-stunning-winner/driver.sh`. It runs the real launcher on Xvfb and clicks the
window with xdotool. All paths are relative to the repo root.

## Prerequisites

Xvfb, tmux, ImageMagick (`import`), ffmpeg and `python3.12` with `python3-tk` were already in the
container. Only xdotool was missing:

```bash
apt-get install -y xdotool
```

## Setup

```bash
.claude/skills/run-stunning-winner/driver.sh setup
```

This finds a Python that has tkinter, creates `.venv` (git-ignored) with mutagen, and links that
Python as `$RUN_DIR/bin/python3` so `launch.sh` picks it up. Expect `ready: tkinter 8.6 mutagen …`.

## Run (agent path)

Start with the one-shot check. It runs the full user flow (launch → Browse… → filter → Apply →
Yes) and diffs the tags written to disk against the expected values:

```bash
.claude/skills/run-stunning-winner/driver.sh smoke   # -> SMOKE PASS, exit 0
```

On a mismatch it prints a unified diff, `SMOKE FAIL`, and exits 1. To confirm it can fail, I broke
the Bossa Nova rule and got `-03.m4a ['Latin//Bossa Nova'] / +03.m4a ['Jazz//Bossa Nova']`.
Screenshots: `smoke_preview.png` and `smoke_applied.png`. Look at them after any GUI change.

To drive it step by step:

```bash
D=.claude/skills/run-stunning-winner/driver.sh
$D fixtures                          # sample library -> /tmp/run-genre-retagger/lib
$D start                             # Xvfb :99 + ./launch.sh in tmux session "gui"
$D browse /tmp/run-genre-retagger/lib  # Browse… -> Tk folder dialog -> auto-scan
$D scan /tmp/run-genre-retagger/lib  # or: type path in the box + Enter (replaces old text)
$D ss preview                        # -> /tmp/run-genre-retagger/preview.png  (look at it)
$D filter                            # toggle "Show only files that will change"
$D apply                             # click Apply changes, Enter = Yes
$D ss applied                        # summary dialog over blue "Updated" rows
$D ok                                # dismiss the dialog
$D tags                              # read the tags back from disk
$D stop
```

The expected `tags` output after applying is:
`03.m4a ['Latin//Bossa Nova']`, `04.ogg ['Rock//Shoegaze']`, `05.flac ['Jazz']`,
`06_none.mp3 None`, `07_broken.mp3 ERROR can't sync to MPEG frame`,
`Band/Album/01.mp3 ['Rock//Post-Punk']`, `Band/Album/02.flac ['Reggae//Ska//Ska Punk']`.

Screenshots and logs go in `/tmp/run-genre-retagger/` (override with `RUN_DIR`). The launcher's
terminal output goes to `gui.log` there; it's empty on a healthy run.

### Direct invocation (most changes touch only the rules)

```bash
D=.claude/skills/run-stunning-winner/driver.sh
$D classify "K-Pop" "Pop Punk" "Drum & Bass"   # one line per genre: 'K-Pop' -> World//Asia//K-Pop
$D shadowed                                    # rules whose own name is matched by another rule
$D fixtures && $D cli /tmp/run-genre-retagger/lib n   # CLI dry-run table, answer n (y writes)
```

The `shadowed` command prints a 10-line baseline. Every line on it is expected:
- **Test artifacts:** Symphonic Black, Minimal, East Coast, the four Holiday//Christmas subgenres
  and Inspirational. Their tag name alone isn't a pattern the rule matches; the real phrases
  like "minimal techno" classify correctly.
- **Deliberate duplicates:** Surf Rock and Folk-Rock, where the user picked the `Rock//` version.

Any **new** line after a rules edit means a rule got shadowed. Re-run `fixtures` before each GUI
run, because applying rewrites the files.

## Test

There is no test suite. `driver.sh smoke` is the end-to-end check, and `driver.sh shadowed` is the
check for rule changes.

## Run (human path)

Double-click `launch.sh` (Linux), `Genre Retagger (Mac).command` or `Genre Retagger (Windows).bat`.
Headless this does nothing useful without Xvfb, so use the agent path. The Windows `.bat` has never
been executed, because there's no Windows here.

## Gotchas

- **`/usr/bin/python3` is 3.11 with no `_tkinter`.** `apt install python3-tk` only covers 3.12,
  so `launch.sh` would stop at "This Python has no Tk (window) support". `setup` puts a
  `python3` → `python3.12` link first on `PATH` for `start`.
- **PEP 668:** `python3.12 -m pip install mutagen` fails with "externally-managed-environment".
  This is why everything goes through `.venv`, which is also the path `launch.sh` takes on first run.
- **Clicks use fixed coordinates.** There's no window manager, so the main window sits at 0,0 at
  1000x620: folder entry (400,21), filter checkbox (18,56), Apply (930,597). If you change the GUI
  layout or the default `geometry`, update the numbers in `driver.sh`.
- **In a Tk entry, Ctrl+A moves to the start of the line; it doesn't select all.** Clearing the
  box with Ctrl+A then BackSpace left the old path in place, so the new one was typed in front of
  it (`/tmp/…/lib/tmp/…/lib`) and the app said "Please choose a folder that exists." Tk's
  select-all is **Ctrl+/**, which `scan` now uses.
- **Tk hides dialogs instead of destroying them.** After the first Apply, the old
  "Apply changes?" window still exists (unmapped), so a plain `xdotool search` "finds" it before
  the new one appears. The driver's `visible`/`gone` helpers always pass `--onlyvisible`.
- **The Tk folder dialog needs Enter twice.** The Selection field is focused and pre-selected, so
  typing replaces it. The first Enter only navigates *into* the folder; the second accepts it.
- **Message boxes are also titled "Genre Retagger"**, the same as the main window, so the
  driver's `window` lookup is only trustworthy before any dialog has opened, as in `start`.
- **Use Enter for dialogs.** Tk's `askyesno` defaults to Yes and `showinfo` to OK, so Enter is
  more reliable than guessing where a dialog lands.
- **Pressing Enter in the folder box starts a scan** (`<Return>` binding), so `scan` needs no
  click on the Scan button.
- **Don't pipe `shadowed`/`classify` into `head`.** That raises a harmless `BrokenPipeError`
  traceback.

## Troubleshooting

- **Table goes blank after Apply with the filter on**: this was a real bug, fixed in 7bf9229. If
  it comes back, check the filter condition in `RetagApp._refresh_table`.
- **`ModuleNotFoundError: No module named 'tkinter'`**: you ran a script with `python3` (3.11).
  Use `.venv/bin/python`, or rerun `setup`.
- **"Please choose a folder that exists." with a doubled path in the box**: this was the Ctrl+A
  issue above. Use the current `scan`, which uses Ctrl+/.
- **`timeout waiting for: visible ^Apply changes\?$`**: Apply was clicked while it was disabled
  (no scan yet, or nothing to change), or an error box is covering the window. Take a screenshot
  with `$D ss debug` to see which.
- **`start` hangs on "timeout waiting for: window"**: read `/tmp/run-genre-retagger/gui.log`
  (or `tmux attach -t gui`). It's usually the Tk check in `launch.sh` or a failed mutagen
  install.
