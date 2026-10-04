# Genre retagger

Scans a music library and rewrites each file's genre tag into a
`Parent//Sub//Detail` hierarchy using the rules in `genre_classifier.py`.

## Easy launch (window)

Double-click the launcher for your computer:

| Computer | Double-click |
|---|---|
| Windows | `Genre Retagger (Windows).bat` |
| Mac | `Genre Retagger (Mac).command` (first time: right-click → Open) |
| Linux | `launch.sh` (or run `./launch.sh`) |

You need Python 3 from <https://www.python.org/downloads/> (on Windows, tick
"Add python.exe to PATH" during setup). The first launch installs `mutagen`
automatically.

In the window: **Browse…** to your music folder → check the preview →
**Apply changes**. Nothing is written until you click Apply and confirm.

## Command line

```
pip install -r requirements.txt
python retag_genres.py            # prompts for a directory
python retag_genres.py ~/Music    # or pass it directly
```

It always starts with a dry run: a `Filename | Current Genre | Proposed Genre`
table plus counts. Nothing is written until you answer `y` to
`Apply changes? (y/n)`.

## Details

- Formats: MP3, AIFF, WAV (ID3 `TCON`), FLAC / OGG / Opus (Vorbis `GENRE`),
  M4A/MP4 (`©gen`), WMA (`WM/Genre`), APE / WavPack / Musepack (APEv2 `Genre`).
- Only the first genre is classified; all genre values are replaced with the
  single result. Values separated by `;`, NUL, or (ID3v2.3) `/` count as
  multiple genres.
- Files with no genre tag, or whose tag already equals the result, are skipped.
- MP3s keep their existing ID3 version (v2.3 stays v2.3).

Back up your library first — the write step changes files in place.
