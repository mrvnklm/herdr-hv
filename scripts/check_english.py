#!/usr/bin/env python3
"""Fail when German text slips into the repository.

Everything here is English: code, comments, docs, test names and UI strings. The check
looks for umlauts/ß and for common German words as whole words. A line that must stay
German (a legacy label hv still recognises) carries the marker `lang-ok` in a comment.

    scripts/check_english.py                  # all tracked files
    scripts/check_english.py --files a b ...  # just these (pre-commit passes the index)
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {"", ".py", ".md", ".toml", ".sh", ".json", ".yml", ".yaml", ".txt"}
SKIP = {"LICENSE", "scripts/check_english.py"}  # this file lists the words on purpose
WORDS = """
aber alle als auch auf aus bei bis bleibt dann dass dem den der des diese dieser doch durch
eine einem einen einer eines fehlt fehler gibt gruppe gruppen hier immer ist jetzt kein keine
klick kopfzeile mehr mit nach neue neuer nicht noch nur oder ohne schon sich sonst über und
unter vom von vor wenn werden wieder wird zeile zum zur zurück
""".split()
# lowercase or Capitalised, never ALL CAPS: "MIT" is a license, "mit" is German
PATTERN = re.compile(r"[äöüÄÖÜß]|\b(?:%s)\b" % "|".join(w for word in WORDS for w in (word, word.capitalize())))


def tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
    return out.split()


def check(paths):
    hits = []
    for rel in paths:
        path = ROOT / rel
        if rel in SKIP or path.suffix not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            if "lang-ok" in line:
                continue
            match = PATTERN.search(line)
            if match:
                hits.append(f"{rel}:{number}: {match.group(0)!r} in: {line.strip()[:100]}")
    return hits


def main(argv):
    paths = argv[argv.index("--files") + 1:] if "--files" in argv else tracked()
    hits = check(paths)
    for hit in hits:
        print(hit)
    if hits:
        print(f"check_english: {len(hits)} German line(s); write English or mark with lang-ok")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
