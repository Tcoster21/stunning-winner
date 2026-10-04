#!/usr/bin/env python3
"""Rewrite genre tags in a music library using genre_classifier.classify_genre.

Usage:
    python retag_genres.py [DIRECTORY]

If DIRECTORY is omitted you are prompted for it. The script always shows a
dry-run table first and only writes after you answer "y".
"""

import os
import re
import sys

from mutagen import File as MutagenFile
from mutagen import MutagenError
from mutagen.aiff import AIFF
from mutagen.apev2 import APEv2File
from mutagen.asf import ASF
from mutagen.flac import FLAC
from mutagen.id3 import ID3FileType, TCON
from mutagen.mp4 import MP4
from mutagen.ogg import OggFileType
from mutagen.wave import WAVE

from genre_classifier import classify_genre

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".m4a", ".m4b", ".mp4", ".ogg", ".oga", ".opus",
    ".aiff", ".aif", ".wav", ".wma", ".ape", ".wv", ".mpc",
}

MP4_GENRE = "\xa9gen"
ASF_GENRE = "WM/Genre"
APE_GENRE = "Genre"
VORBIS_GENRE = "genre"


# --------------------------------------------------------------------------
# Format-specific tag access
# --------------------------------------------------------------------------

# ID3v2.3 stores multiple genres joined by a single "/". Split on that, but
# never on "//", which is the hierarchy separator this script writes.
_ID3_SEP = re.compile(r"(?<!/)/(?!/)")


def _split_values(values, id3=False):
    """Flatten tag values into individual, non-empty genre strings."""
    out = []
    for v in values:
        text = str(v).replace("\x00", ";")
        if id3:
            text = _ID3_SEP.sub(";", text)
        for part in text.split(";"):
            part = part.strip()
            if part:
                out.append(part)
    return out


def read_genres(audio):
    """Return the list of genre strings stored in a mutagen file object."""
    tags = audio.tags
    if tags is None:
        return []

    # MP3, AIFF, WAV (ID3 tags). TCON.genres resolves ID3v1-style "(17)" refs.
    if isinstance(audio, (ID3FileType, AIFF, WAVE)):
        frames = tags.getall("TCON")
        return _split_values((g for f in frames for g in f.genres), id3=True)

    if isinstance(audio, MP4):
        return _split_values(tags.get(MP4_GENRE, []))

    if isinstance(audio, ASF):
        return _split_values(tags.get(ASF_GENRE, []))

    if isinstance(audio, APEv2File):
        return _split_values([tags[APE_GENRE]] if APE_GENRE in tags else [])

    # FLAC, Ogg Vorbis/Opus/FLAC/Speex: Vorbis comments, case-insensitive keys.
    if isinstance(audio, (FLAC, OggFileType)):
        return _split_values(tags.get(VORBIS_GENRE, []))

    # Unknown container: try a generic "genre" key.
    try:
        return _split_values(tags.get("genre", []))
    except Exception:
        return []


def write_genre(audio, genre):
    """Replace all genre values in the file with a single new genre."""
    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags

    if isinstance(audio, (ID3FileType, AIFF, WAVE)):
        tags.setall("TCON", [TCON(encoding=3, text=[genre])])
        # Keep the file's existing ID3 version (v2.3 is common for player compat).
        v2_version = 3 if tags.version[:2] == (2, 3) else 4
        audio.save(v2_version=v2_version)
        return

    if isinstance(audio, MP4):
        tags[MP4_GENRE] = [genre]
        tags.pop("gnre", None)  # legacy numeric genre atom
    elif isinstance(audio, ASF):
        tags[ASF_GENRE] = [genre]
    elif isinstance(audio, APEv2File):
        tags[APE_GENRE] = genre
    elif isinstance(audio, (FLAC, OggFileType)):
        tags[VORBIS_GENRE] = [genre]
    else:
        tags["genre"] = [genre]
    audio.save()


# --------------------------------------------------------------------------
# Scanning / planning
# --------------------------------------------------------------------------

def find_audio_files(root):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if os.path.splitext(name)[1].lower() in AUDIO_EXTENSIONS:
                yield os.path.join(dirpath, name)


