"""Genre choices for the GUI dropdowns: Parent // Sub // Sub-sub.

Built from the tags in genre_classifier.RULES plus any custom genres the user
has added, which are saved to ~/.genre_retagger_custom.json (override with the
GENRE_RETAGGER_CUSTOM environment variable).
"""

import json
import os

from genre_classifier import RULES

SEP = "//"
CUSTOM_FILE = os.environ.get(
    "GENRE_RETAGGER_CUSTOM",
    os.path.join(os.path.expanduser("~"), ".genre_retagger_custom.json"))


def split_genre(genre):
    """Split "A//B//C" into at most three parts.

    Deeper genres keep the parent, sub and most specific level, e.g.
    "Dance//Trance//Psytrance//Goa" -> ["Dance", "Trance", "Goa"].
    """
    parts = [p.strip() for p in genre.split(SEP) if p.strip()]
    if len(parts) > 3:
        parts = [parts[0], parts[1], parts[-1]]
    return parts


def join_genre(parent, sub="", detail=""):
    return SEP.join(p.strip() for p in (parent, sub, detail) if p.strip())


class Taxonomy:
    def __init__(self, custom_file=CUSTOM_FILE):
        self.custom_file = custom_file
        self.tree = {}  # parent -> {sub -> set(detail)}
        for _pattern, tag in RULES:
            self._add(split_genre(tag))
        self.custom = self._load()
        for genre in self.custom:
            self._add(split_genre(genre))

    def _add(self, parts):
        if not parts:
            return
        subs = self.tree.setdefault(parts[0], {})
        if len(parts) > 1:
            details = subs.setdefault(parts[1], set())
            if len(parts) > 2:
                details.add(parts[2])

    def _load(self):
        try:
            with open(self.custom_file, encoding="utf-8") as f:
                data = json.load(f)
            return [g for g in data if isinstance(g, str)]
        except (OSError, ValueError):
            return []

    def parents(self):
        return sorted(self.tree, key=str.lower)

    def subs(self, parent):
        return sorted(self.tree.get(parent, {}), key=str.lower)

    def details(self, parent, sub):
        return sorted(self.tree.get(parent, {}).get(sub, ()), key=str.lower)

    def is_known(self, genre):
        parts = split_genre(genre)
        if not parts or parts[0] not in self.tree:
            return False
        if len(parts) > 1 and parts[1] not in self.tree[parts[0]]:
            return False
        if len(parts) > 2 and parts[2] not in self.tree[parts[0]][parts[1]]:
            return False
        return True

    def remember(self, genre):
        """Add a custom genre and save it. Returns True if it was new."""
        if self.is_known(genre):
            return False
        self._add(split_genre(genre))
        self.custom.append(genre)
        try:
            with open(self.custom_file, "w", encoding="utf-8") as f:
                json.dump(sorted(set(self.custom)), f, indent=1, ensure_ascii=False)
        except OSError:
            pass  # still usable for this session
        return True
