---
name: run-stunning-winner
description: Run, start, launch, drive and screenshot the Genre Retagger (Tkinter GUI + CLI that rewrites music genre tags with mutagen), test genre classifier rules, or check rule ordering. Use when asked to run the app or GUI, take a screenshot, try the retagger on sample files, or verify a change to genre_classifier.py, retag_genres.py, retag_gui.py or launch.sh.
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

```bash
D=.claude/skills/run-stunning-winner/driver.sh
$D fixtures                          # sample library -> /tmp/run-genre-retagger/lib
$D start                             # Xvfb :99 + ./launch.sh in tmux session "gui"
$D scan /tmp/run-genre-retagger/lib  # type path + Enter -> preview table
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
- **`start` hangs on "timeout waiting for: window"**: read `/tmp/run-genre-retagger/gui.log`
  (or `tmux attach -t gui`). It's usually the Tk check in `launch.sh` or a failed mutagen
  install.