def build_plan(root, progress=None):
    """Return a list of dicts describing what would happen to each file.

    progress, if given, is called as progress(n, total) before the nth file.
    """
    plan = []
    paths = sorted(find_audio_files(root))
    for i, path in enumerate(paths, 1):
        if progress:
            progress(i, len(paths))
        entry = {"path": path, "rel": os.path.relpath(path, root),
                 "current": "", "proposed": "", "status": ""}
        try:
            audio = MutagenFile(path)
        except (MutagenError, OSError) as e:
            entry["status"] = f"error: {e}"
            plan.append(entry)
            continue
        if audio is None:
            entry["status"] = "error: unsupported/unrecognized file"
            plan.append(entry)
            continue

        genres = read_genres(audio)
        if not genres:
            entry["status"] = "no genre"
            plan.append(entry)
            continue

        current = genres[0]
        proposed = classify_genre(current)
        entry["current"] = current
        entry["proposed"] = proposed
        # Multiple values collapse to one, so only "same" when nothing changes.
        if proposed == current and len(genres) == 1:
            entry["status"] = "same"
        else:
            entry["status"] = "change"
        plan.append(entry)
    return plan


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def _fit(text, width):
    if len(text) <= width:
        return text.ljust(width)
    return "…" + text[-(width - 1):]


def print_table(plan, max_name=60, max_genre=40):
    headers = ("Filename", "Current Genre", "Proposed Genre")
    rows = []
    for e in plan:
        if e["status"] == "no genre":
            current, proposed = "(none)", "(skip)"
        elif e["status"].startswith("error"):
            current, proposed = "(unreadable)", "(skip)"
        else:
            current = e["current"]
            proposed = e["proposed"] + ("  (unchanged)" if e["status"] == "same" else "")
        rows.append((e["rel"], current, proposed))

    w1 = min(max_name, max([len(headers[0])] + [len(r[0]) for r in rows]))
    w2 = min(max_genre, max([len(headers[1])] + [len(r[1]) for r in rows]))
    w3 = max([len(headers[2])] + [len(r[2]) for r in rows])

    line = f"{_fit(headers[0], w1)} | {_fit(headers[1], w2)} | {headers[2]}"
    print(line)
    print("-" * w1 + "-+-" + "-" * w2 + "-+-" + "-" * w3)
    for name, current, proposed in rows:
        print(f"{_fit(name, w1)} | {_fit(current, w2)} | {proposed}")


def count(plan, status):
    return sum(1 for e in plan if e["status"] == status)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    if len(sys.argv) > 1:
        root = sys.argv[1]
    else:
        root = input("Directory to scan: ").strip().strip('"').strip("'")
    root = os.path.abspath(os.path.expanduser(root))
    if not os.path.isdir(root):
        print(f"Not a directory: {root}")
        return 1

    print(f"Scanning {root} ...\n")
    plan = build_plan(root)
    if not plan:
        print("No audio files found.")
        return 0

    print("DRY RUN — no files have been modified.\n")
    print_table(plan)

    to_change = [e for e in plan if e["status"] == "change"]
    read_errors = [e for e in plan if e["status"].startswith("error")]
    print()
    print(f"Files found:        {len(plan)}")
    print(f"Would update:       {len(to_change)}")
    print(f"Already correct:    {count(plan, 'same')}")
    print(f"No genre tag:       {count(plan, 'no genre')}")
    if read_errors:
        print(f"Unreadable:         {len(read_errors)}")
        for e in read_errors:
            print(f"  {e['rel']}: {e['status']}")
    print()

    if not to_change:
        print("Nothing to change.")
        return 0

    try:
        answer = input("Apply changes? (y/n) ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        print("Aborted. No files were modified.")
        return 0

    updated = 0
    write_errors = []
    for e in to_change:
        try:
            audio = MutagenFile(e["path"])
            write_genre(audio, e["proposed"])
            updated += 1
        except Exception as exc:  # keep going; report at the end
            write_errors.append((e["rel"], exc))

    print()
    print("Summary")
    print("-------")
    print(f"Updated:                      {updated}")
    print(f"Skipped (already correct):    {count(plan, 'same')}")
    print(f"Skipped (no genre found):     {count(plan, 'no genre')}")
    if read_errors:
        print(f"Skipped (unreadable):         {len(read_errors)}")
    if write_errors:
        print(f"Failed to write:              {len(write_errors)}")
        for rel, exc in write_errors:
            print(f"  {rel}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
