#!/usr/bin/env python3
"""Simple window for the genre retagger: pick a folder, preview, apply."""

import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mutagen import File as MutagenFile

from retag_genres import build_plan, write_genre

STATUS_TEXT = {
    "change": "Will update",
    "same": "Already correct",
    "no genre": "No genre — skip",
    "updated": "Updated",
}


class RetagApp:
    def __init__(self, root):
        self.root = root
        self.plan = []
        self.events = queue.Queue()  # worker thread -> UI thread
        self.busy = False

        root.title("Genre Retagger")
        root.geometry("1000x620")
        root.minsize(700, 400)
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
        self.scan_btn = ttk.Button(top, text="Scan (preview)", command=self.scan)
        self.scan_btn.pack(side="left", padx=(6, 0))

        opts = ttk.Frame(self.root)
        opts.pack(fill="x", padx=10)
        self.only_changes = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Show only files that will change",
                        variable=self.only_changes,
                        command=self._refresh_table).pack(side="left")
        self.counts = ttk.Label(opts, text="")
        self.counts.pack(side="right")

        table = ttk.Frame(self.root)
        table.pack(fill="both", expand=True, **pad)
        cols = ("file", "current", "proposed", "status")
        self.tree = ttk.Treeview(table, columns=cols, show="headings")
        for col, title, width in (("file", "File", 360),
                                  ("current", "Current Genre", 180),
                                  ("proposed", "Proposed Genre", 280),
                                  ("status", "Status", 130)):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w")
        self.tree.tag_configure("change", foreground="#0a5c0a")
        self.tree.tag_configure("same", foreground="#777777")
        self.tree.tag_configure("skip", foreground="#777777")
        self.tree.tag_configure("error", foreground="#b00020")
        self.tree.tag_configure("updated", foreground="#0b4f9c")
        ysb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(bottom, mode="determinate", length=220)
        self.progress.pack(side="left")
        self.status = ttk.Label(bottom, text="Choose your music folder, then click Scan. "
                                             "Nothing is changed until you click Apply.")
        self.status.pack(side="left", padx=10)
        self.apply_btn = ttk.Button(bottom, text="Apply changes",
                                    command=self.apply, state="disabled")
        self.apply_btn.pack(side="right")

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
        self.plan = []
        self._refresh_table()
        self._set_busy(True, "Scanning…")

        def work():
            try:
                plan = build_plan(root_dir, progress=lambda n, t: self.events.put(("progress", n, t)))
                self.events.put(("scanned", plan))
            except Exception as exc:
                self.events.put(("failed", f"Scan failed: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def apply(self):
        todo = [e for e in self.plan if e["status"] == "change"]
        if self.busy or not todo:
            return
        if not messagebox.askyesno(
                "Apply changes?",
                f"Rewrite the genre tag in {len(todo)} file(s)?\n\n"
                "Files are changed in place. Make sure you have a backup."):
            return
        self._set_busy(True, "Writing tags…")

        def work():
            failed = []
            for i, e in enumerate(todo, 1):
                self.events.put(("progress", i, len(todo)))
                try:
                    write_genre(MutagenFile(e["path"]), e["proposed"])
                    e["status"] = "updated"
                except Exception as exc:
                    e["status"] = f"error: write failed: {exc}"
                    failed.append(e)
            self.events.put(("applied", len(todo) - len(failed), failed))

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
            self.plan = args[0]
            self._refresh_table()
            changes = self._count("change")
            if not self.plan:
                msg = "No audio files found in that folder."
            elif changes:
                msg = f"Preview ready: {changes} file(s) will change. Review, then click Apply."
            else:
                msg = "Preview ready: nothing to change."
            self._set_busy(False, msg)
        elif kind == "applied":
            updated, failed = args
            self._refresh_table()
            self._set_busy(False, f"Done: {updated} file(s) updated"
                                  + (f", {len(failed)} failed." if failed else "."))
            summary = (f"Updated: {updated}\n"
                       f"Skipped (already correct): {self._count('same')}\n"
                       f"Skipped (no genre found): {self._count('no genre')}")
            if failed:
                summary += f"\nFailed to write: {len(failed)} (shown in red)"
            messagebox.showinfo("Genre Retagger", summary)
        elif kind == "failed":
            self._set_busy(False, args[0])
            messagebox.showerror("Genre Retagger", args[0])

    # --------------------------------------------------------------- helpers

    def _count(self, status):
        return sum(1 for e in self.plan if e["status"] == status)

    def _set_busy(self, busy, message):
        self.busy = busy
        self.status.configure(text=message)
        self.scan_btn.configure(state="disabled" if busy else "normal")
        can_apply = not busy and self._count("change") > 0
        self.apply_btn.configure(state="normal" if can_apply else "disabled")
        if not busy:
            self.progress.configure(value=0)

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for e in self.plan:
            status = e["status"]
            # Keep rows that were changed (or failed to) visible after Apply.
            if (self.only_changes.get() and status not in ("change", "updated")
                    and "write failed" not in status):
                continue
            if status.startswith("error"):
                tag = "error"
                label = "Write failed" if "write failed" in status else "Unreadable"
                current, proposed = e["current"] or "—", e["proposed"] or "—"
            else:
                tag = "skip" if status == "no genre" else status
                label = STATUS_TEXT.get(status, status)
                current = e["current"] or "(none)"
                proposed = e["proposed"] or "—"
            self.tree.insert("", "end", values=(e["rel"], current, proposed, label),
                             tags=(tag,))
        errors = sum(1 for e in self.plan if e["status"].startswith("error"))
        if self.plan:
            text = (f"{len(self.plan)} files · {self._count('change')} to change · "
                    f"{self._count('same')} already correct · "
                    f"{self._count('no genre')} no genre")
            if self._count("updated"):
                text += f" · {self._count('updated')} updated"
            if errors:
                text += f" · {errors} unreadable/failed"
        else:
            text = ""
        self.counts.configure(text=text)


def main():
    root = tk.Tk()
    RetagApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
