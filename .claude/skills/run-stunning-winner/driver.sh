#!/usr/bin/env bash
# Driver for the Genre Retagger (Tkinter GUI + CLI) in a headless Linux container.
# Run from the repo root:  .claude/skills/run-stunning-winner/driver.sh <command> [args]
#
#   setup             pick a Tk-capable python, create .venv with mutagen, check tools
#   fixtures [DIR]    generate a sample music library (mp3/flac/m4a/ogg, mixed genres)
#   start             start Xvfb :99 and the GUI via ./launch.sh (in tmux session "gui")
#   scan DIR          type DIR into the folder box and press Enter (starts a scan)
#   filter            toggle "Show only files that will change"
#   apply             click "Apply changes", then Enter = "Yes" in the confirm dialog
#   ok                press Enter (dismiss the result dialog)
#   ss NAME           screenshot the whole display to $RUN_DIR/NAME.png
#   tags [DIR]        print the genre tag stored in every file under DIR
#   classify GENRE..  print classify_genre() for each argument
#   shadowed          list rules whose own genre name is matched by another rule
#   cli DIR [y|n]     run the command-line tool, answering the prompt with y or n
#   stop              kill the GUI and Xvfb
set -euo pipefail

REPO=$(cd "$(dirname "$0")/../../.." && pwd)
RUN_DIR=${RUN_DIR:-/tmp/run-genre-retagger}
export DISPLAY=${DISPLAY_NUM:-:99}
VPY="$REPO/.venv/bin/python"
mkdir -p "$RUN_DIR"

tk_python() {
    # /usr/bin/python3 is often a build without _tkinter; find one that has it.
    for p in python3 python3.13 python3.12 python3.11 python3.10; do
        command -v "$p" >/dev/null && "$p" -c "import tkinter" 2>/dev/null && { command -v "$p"; return; }
    done
    echo "No python with tkinter. Fix: apt-get install -y python3-tk" >&2; exit 1
}

wait_for() {  # wait_for <seconds> <command...>
    local n=$(( $1 * 5 )); shift
    for _ in $(seq "$n"); do "$@" >/dev/null 2>&1 && return 0; sleep 0.2; done
    echo "timeout waiting for: $*" >&2; return 1
}

window() { xdotool search --name '^Genre Retagger$' | head -1; }

case "${1:-}" in
setup)
    for t in Xvfb xdotool tmux import ffmpeg; do
        command -v "$t" >/dev/null || { echo "missing $t (see SKILL.md Prerequisites)"; exit 1; }
    done
    PY=$(tk_python); echo "Tk python: $PY"
    mkdir -p "$RUN_DIR/bin"; ln -sf "$PY" "$RUN_DIR/bin/python3"
    if [ ! -x "$VPY" ]; then "$PY" -m venv "$REPO/.venv"; fi
    "$VPY" -c "import mutagen" 2>/dev/null || "$VPY" -m pip install -q mutagen
    "$VPY" -c "import tkinter, mutagen; print('ready: tkinter', tkinter.TkVersion, 'mutagen', mutagen.version_string)"
    ;;
fixtures)
    D=${2:-$RUN_DIR/lib}; rm -rf "$D"; mkdir -p "$D/Band/Album"; cd "$D"
    gen() { ffmpeg -y -loglevel error -f lavfi -i anullsrc=r=44100:cl=mono -t 0.3 "$@"; }
    gen -metadata genre="Post-Punk"  "Band/Album/01.mp3"
    gen -metadata genre="Ska Punk"   "Band/Album/02.flac"
    gen -metadata genre="Bossa Nova" 03.m4a
    gen -c:a libvorbis -metadata genre="Shoegaze" 04.ogg
    gen -metadata genre="Jazz"       05.flac          # already correct
    gen                              06_none.mp3      # no genre tag
    echo junk >                      07_broken.mp3    # unreadable
    echo "fixtures in $D"
    ;;
start)
    [ -e "$RUN_DIR/bin/python3" ] || { echo "run setup first"; exit 1; }
    pgrep -f "Xvfb $DISPLAY" >/dev/null || { Xvfb "$DISPLAY" -screen 0 1100x700x24 >"$RUN_DIR/xvfb.log" 2>&1 & }
    wait_for 10 xdotool getmouselocation
    tmux kill-session -t gui 2>/dev/null || true
    tmux new-session -d -s gui "cd '$REPO' && DISPLAY=$DISPLAY PATH='$RUN_DIR/bin':\$PATH ./launch.sh 2>&1 | tee '$RUN_DIR/gui.log'; sleep 3600"
    wait_for 120 window
    sleep 0.5; echo "window $(window) up"; xdotool getwindowgeometry "$(window)"
    ;;
scan)
    D=${2:?usage: scan DIR}
    # No window manager: the main window sits at 0,0, 1000x620. Folder entry at (400,21).
    xdotool mousemove 400 21 click 1; xdotool key ctrl+a BackSpace
    xdotool type --delay 5 "$D"; xdotool key Return
    sleep 2
    ;;
filter) xdotool mousemove 18 56 click 1; sleep 0.3 ;;
apply)
    xdotool mousemove 930 597 click 1
    wait_for 10 xdotool search --name '^Apply changes\?$'
    xdotool key Return   # askyesno defaults to Yes
    sleep 2
    ;;
ok) xdotool key Return; sleep 0.3 ;;
ss) import -window root "$RUN_DIR/${2:?usage: ss NAME}.png"; echo "$RUN_DIR/$2.png" ;;
tags)
    D=${2:-$RUN_DIR/lib}
    "$VPY" - "$D" <<'PY'
import sys, glob, mutagen
root = sys.argv[1]
for f in sorted(glob.glob(root + "/**/*.*", recursive=True)):
    try:
        a = mutagen.File(f, easy=True)
        print(f[len(root) + 1:], a.get("genre") if a else None)
    except Exception as e:
        print(f[len(root) + 1:], "ERROR", e)
PY
    ;;
classify)
    shift; cd "$REPO"
    "$VPY" -c 'import sys; from genre_classifier import classify_genre as c
for g in sys.argv[1:]: print(f"{g!r:28} -> {c(g)}")' "$@"
    ;;
shadowed)
    cd "$REPO"
    "$VPY" -c 'from genre_classifier import RULES, classify_genre
for p, t in RULES:
    name = t.split("//")[-1]; got = classify_genre(name)
    if got != t: print(f"{name!r:24} want {t:45} got {got}")'
    ;;
cli)
    D=${2:?usage: cli DIR [y|n]}; cd "$REPO"
    printf '%s\n' "${3:-n}" | "$VPY" retag_genres.py "$D"
    ;;
stop)
    tmux kill-session -t gui 2>/dev/null || true
    pkill -f "Xvfb $DISPLAY" 2>/dev/null || true
    echo stopped
    ;;
*) sed -n '2,20p' "$0"; exit 1 ;;
esac
