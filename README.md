# Genre retagger

Set the genre tags in a music library to a `Parent//Sub//Sub-sub` hierarchy.
The window lets you pick genres by hand from dropdowns (or type your own);
the command-line tool assigns them automatically with the rules in
`genre_classifier.py`.

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

In the window:

1. **Browse…** to your music folder. The table lists every audio file and its
   current genre.
2. Select one or more files (Ctrl/Cmd-click or Shift-click for several;
   click a column header to sort; **Select all with same current genre**
   grabs every file that shares the selected file's genre).
3. Choose **Parent**, then **Sub**, then **Sub-sub** from the dropdowns. Each
   list narrows to fit the one before it. Sub and Sub-sub are optional. To use
   a genre that isn't listed, just type it into any box. Custom genres are
   remembered (in `~/.genre_retagger_custom.json`) and appear in the lists
   next time.
4. Click **Set genre on N files**. The New Genre column fills in; nothing is
   written yet. **Clear new genre** undoes it for the selected files.
5. Click **Apply changes** and confirm. Only then are files written.

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
- Writing a genre replaces all of a file's genre values with that one genre.
  The command-line tool classifies only the first existing genre. Values separated by `;`, NUL, or (ID3v2.3) `/` count as
  multiple genres.
- Command line: files with no genre tag, or whose tag already equals the
  result, are skipped. In the window you can give untagged files a genre too.
- MP3s keep their existing ID3 version (v2.3 stays v2.3).

Back up your library first — the write step changes files in place.
