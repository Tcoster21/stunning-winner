#!/usr/bin/env python3
"""Simple window for setting genre tags by hand.

Pick a folder, select files in the table, choose Parent / Sub / Sub-sub
genres from the dropdowns (or type your own), then Apply.
"""

import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mutagen import File as MutagenFile

from genre_taxonomy import Taxonomy, join_genre, split_genre
from retag_genres import scan_library, write_genre


class RetagApp:
    def __init__(self, root):
        self.root = root
        self.entries = []            # one dict per audio file, see scan_library()
        self.taxonomy = Taxonomy()
        self.events = queue.Queue()  # worker thread -> UI thread
        self.busy = False
        self.sort_col, self.sort_reverse = "file", False

        root.title("Genre Retagger")
        root.geometry("1000x660")
        root.minsize(760, 460)
        if sys.platform.startswith("linux"):
            ttk.Style().theme_use("clam")

        self._build_widgets()
        root.after(100, self._poll_events)

    # ---------------------------------------------------------------- layout

    def _build_widgets(self):
        pad = {"padx": 10, "pady": 6}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Music folder:").pack(side="left")
        self.folder = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.folder)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        entry.bind("<Return>", lambda _e: self.scan())
        ttk.Button(top, text="Browse…", command=self.browse).pack(side="left")
        self.scan_btn = ttk.Button(top, text="Scan", command=self.scan)
        self.scan_btn.pack(side="left", padx=(6, 0))

        opts = ttk.Frame(self.root)
        opts.pack(fill="x", padx=10)
        self.only_pending = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Show only files with a new genre",
                        variable=self.only_pending,
                        command=self._refresh_table).pack(side="left")
        self.counts = ttk.Label(opts, text="")
        self.counts.pack(side="right")

        table = ttk.Frame(self.root)
        table.pack(fill="both", expand=True, **pad)
        cols = ("file", "current", "new", "status")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="extended")
        for col, title, width in (("file", "File", 360),
                                  ("current", "Current Genre", 230),
                                  ("new", "New Genre", 250),
                                  ("status", "Status", 120)):
            self.tree.heading(col, text=title, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=width, anchor="w")
        self.tree.tag_configure("pending", foreground="#0a5c0a")
        self.tree.tag_configure("muted", foreground="#777777")
        self.tree.tag_configure("error", foreground="#b00020")
        self.tree.tag_configure("updated", foreground="#0b4f9c")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        ysb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)

        # Genre picker: three linked dropdowns. Typing a value that isn't in
        # the list creates a custom genre.
        editor = ttk.LabelFrame(self.root, text="Set genre for selected files")
        editor.pack(fill="x", padx=10, pady=(0, 6))
        row1 = ttk.Frame(editor)
        row1.pack(fill="x", padx=8, pady=(6, 2))
        self.parent_var, self.sub_var, self.detail_var = (tk.StringVar() for _ in range(3))
        self.parent_box = self._combo(row1, "Parent", self.parent_var)
        self.sub_box = self._combo(row1, "Sub", self.sub_var)
        self.detail_box = self._combo(row1, "Sub-sub", self.detail_var)
        self.parent_box.configure(values=self.taxonomy.parents())
        self.parent_box.bind("<<ComboboxSelected>>", lambda _e: self._parent_changed(clear=True))
        self.parent_box.bind("<FocusOut>", lambda _e: self._parent_changed(clear=False))
        self.sub_box.bind("<<ComboboxSelected>>", lambda _e: self._sub_changed(clear=True))
        self.sub_box.bind("<FocusOut>", lambda _e: self._sub_changed(clear=False))
        # Refresh the next list just before it opens, so typed values count too.
        self.sub_box.configure(postcommand=lambda: self._parent_changed(clear=False))
        self.detail_box.configure(postcommand=lambda: self._sub_changed(clear=False))

        row2 = ttk.Frame(editor)
        row2.pack(fill="x", padx=8, pady=(2, 8))
        self.set_btn = ttk.Button(row2, text="Set genre", command=self.set_genre)
        self.set_btn.pack(side="left")
        ttk.Button(row2, text="Clear new genre", command=self.clear_genre).pack(side="left", padx=6)
        ttk.Button(row2, text="Select all with same current genre",
                   command=self.select_same).pack(side="left")
        self.preview = ttk.Label(row2, text="")
        self.preview.pack(side="right")
        for var in (self.parent_var, self.sub_var, self.detail_var):
            var.trace_add("write", lambda *_a: self._update_preview())

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(bottom, mode="determinate", length=200)
        self.progress.pack(side="left")
        self.status = ttk.Label(bottom, text="Choose your music folder. "
                                             "Nothing is changed until you click Apply.")
        self.status.pack(side="left", padx=10)
        self.apply_btn = ttk.Button(bottom, text="Apply changes",
                                    command=self.apply, state="disabled")
        self.apply_btn.pack(side="right")

    def _combo(self, parent, label, var):
        ttk.Label(parent, text=label + ":").pack(side="left", padx=(0, 4))
        box = ttk.Combobox(parent, textvariable=var, width=24, height=20)
        box.pack(side="left", padx=(0, 14))
        box.bind("<Return>", lambda _e: self.set_genre())
        return box

    # ------------------------------------------------------- genre dropdowns

    def _parent_changed(self, clear):
        self.sub_box.configure(values=self.taxonomy.subs(self.parent_var.get().strip()))
        if clear:
            self.sub_var.set("")
            self.detail_var.set("")
        self._sub_changed(clear=clear)

    def _sub_changed(self, clear):
        self.detail_box.configure(values=self.taxonomy.details(
            self.parent_var.get().strip(), self.sub_var.get().strip()))
        if clear:
            self.detail_var.set("")

    def _chosen_genre(self):
        parent, sub, detail = (v.get().strip() for v in
                               (self.parent_var, self.sub_var, self.detail_var))
        if not parent or (detail and not sub):
            return None
        return join_genre(parent, sub, detail)

    def _update_preview(self):
        genre = self._chosen_genre()
        if genre is None:
            text = "Choose at least a Parent" if not self.parent_var.get().strip() \
                else "Fill in Sub before Sub-sub"
        else:
            text = f"Will set: {genre}"
            if not self.taxonomy.is_known(genre):
                text += "  (new custom genre)"
        self.preview.configure(text=text)

    def _fill_dropdowns(self, genre):
        parts = split_genre(genre) + ["", "", ""]
        self.parent_var.set(parts[0])
        self._parent_changed(clear=False)
        self.sub_var.set(parts[1])
        self._sub_changed(clear=False)
        self.detail_var.set(parts[2])

    # --------------------------------------------------------------- actions

    def browse(self):
        path = filedialog.askdirectory(title="Choose your music folder",
                                       initialdir=self.folder.get() or os.path.expanduser("~"))
        if path:
            self.folder.set(path)
            self.scan()

    def scan(self):
        if self.busy:
            return
        root_dir = os.path.expanduser(self.folder.get().strip())
        if not os.path.isdir(root_dir):
            messagebox.showerror("Genre Retagger", "Please choose a folder that exists.")
            return
        self.entries = []
        self._refresh_table()
        self._set_busy(True, "Scanning…")

        def work():
            try:
                entries = scan_library(
                    root_dir, progress=lambda n, t: self.events.put(("progress", n, t)))
                self.events.put(("scanned", entries))
            except Exception as exc:
                self.events.put(("failed", f"Scan failed: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def _selected(self):
        return [self.entries[int(iid)] for iid in self.tree.selection()]

    def set_genre(self):
        targets = [e for e in self._selected() if not e["status"].startswith("error")]
        if not targets:
            messagebox.showinfo("Genre Retagger", "Select one or more files in the table first "
                                                  "(Ctrl/Cmd-click or Shift-click for several).")
            return
        genre = self._chosen_genre()
        if genre is None:
            messagebox.showinfo("Genre Retagger", "Choose at least a Parent genre, and fill in "
                                                  "Sub before Sub-sub.")
            return
        is_new = self.taxonomy.remember(genre)
        if is_new:
            self.parent_box.configure(values=self.taxonomy.parents())
        for e in targets:
            e["new"] = genre
            e.pop("result", None)
        self._refresh_table(keep_selection=True)
        msg = f"Set “{genre}” on {len(targets)} file(s)."
        if is_new:
            msg += " Saved as a custom genre."
        self._set_busy(False, msg + " Click Apply to write.")

    def clear_genre(self):
        sel = self._selected()
        for e in sel:
            e.pop("new", None)
        self._refresh_table(keep_selection=True)
        self._set_busy(False, f"Cleared the new genre on {len(sel)} file(s).")

    def select_same(self):
        sel = self._selected()
        if not sel:
            return
        current = sel[0]["current"]
        same = [iid for iid in self.tree.get_children()
                if self.entries[int(iid)]["current"] == current]
        self.tree.selection_set(same)
        if same:
            self.tree.see(same[0])

    def apply(self):
        todo = [e for e in self.entries if self._is_pending(e)]
        if self.busy or not todo:
            return
        if not messagebox.askyesno(
                "Apply changes?",
                f"Rewrite the genre tag in {len(todo)} file(s)?\n\n"
                "Files are changed in place. Make sure you have a backup."):
            return
        self._set_busy(True, "Writing tags…")

        def work():
            failed = 0
            for i, e in enumerate(todo, 1):
                self.events.put(("progress", i, len(todo)))
                try:
                    write_genre(MutagenFile(e["path"]), e["new"])
                    e.update(current=e["new"], count=1, status="ok", result="updated")
                    e.pop("new")
                except Exception as exc:
                    e["result"] = f"write failed: {exc}"
                    failed += 1
            self.events.put(("applied", len(todo) - failed, failed))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------- worker messages

    def _poll_events(self):
        try:
            while True:
                self._handle(*self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _handle(self, kind, *args):
        if kind == "progress":
            n, total = args
            self.progress.configure(maximum=max(total, 1), value=n)
        elif kind == "scanned":
            self.entries = args[0]
            self._refresh_table()
            msg = (f"Found {len(self.entries)} file(s). Select files, choose a genre, "
                   "click Set genre, then Apply." if self.entries
                   else "No audio files found in that folder.")
            self._set_busy(False, msg)
        elif kind == "applied":
            updated, failed = args
            self._refresh_table(keep_selection=True)
            self._set_busy(False, f"Done: {updated} file(s) updated"
                                  + (f", {failed} failed." if failed else "."))
            summary = f"Updated: {updated}"
            if failed:
                summary += f"\nFailed to write: {failed} (shown in red)"
            messagebox.showinfo("Genre Retagger", summary)
        elif kind == "failed":
            self._set_busy(False, args[0])
            messagebox.showerror("Genre Retagger", args[0])

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _is_pending(e):
        new = e.get("new")
        return bool(new) and (new != e["current"] or e["count"] > 1)

    def _row(self, e):
        """Return (values, tag) for one table row."""
        new = e.get("new", "")
        result = e.get("result", "")
        if e["status"].startswith("error"):
            return (e["rel"], "—", "", "Unreadable"), "error"
        current = e["current"] or "(none)"
        if result.startswith("write failed"):
            return (e["rel"], current, new, "Write failed"), "error"
        if self._is_pending(e):
            return (e["rel"], current, new, "Will change"), "pending"
        if new:
            return (e["rel"], current, new, "Same as current"), "muted"
        if result == "updated":
            return (e["rel"], current, "", "Updated"), "updated"
        return (e["rel"], current, "", "No genre" if not e["current"] else ""), \
            "muted" if not e["current"] else ""

    def _sort_by(self, col):
        self.sort_reverse = not self.sort_reverse if self.sort_col == col else False
        self.sort_col = col
        self._refresh_table(keep_selection=True)

    def _refresh_table(self, keep_selection=False):
        selected = set(self.tree.selection()) if keep_selection else set()
        self.tree.delete(*self.tree.get_children())
        col_index = {"file": 0, "current": 1, "new": 2, "status": 3}[self.sort_col]
        rows = []
        for i, e in enumerate(self.entries):
            if self.only_pending.get() and not (self._is_pending(e) or e.get("result")):
                continue
            values, tag = self._row(e)
            rows.append((values[col_index].lower(), i, values, tag))
        rows.sort(key=lambda r: (r[0], r[1]), reverse=self.sort_reverse)
        for _key, i, values, tag in rows:
            self.tree.insert("", "end", iid=str(i), values=values, tags=(tag,) if tag else ())
        keep = [iid for iid in selected if self.tree.exists(iid)]
        if keep:
            self.tree.selection_set(keep)

        if self.entries:
            pending = sum(1 for e in self.entries if self._is_pending(e))
            no_genre = sum(1 for e in self.entries if e["status"] == "no genre" and not e.get("new"))
            errors = sum(1 for e in self.entries if e["status"].startswith("error"))
            text = f"{len(self.entries)} files · {pending} to change"
            if no_genre:
                text += f" · {no_genre} no genre"
            if errors:
                text += f" · {errors} unreadable"
            self.counts.configure(text=text)
        else:
            self.counts.configure(text="")

    def _on_select(self, _event=None):
        sel = self._selected()
        if not sel:
            return
        # Pre-fill the dropdowns when every selected file shares one genre that is
        # already in Parent//Sub form (a plain old tag like "Bossa Nova" is not).
        genres = {e.get("new") or e["current"] for e in sel}
        genre = genres.pop() if len(genres) == 1 else ""
        if "//" in genre:
            self._fill_dropdowns(genre)
        n = len(sel)
        self.set_btn.configure(text=f"Set genre on {n} file{'s' if n != 1 else ''}")

    def _set_busy(self, busy, message):
        self.busy = busy
        self.status.configure(text=message)
        self.scan_btn.configure(state="disabled" if busy else "normal")
        can_apply = not busy and any(self._is_pending(e) for e in self.entries)
        self.apply_btn.configure(state="normal" if can_apply else "disabled")
        if not busy:
            self.progress.configure(value=0)


def main():
    root = tk.Tk()
    RetagApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
