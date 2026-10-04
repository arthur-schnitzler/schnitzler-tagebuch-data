#!/usr/bin/env python3
"""PreToolUse-Hook des Skills »personen-auszeichnen«: XML-Daten werden nur über `pa.py apply` geändert.

Geschützt (nur Schreiben, Lesen bleibt frei):
  editions/*.xml, indices/index_person_day.xml, indices/implied-persons.txt

  Edit, Write, MultiEdit, NotebookEdit   verweigert, wenn das Ziel eine geschützte Datei ist
  Bash                                   Heuristik: Umleitungen, sed/perl -i, tee, mv/cp/rm/touch, Python-Schreib-
                                         zugriffe und zerstörende git-Befehle, sofern das Kommando eine geschützte
                                         Datei oder den Ordner editions/ nennt. Teilkommandos, die `pa.py` aufrufen,
                                         sind der erlaubte Schreibweg und werden nicht beanstandet.

Warum: Der Applier hält Sicherungen ein (Textgleichheit, nur Hinzufügungen, Tag- und ID-Prüfung), die ein direkter
Edit umgehen würde. Der Hook ist ein Sicherheitsnetz gegen Versehen, kein Zaun gegen Absicht; `pa.py verify`
prüft nach dem Lauf den Arbeitsstand gegen git HEAD.

Protokoll: JSON auf stdin (tool_name, tool_input, cwd); Verweigerung als JSON auf stdout, Exit 0.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

GRUND = ("Skill personen-auszeichnen: Die Daten in editions/ und indices/index_person_day.xml (sowie "
         "indices/implied-persons.txt) werden nur über `python3 .claude/skills/personen-auszeichnen/scripts/pa.py "
         "apply` geändert, weil nur der Applier Textgleichheit und Nur-Hinzufügen sichert. Direkte Edits sind gesperrt; "
         "Entscheidungen stehen in einer JSON-Datei unter temp/personen-auszeichnen/.")

GESCHUETZT_REL = ("indices/index_person_day.xml", "indices/implied-persons.txt")
SCHREIB_UMLEITUNG = re.compile(r">>?\s*[\"']?[^\s\"'|;&<>]*(?:editions/|index_person_day\.xml|implied-persons\.txt)")
INPLACE = re.compile(r"\b(?:sed|perl|ruby)\b[^|;&\n]*\s-[A-Za-z]*i\b|--in-place|\bawk\b[^|;&\n]*inplace")
ZIEL = r"[^)]*?(?:editions/|index_person_day\.xml|implied-persons\.txt)"
PYTHON_SCHREIBT = [
    re.compile(rf"open\(\s*{ZIEL}[^)]*?,\s*['\"][^'\"]*[wax+]"),
    re.compile(rf"Path\({ZIEL}[^)]*\)\.(?:write_text|write_bytes|unlink|rename|replace|touch)\("),
    re.compile(rf"(?:os\.(?:rename|replace|remove|unlink)|shutil\.(?:move|rmtree))\({ZIEL}"),
    re.compile(rf"\.write\(\s*{ZIEL}"),
]
GIT_IMMER = {"clean", "stash", "restore", "rm", "mv", "apply", "am"}


def verweigern(grund=GRUND):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": grund}}, ensure_ascii=False))
    sys.exit(0)


def repo_wurzel(daten):
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(os.path.realpath(env))
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "editions").is_dir():
            return p
    return Path(os.path.realpath(daten.get("cwd") or "."))


def ist_geschuetzt(pfad, cwd, repo):
    if not pfad:
        return False
    q = Path(pfad)
    if not q.is_absolute():
        q = Path(cwd) / q
    q = Path(os.path.realpath(q))
    if not (q == repo or repo in q.parents):
        return False
    rel = q.relative_to(repo).as_posix()
    return (rel.startswith("editions/") and q.suffix.lower() == ".xml") or rel in GESCHUETZT_REL


def geschuetzter_pfad(wort, cwd, repo):
    if not wort or wort.startswith("-"):
        return False
    if ist_geschuetzt(wort, cwd, repo):
        return True
    q = Path(wort)
    if not q.is_absolute():
        q = Path(cwd) / q
    q = Path(os.path.realpath(q))
    return q == repo / "editions"


def teilkommandos(cmd):
    for stueck in re.split(r"&&|\|\||[;|\n]", cmd):
        try:
            yield stueck, shlex.split(stueck)
        except ValueError:
            yield stueck, stueck.split()


def bash_verdacht(cmd, cwd, repo):
    """Grund für die Verweigerung oder None. `pa.py`-Aufrufe sind der erlaubte Schreibweg."""
    for stueck, w in teilkommandos(cmd):
        if not w or "personen-auszeichnen/scripts/pa.py" in stueck or re.search(r"\bpa\.py\b", stueck):
            continue
        if SCHREIB_UMLEITUNG.search(stueck):
            return "Umleitung in eine geschützte Datei"
        if re.search(r"editions/|index_person_day\.xml|implied-persons\.txt", stueck) and INPLACE.search(stueck):
            return "Bearbeitung einer geschützten Datei an Ort und Stelle (sed/perl -i)"
        if re.search(r"\b(?:python3?|node|ruby|perl)\b", stueck) and any(r.search(stueck) for r in PYTHON_SCHREIBT):
            return "Skript, das geschützte Dateien schreibt"
        name = os.path.basename(w[0])
        args = [a for a in w[1:] if not a.startswith("-")]
        if name == "tee" and any(geschuetzter_pfad(a, cwd, repo) for a in args):
            return "tee in eine geschützte Datei"
        if name in {"rm", "unlink", "shred", "truncate", "touch", "mv"} and any(geschuetzter_pfad(a, cwd, repo) for a in args):
            return f"{name} auf eine geschützte Datei"
        if name in {"cp", "install", "ln", "rsync"} and args and geschuetzter_pfad(args[-1], cwd, repo):
            return f"{name} mit geschützter Datei als Ziel"
        if name == "git" and len(w) > 1:
            sub = next((a for a in w[1:] if not a.startswith("-")), "")
            rest = w[w.index(sub) + 1:] if sub in w else []
            if sub in GIT_IMMER:
                return f"git {sub} kann Dateien im Arbeitsverzeichnis ändern"
            if sub == "reset" and "--hard" in rest:
                return "git reset --hard verwirft Änderungen"
            if sub in {"checkout", "switch"} and ("--" in rest or "." in rest or any(geschuetzter_pfad(a, cwd, repo) for a in rest)):
                return f"git {sub} kann Dateien zurücksetzen"
    return None


def main():
    try:
        daten = json.load(sys.stdin)
    except Exception:
        return
    werkzeug = daten.get("tool_name", "")
    eingabe = daten.get("tool_input") or {}
    cwd = daten.get("cwd") or os.getcwd()
    try:
        repo = repo_wurzel(daten)
        if werkzeug in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
            pfad = eingabe.get("file_path") or eingabe.get("notebook_path")
            if ist_geschuetzt(pfad, cwd, repo):
                verweigern()
        elif werkzeug == "Bash":
            grund = bash_verdacht(eingabe.get("command") or "", cwd, repo)
            if grund:
                verweigern(f"{GRUND} (Anlass: {grund}.)")
    except SystemExit:
        raise
    except Exception:
        roh = json.dumps(eingabe, ensure_ascii=False)
        if werkzeug in {"Edit", "Write", "MultiEdit", "NotebookEdit"} and ("editions/" in roh or "index_person_day" in roh):
            verweigern()


if __name__ == "__main__":
    main()
