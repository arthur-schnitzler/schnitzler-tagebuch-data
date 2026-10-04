#!/usr/bin/env python3
"""Helfer des Skills »personen-auszeichnen« (Tagebuch-Daten, editions/entry__YYYY-MM-DD.xml).

Aufruf aus dem Repo-Wurzelverzeichnis:  python3 .claude/skills/personen-auszeichnen/scripts/pa.py <Befehl> …

  scan <Bereich> [--aufgaben 1,2,3]   Arbeitspaket für Claude: Tage mit Arbeit, Kandidaten, Prüfbefunde
                                      (liest nur; schreibt nach temp/personen-auszeichnen/<Bereich>/)
  apply <entscheidungen.json> …       der EINZIGE Schreibweg in editions/ und indices/ (Trockenlauf: --dry-run)
  verify [Bereich]                    prüft den Arbeitsstand gegen git HEAD (nur Hinzufügungen, Textgleichheit, …)
  bericht <Bereich>                   fasst Protokoll und offene Punkte zu bericht.md zusammen
  namensformen [--person pmbN]        zeigt, was aus dem Korpus gelernt wurde (Namensformen, allusively-Zuordnung)
  implied-liste                       zeigt indices/implied-persons.txt

Ein Bereich ist ein Tag (1902-07-02), ein Monat (1902-07), ein Jahr (1902), ein Zeitraum (1902-07..1902-09) oder »alle«.

Arbeitsweise: Der Helfer liest und schreibt die XML-Dateien im Rohtext (Regex-Tokenizer), nie über
Parser und Serialisierer. Dadurch bleiben Zeilenumbrüche, xml:space="preserve" und Einrückung unangetastet
und der Git-Diff enthält nur die eingefügten Tags und Attribute.
"""

from __future__ import annotations

import argparse
import bisect
import collections
import csv
import datetime as dt
import hashlib
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from lxml import etree

TEI = "http://www.tei-c.org/ns/1.0"
NS = {"t": TEI}
XMLID = "{http://www.w3.org/XML/1998/namespace}id"
HIER = Path(__file__).resolve().parent


class PaError(Exception):
    def __init__(self, msg, code="fehler"):
        super().__init__(msg)
        self.code = code


# ----------------------------------------------------------------------------------------------
# Repo und Pfade
# ----------------------------------------------------------------------------------------------

class Repo:
    def __init__(self, root):
        self.root = Path(root)
        self.editions = self.root / "editions"
        self.indices = self.root / "indices"
        self.listperson = self.indices / "listperson.xml"
        self.index = self.indices / "index_person_day.xml"
        self.implied = self.indices / "implied-persons.txt"
        self.haushalte = HIER.parent / "references" / "haushalte.md"
        self.temp = self.root / "temp" / "personen-auszeichnen"
        self.verw_dir = HIER.parent / "data"                      # gekürzte PMB-Relationen (Verwandtschaft)
        self.verw_relationen = self.verw_dir / "verwandtschaft-relationen.csv"
        self.verw_personen = self.verw_dir / "verwandtschaft-personen.xml"
        self.verw_quelle = self.verw_dir / "verwandtschaft-quelle.json"
        self.pmb_quelle = self.root / "temp-indices"             # ungekürzte PMB-Dateien (relations.csv, listperson.xml)
        self.lauf = HIER.parent / "lauf"                          # Spuren eines Gesamtlaufs: Entscheidungen, Berichte, Fortschritt

    def entry(self, tag):
        return self.editions / f"entry__{tag}.xml"


def _finde_wurzel():
    env = os.environ.get("PA_REPO")
    if env:
        return Path(env)
    for p in HIER.parents:
        if (p / "editions").is_dir() and (p / "indices").is_dir():
            return p
    return Path.cwd()


R = Repo(_finde_wurzel())

TAG_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
REF_RE = re.compile(r"(pmb\d+|implied-person_\d+)")


def lies(path):
    return Path(path).read_bytes().decode("utf-8")


def schreibe(path, text):
    """Atomar schreiben, Zeilenenden unverändert lassen."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, path)


# ----------------------------------------------------------------------------------------------
# Roh-Tokenizer und Dokumentmodell
# ----------------------------------------------------------------------------------------------

_NAME = r"[A-Za-z_][\w:.\-]*"
_TOKEN_RE = re.compile(
    r"(?P<comment><!--.*?-->)|(?P<pi><\?.*?\?>)|(?P<cdata><!\[CDATA\[.*?\]\]>)|(?P<decl><![A-Za-z][^>]*>)"
    rf"|(?P<end></(?P<endname>{_NAME})\s*>)"
    rf"|(?P<start><(?P<name>{_NAME})(?P<attrs>(?:\s+{_NAME}\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)\s*(?P<selfclose>/?)>)"
    r"|(?P<text>[^<]+)",
    re.S,
)
_ATTR_RE = re.compile(rf"({_NAME})\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")
_ENT_RE = re.compile(r"&(#[0-9]+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]*);")
_NAMED_ENT = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}

# In diesen Elementen entstehen keine neuen Personen-rs (Text ist bereits ausgezeichnet oder keine Prosa).
GESPERRT = frozenset({"rs", "date", "persName", "placeName", "name", "orgName", "bibl", "fw", "forename",
                      "surname", "roleName", "title", "ref", "note", "head", "num", "measure"})


def dekodiere(raw):
    """-> (Text, Offsets). Offsets[i] ist die Rohposition des i-ten Zeichens, Offsets[len] = len(raw).
    Ohne Entitäten ist Offsets None (Identität)."""
    if "&" not in raw:
        return raw, None
    out, offs, i = [], [], 0
    for m in _ENT_RE.finditer(raw):
        for k in range(i, m.start()):
            out.append(raw[k])
            offs.append(k)
        ref = m.group(1)
        if ref.startswith("#x"):
            ch = chr(int(ref[2:], 16))
        elif ref.startswith("#"):
            ch = chr(int(ref[1:]))
        elif ref in _NAMED_ENT:
            ch = _NAMED_ENT[ref]
        else:
            raise PaError(f"unbekannte Entität &{ref};", "tokenizer")
        out.append(ch)
        offs.append(m.start())
        i = m.end()
    for k in range(i, len(raw)):
        out.append(raw[k])
        offs.append(k)
    offs.append(len(raw))
    return "".join(out), offs


class El:
    __slots__ = ("idx", "name", "attrs", "attr_end", "s_tok", "e_tok", "parent", "start", "end", "fs", "fe",
                 "spans")

    def __init__(self, idx, name, attrs, spans, attr_end, s_tok, parent, start):
        self.idx, self.name, self.attrs, self.spans, self.attr_end = idx, name, attrs, spans, attr_end
        self.s_tok = self.e_tok = s_tok
        self.parent = parent
        self.start = start
        self.end = start
        self.fs = self.fe = None


class Seg:
    __slots__ = ("tok", "fs", "fe", "raw_start", "offs", "parent", "eligible")

    def __init__(self, tok, fs, fe, raw_start, offs, parent, eligible):
        self.tok, self.fs, self.fe, self.raw_start, self.offs = tok, fs, fe, raw_start, offs
        self.parent, self.eligible = parent, eligible

    def raw_pos(self, flat_i):
        k = flat_i - self.fs
        return self.raw_start + (k if self.offs is None else self.offs[k])


class Anker:
    __slots__ = ("seg", "a", "b", "raw_a", "raw_b", "text")


class Doc:
    """Eine Tagebuchdatei im Rohtext mit Elementbaum, Textfluss (flat) und Segmenten."""

    def __init__(self, raw, name=""):
        self.raw, self.name = raw, name
        self.toks = []          # (Art, Start, Ende, Verweis)  Verweis: Element-Nr. bzw. Eltern-Nr.
        self.els = []
        stack = []
        pos = 0
        for m in _TOKEN_RE.finditer(raw):
            s, e = m.start(), m.end()
            if s != pos:
                raise PaError(f"{name}: unlesbare Stelle bei Zeichen {pos}", "tokenizer")
            pos = e
            top = stack[-1] if stack else -1
            if m.group("text") is not None:
                self.toks.append(("text", s, e, top))
            elif m.group("start") is not None:
                astr = m.group("attrs")
                base = m.start("attrs")
                attrs, spans = {}, {}
                last = base
                for am in _ATTR_RE.finditer(astr):
                    attrs[am.group(1)] = am.group(2) if am.group(2) is not None else am.group(3)
                    spans[am.group(1)] = base + am.end()
                    last = base + am.end()
                if not attrs:
                    last = m.start("name") + len(m.group("name"))
                el = El(len(self.els), m.group("name"), attrs, spans, last, len(self.toks), top, s)
                self.els.append(el)
                if m.group("selfclose"):
                    el.end = e
                    self.toks.append(("empty", s, e, el.idx))
                else:
                    self.toks.append(("start", s, e, el.idx))
                    stack.append(el.idx)
            elif m.group("end") is not None:
                if not stack or self.els[stack[-1]].name != m.group("endname"):
                    raise PaError(f"{name}: Endtag </{m.group('endname')}> bei Zeichen {s} passt nicht", "tokenizer")
                el = self.els[stack.pop()]
                el.e_tok = len(self.toks)
                el.end = e
                self.toks.append(("end", s, e, el.idx))
            elif m.group("cdata") is not None:
                raise PaError(f"{name}: CDATA wird nicht unterstützt", "tokenizer")
            else:
                self.toks.append(("other", s, e, top))
        if pos != len(raw):
            raise PaError(f"{name}: unlesbare Stelle bei Zeichen {pos}", "tokenizer")
        if stack:
            raise PaError(f"{name}: Element <{self.els[stack[-1]].name}> nicht geschlossen", "tokenizer")
        self._baue_fluss()

    # -- Aufbau -----------------------------------------------------------------------------
    def _vorfahren(self, idx):
        while idx >= 0:
            yield self.els[idx]
            idx = self.els[idx].parent

    def _baue_fluss(self):
        self.body = None
        for el in self.els:
            if el.name == "body" and any(a.name == "text" for a in self._vorfahren(el.parent)):
                self.body = el
                break
        self.segs, parts, pos = [], [], 0
        self.by_id = {}
        if self.body is None:
            self.flat, self._seg_fs = "", []
            return
        b = self.body
        b.fs = 0
        for i in range(b.s_tok + 1, b.e_tok):
            kind, s, e, ref = self.toks[i]
            if kind == "text":
                dec, offs = dekodiere(self.raw[s:e])
                ok = not any(a.name in GESPERRT for a in self._vorfahren(ref))
                self.segs.append(Seg(i, pos, pos + len(dec), s, offs, ref, ok))
                parts.append(dec)
                pos += len(dec)
            elif kind in ("start", "empty"):
                el = self.els[ref]
                el.fs = pos
                if kind == "empty":
                    el.fe = pos
                xid = el.attrs.get("xml:id")
                if xid:
                    self.by_id.setdefault(xid, []).append(el.idx)
            elif kind == "end":
                self.els[ref].fe = pos
        b.fe = pos
        self.flat = "".join(parts)
        self._seg_fs = [sg.fs for sg in self.segs]

    # -- Abfragen ---------------------------------------------------------------------------
    def text_von(self, el):
        return self.flat[el.fs:el.fe]

    def im_body(self, el):
        return self.body is not None and el.fs is not None

    def elemente(self, name):
        return [el for el in self.els if el.name == name and self.im_body(el)]

    def finde_id(self, xid):
        ids = self.by_id.get(xid, [])
        if not ids:
            raise PaError(f"{self.name}: xml:id {xid} nicht im body gefunden", "id")
        if len(ids) > 1:
            raise PaError(f"{self.name}: xml:id {xid} kommt in der Datei mehrfach vor", "id")
        return self.els[ids[0]]

    def umgebung(self, a, b, n=40):
        return self.flat[max(0, a - n):a], self.flat[a:b], self.flat[b:b + n]

    def treffer(self, text, vorher="", nachher="", teilwort=False, bereits_ref=None):
        """Alle Fundstellen von vorher|text|nachher im Textfluss, sortiert nach Eignung:
        -> (freie [(Seg, a, b)], Zahl über Elementgrenze, Zahl in ausgezeichnetem Text, Zahl schon mit ref)."""
        s = vorher + text + nachher
        flat = self.flat
        frei, grenze, gesperrt, erledigt = [], 0, 0, 0
        i = flat.find(s)
        while i >= 0:
            a = i + len(vorher)
            b = a + len(text)
            nxt = flat.find(s, i + 1)
            if not teilwort and ((a > 0 and flat[a - 1].isalnum()) or (b < len(flat) and flat[b].isalnum())):
                i = nxt
                continue
            k = bisect.bisect_right(self._seg_fs, a) - 1
            seg = self.segs[k] if k >= 0 else None
            if bereits_ref and seg is not None and self._schon_mit_ref(seg, bereits_ref, a, b):
                erledigt += 1
                gesperrt += 1
            elif seg is None or b > seg.fe:
                grenze += 1
            elif not seg.eligible:
                gesperrt += 1
            else:
                frei.append((seg, a, b))
            i = nxt
        return frei, grenze, gesperrt, erledigt

    def finde_anker(self, text, vorher="", nachher="", nr=None, teilwort=False, bereits_ref=None):
        """Löst vorher|text|nachher auf. Der Treffer muss in einem einzigen, noch nicht ausgezeichneten
        Textknoten liegen. Gibt Anker zurück, oder None, wenn der Text schon mit einem rs der gewünschten
        Refs ausgezeichnet ist (bereits_ref)."""
        if not text:
            raise PaError("Anker ohne Text", "anker")
        frei, grenze, gesperrt, erledigt = self.treffer(text, vorher, nachher, teilwort, bereits_ref)
        if nr:
            if not (1 <= nr <= len(frei)):
                raise PaError(f"Anker »{text}«: nr={nr}, aber nur {len(frei)} freie Treffer", "anker")
            frei = [frei[nr - 1]]
        if len(frei) == 1:
            sg, a, b = frei[0]
            an = Anker()
            an.seg, an.a, an.b, an.text = sg, a, b, text
            an.raw_a, an.raw_b = sg.raw_pos(a), sg.raw_pos(b)
            return an
        if not frei and erledigt:
            return None
        if not frei:
            why = []
            if gesperrt:
                why.append(f"{gesperrt}× in bereits ausgezeichnetem Text")
            if grenze:
                why.append(f"{grenze}× über eine Elementgrenze")
            raise PaError(f"Anker »{text}« nicht gefunden" + (f" ({', '.join(why)})" if why else ""), "anker")
        raise PaError(f"Anker »{text}« mehrdeutig ({len(frei)} freie Treffer; vorher/nachher oder nr angeben)", "anker")

    def anker_fuer(self, a, b, teilwort=False):
        """Kürzester eindeutiger Anker (text, vorher, nachher[, nr]) für die Textflussstelle [a, b)."""
        text = self.flat[a:b]
        for n in (0, 4, 8, 14, 24, 40, 80):
            vor = self.flat[max(0, a - n):a]
            nach = self.flat[b:b + n]
            frei, _, _, _ = self.treffer(text, vor, nach, teilwort)
            if len(frei) == 1 and frei[0][1] == a:
                d = {"text": text}
                if vor:
                    d["vorher"] = vor
                if nach:
                    d["nachher"] = nach
                if teilwort:
                    d["teilwort"] = True
                return d
        frei, _, _, _ = self.treffer(text, "", "", teilwort)
        for k, (_, x, _) in enumerate(frei, 1):
            if x == a:
                d = {"text": text, "nr": k}
                if teilwort:
                    d["teilwort"] = True
                return d
        return None

    def _schon_mit_ref(self, seg, refs, a, b):
        """Liegt [a, b) schon vollständig in einem rs, das alle refs trägt?"""
        for el in self._vorfahren(seg.parent):
            if el.name == "rs" and el.attrs.get("ref") and el.fs is not None and el.fs <= a and b <= el.fe:
                if set(refs) <= {r.lstrip("#") for r in el.attrs["ref"].split()}:
                    return True
        return False


# ----------------------------------------------------------------------------------------------
# Eingabe: Bereiche
# ----------------------------------------------------------------------------------------------

def alle_tage():
    return sorted(p.stem[7:] for p in R.editions.glob("entry__*.xml"))


def bereich_tage(spec):
    tage = alle_tage()
    spec = (spec or "").strip()
    if spec in ("", "alle"):
        return tage
    if ".." in spec:
        lo, hi = spec.split("..", 1)
        return [t for t in tage if t >= lo and (t <= hi or t.startswith(hi))]
    return [t for t in tage if t.startswith(spec)]


def bereich_name(tage, spec=None):
    """Ordnername eines Bereichs: die Angabe selbst, wenn sie ein Tag, Monat oder Jahr ist (so heißt der Ordner auch bei einem
    Monat mit nur einem Eintrag), sonst aus den Tagen abgeleitet (Zeitraum, »alle«)."""
    if spec and re.fullmatch(r"\d{4}(-\d{2}){0,2}", spec.strip()):
        return spec.strip()
    if not tage:
        return "leer"
    if len(tage) == 1:
        return tage[0]
    for n in (7, 4):
        if len({t[:n] for t in tage}) == 1:
            return tage[0][:n]
    return f"{tage[0]}..{tage[-1]}"


# ----------------------------------------------------------------------------------------------
# Kennungen, implied-Liste
# ----------------------------------------------------------------------------------------------

class Ids:
    """Nächste freie xml:id: pNt_ (Personen) und rst_ (allusively), je globales Maximum + 1."""

    def __init__(self):
        self.letzte = {"pNt": 0, "rst": 0}
        rx = re.compile(r'xml:id="(pNt|rst)_(\d+)"')
        for f in R.editions.glob("entry__*.xml"):
            for pre, n in rx.findall(lies(f)):
                if int(n) > self.letzte[pre]:
                    self.letzte[pre] = int(n)

    def neu(self, pre):
        self.letzte[pre] += 1
        return f"{pre}_{self.letzte[pre]:05d}"


class ImpliedListe:
    """indices/implied-persons.txt: Zeilen »implied-person_N|?? [Beschreibung]«."""

    ZEILE = re.compile(r"^(implied-person_(\d+))\|\s*(\?\?|pmb\d+)\s*\[(.+)\]\s*$")

    def __init__(self, pfad=None):
        self.pfad = Path(pfad or R.implied)
        self.zeilen = lies(self.pfad).splitlines() if self.pfad.exists() else []
        self.eintraege = {}     # id -> (pmb, beschreibung)
        self.nach_text = {}     # normierte Beschreibung -> id
        self.max = 0
        self.neue = []
        for z in self.zeilen:
            m = self.ZEILE.match(z)
            if m:
                self.eintraege[m.group(1)] = (m.group(3), m.group(4))
                self.nach_text[self._norm(m.group(4))] = m.group(1)
                self.max = max(self.max, int(m.group(2)))

    @staticmethod
    def _norm(s):
        return re.sub(r"\s+", " ", s).strip().lower()

    def ids(self):
        return set(self.eintraege)

    def holen(self, beschreibung):
        """Id zur Beschreibung; legt sie an, wenn es sie noch nicht gibt. Gibt (id, neu) zurück."""
        beschreibung = re.sub(r"\s+", " ", beschreibung).strip()
        if not beschreibung or "[" in beschreibung or "]" in beschreibung or "|" in beschreibung:
            raise PaError(f"ungültige Beschreibung für implied-person: »{beschreibung}«", "implied")
        k = self._norm(beschreibung)
        if k in self.nach_text:
            return self.nach_text[k], False
        self.max += 1
        pid = f"implied-person_{self.max}"
        self.eintraege[pid] = ("??", beschreibung)
        self.nach_text[k] = pid
        self.zeilen.append(f"{pid}|?? [{beschreibung}]")
        self.neue.append((pid, beschreibung))
        return pid, True

    def speichern(self):
        if self.neue:
            self.pfad.parent.mkdir(parents=True, exist_ok=True)
            schreibe(self.pfad, "\n".join(self.zeilen) + "\n")


# ----------------------------------------------------------------------------------------------
# Index (index_person_day.xml) im Rohtext bearbeiten
# ----------------------------------------------------------------------------------------------

_ITEM_RE = re.compile(r'^([ \t]*)<item target="([^"]+)"\s*(/?)>[ \t]*\n?', re.M)
_IREF_RE = re.compile(r"<ref([^>]*)>([^<]*)</ref>")


def lies_index(raw=None):
    """-> {Tag: [(ref, implied?)]} aus dem Rohtext."""
    raw = raw if raw is not None else lies(R.index)
    out = {}
    for m in _ITEM_RE.finditer(raw):
        refs = []
        if not m.group(3):
            close = raw.find("</item>", m.end())
            for rm in _IREF_RE.finditer(raw[m.end():close]):
                refs.append((rm.group(2).strip(), 'ana="implied"' in rm.group(1)))
        out[m.group(2)] = refs
    return out


def index_ergaenzen(raw, adds):
    """adds: {Tag: [(ref, implied)]}. Fügt fehlende Refs ans Ende des Tages-Items ein, legt fehlende Items
    in Datumsreihenfolge an. Gibt (neuer Rohtext, Liste der tatsächlich eingefügten (Tag, ref, implied))."""
    items = []   # (Tag, Zeilenanfang, Zeilenende nach </item>, Refs, Einrückung der Refs, Zeilenanfang des </item>)
    for m in _ITEM_RE.finditer(raw):
        if m.group(3):
            items.append((m.group(2), m.start(), m.end(), None, None, None, m.group(1)))
            continue
        close = raw.find("</item>", m.end())
        body = raw[m.end():close]
        refs = {rm.group(2).strip() for rm in _IREF_RE.finditer(body)}
        im = re.search(r"^([ \t]+)<ref", body, re.M)
        ind = im.group(1) if im else m.group(1) + "   "
        ls = raw.rfind("\n", 0, close) + 1
        ende = raw.find("\n", close)
        ende = len(raw) if ende < 0 else ende + 1
        items.append((m.group(2), m.start(), ende, refs, ind, ls, m.group(1)))
    tage = [it[0] for it in items]
    eingefuegt, ins = [], []
    for tag in sorted(adds):
        neue = []
        for ref, impl in adds[tag]:
            if tag in tage:
                it = items[tage.index(tag)]
                if it[3] is not None and ref in it[3]:
                    continue
            if any(ref == r for r, _ in neue):
                continue
            neue.append((ref, impl))
        if not neue:
            continue
        zeilen = lambda ind: "".join(
            f'{ind}<ref ana="implied">{r}</ref>\n' if impl else f"{ind}<ref>{r}</ref>\n" for r, impl in neue)
        if tag in tage:
            it = items[tage.index(tag)]
            if it[3] is None:      # <item target="…"/>
                bl = f'{it[6]}<item target="{tag}">\n{zeilen(it[6] + "   " * 2)}{it[6]}</item>\n'
                ins.append((it[1], it[2], bl))
            else:
                if raw[it[5]:raw.find("</item>", it[5])].strip():
                    raise PaError(f"index_person_day.xml: Item {tag} hat </item> nicht in einer eigenen Zeile", "index")
                ins.append((it[5], it[5], zeilen(it[4])))
        else:
            k = bisect.bisect_left(tage, tag)
            ind0 = items[0][6] if items else "   "
            bl = f'{ind0}<item target="{tag}">\n{zeilen(ind0 + "   ")}{ind0}</item>\n'
            if k < len(items):
                pos = items[k][1]
            else:
                pos = raw.rfind("</list>")
                pos = raw.rfind("\n", 0, pos) + 1
            ins.append((pos, pos, bl))
        eingefuegt += [(tag, r, i) for r, i in neue]
    out, last = [], 0
    for a, b, text in sorted(ins, key=lambda x: x[0]):
        out.append(raw[last:a])
        out.append(text)
        last = b
    out.append(raw[last:])
    return "".join(out), eingefuegt


# ----------------------------------------------------------------------------------------------
# Namensmodell (PMB-Personen)
# ----------------------------------------------------------------------------------------------

PARTIKEL = frozenset({"von", "v.", "van", "de", "zu", "der", "la", "le", "di", "da", "del", "y", "vom", "zum", "zur"})
TITEL = frozenset({
    "frau", "herr", "frl", "fräulein", "fr", "dr", "prof", "hofr", "hofrat", "hofrätin", "baron", "baronin",
    "graf", "gräfin", "exc", "excellenz", "hr", "fürst", "fürstin", "dir", "direktor", "director", "doctor",
    "doktor", "prinz", "prinzessin", "herzog", "herzogin", "erzherzog", "erzherzogin", "pater", "mme", "madame",
    "mr", "mrs", "miss", "sig", "signor", "signora", "kaiser", "kaiserin", "könig", "königin", "frauen", "herren",
    "ing", "mag", "med", "phil", "jur", "hofschauspieler", "hofschauspielerin", "schauspielerin", "schauspieler",
    "regisseur", "kapellmeister", "primarius", "professor", "docent", "dozent", "oberst", "major", "hauptmann",
    "leutnant", "lieutenant", "gen", "general", "rittmeister", "rat", "sektionschef", "minister", "bürgermeister"})
_PUNKT = " \t\n.,;:!?()[]{}»«„“”‚‘’'\"―–—"


def fold(s):
    s = s.lower().replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("ph", "f").replace("th", "t").replace("ck", "k").replace("c", "k").replace("y", "i")


def woerter(s):
    """Wörter einer Oberfläche/eines Namens; Bindestrich trennt, Satzzeichen an den Rändern fallen weg,
    ein Schlusspunkt (Abkürzung: »Rich.«, »Sigm.«) bleibt erhalten."""
    out = []
    for w in re.split(r"[\s\-‐]+", s):
        k = w.strip(_PUNKT)
        if not k:
            continue
        if w.rstrip(" ,;:!?)]»“”’'\"―–—").endswith("."):
            k += "."
        out.append(k)
    return out


def ist_titel(w):
    k = fold(w.strip(_PUNKT))
    return k in {fold(t) for t in TITEL}


def ist_partikel(w):
    return w.lower().strip(_PUNKT + ".") in {p.strip(".") for p in PARTIKEL}


def _ed1(a, b):
    """Editierabstand <= 1 (Ersetzung, Einfügung, Löschung, Vertauschung)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        d = [i for i in range(la) if a[i] != b[i]]
        return len(d) == 1 or (len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]])
    if la > lb:
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


class Person:
    __slots__ = ("pid", "vor", "nach", "varianten", "sex", "geb", "tod", "beruf", "formen", "vorf", "nachf",
                 "ehenamen")

    @property
    def anzeige(self):
        return (self.vor + " " + self.nach).strip() or "?"


def _jahr(d):
    if d is None:
        return None
    for a in ("when-iso", "notBefore-iso", "notAfter-iso", "when"):
        v = d.get(a)
        if v and re.match(r"\d{4}", v):
            return int(v[:4])
    m = re.match(r"-?\d{3,4}", (d.text or "").strip())
    return int(m.group(0)) if m else None


def lade_personen(pfad=None):
    tree = etree.parse(str(pfad or R.listperson))
    out = {}
    for p in tree.iterfind(".//t:person", NS):
        pe = Person()
        pe.pid = p.get(XMLID)
        pe.vor = pe.nach = ""
        pe.varianten, pe.ehenamen = [], []
        varianten_typen = []
        for pn in p.findall("t:persName", NS):
            typ = pn.get("type")
            if typ is None:
                pe.vor = " ".join((c.text or "").strip() for c in pn if etree.QName(c).localname == "forename").strip()
                pe.nach = " ".join((c.text or "").strip() for c in pn if etree.QName(c).localname == "surname").strip()
            else:
                t = (pn.text or "").strip()
                if t:
                    pe.varianten.append(t)
                    varianten_typen.append((typ, t))
                    if typ in ("person_ehename_nachname", "person_geschieden_nachname", "person_verwitwet_nachname"):
                        pe.ehenamen.append(t)
        sx = p.find("t:sex", NS)
        pe.sex = sx.get("value") if sx is not None else None
        pe.geb = _jahr(p.find("t:birth/t:date", NS))
        pe.tod = _jahr(p.find("t:death/t:date", NS))
        pe.beruf = [(o.text or "").strip() for o in p.findall("t:occupation", NS)][:3]
        pe.formen, pe.vorf, pe.nachf = set(), set(), set()
        for teil, ziel in ((pe.vor, pe.vorf), (pe.nach, pe.nachf)):
            for w in woerter(teil):
                if not ist_partikel(w) and len(w.strip(".")) >= 1:
                    ziel.add(fold(w.rstrip(".")))
        pe.formen |= pe.vorf | pe.nachf
        for typ, v in varianten_typen:
            for w in woerter(v):
                if ist_partikel(w):
                    continue
                f = fold(w.rstrip("."))
                pe.formen.add(f)
                if typ.endswith("_nachname"):
                    pe.nachf.add(f)
                elif typ.endswith("_vorname"):
                    pe.vorf.add(f)
        out[pe.pid] = pe
    return out


def stufe_wort(w, formen, gelernt=None):
    """3 = Namensform der Person, 2 = gelernt oder Abkürzung, 1 = Initiale oder ähnlich, 0 = passt nicht."""
    abk = w.endswith(".")
    w0 = w.rstrip(".")
    if not w0 or ist_titel(w0):
        return 0
    ini = re.fullmatch(r"([A-ZÄÖÜ])\.(?:s|’s|'s)?", w)
    if ini:
        c = fold(ini.group(1))
        return 1 if any(f[0] == c for f in formen) else 0
    cands = {fold(w0)}
    if len(w0) > 3 and w0.lower().endswith("s"):
        cands.add(fold(w0[:-1]))
    if w0.lower().endswith(("’s", "'s")):
        cands.add(fold(w0[:-2]))
    for c in cands:
        if len(c) >= 2 and c in formen:
            return 3
    for c in cands:
        if gelernt and (gelernt.get(c, 0) >= 3 or (gelernt.get(c, 0) >= 2 and len(c) >= 4)):
            return 2
    for c in cands:
        if abk and len(c) >= 2 and any(f.startswith(c) for f in formen):
            return 2
    for c in cands:
        if len(c) >= 5 and any(len(f) >= 5 and _ed1(c, f) for f in formen):
            return 1
    return 0


def stufe(oberflaeche, person, gelernt=None):
    """Passt die Oberfläche zur Person? Jedes Namenswort muss passen; Ergebnis = bestes Wort (0..3)."""
    ws = [w for w in woerter(oberflaeche) if not ist_titel(w) and not ist_partikel(w)]
    if not ws:
        return 0
    lv = [stufe_wort(w, person.formen, gelernt) for w in ws]
    return max(lv) if min(lv) >= 1 else 0


def stufe_streng(oberflaeche, person, gelernt=None):
    """Wie stufe(), aber für automatische Zuordnung (Stufe A): mindestens ein Wort ist eine PMB-Namensform,
    oder alle Wörter sind es mindestens gelernt/abgekürzt."""
    ws = [w for w in woerter(oberflaeche) if not ist_titel(w) and not ist_partikel(w)]
    if not ws:
        return 0
    lv = [stufe_wort(w, person.formen, gelernt) for w in ws]
    if min(lv) < 1:
        return 0
    return max(lv) if (max(lv) >= 3 or min(lv) >= 2) else 1


def auto_teile(text, person):
    """Zerlegt einen Namensanker in [(von, bis, Rolle)] mit Rolle roleName|forename|surname (Korpuskonvention:
    Anrede/Titel -> roleName, Partikel zum Vornamen)."""
    toks = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"[^\s,;:!?()]+", text)]
    if not toks:
        return []
    rollen = []
    for _, _, w in toks:
        k = w.strip(_PUNKT)
        if ist_titel(k):
            rollen.append("roleName")
        elif ist_partikel(k):
            rollen.append("part")
        else:
            f = fold(k.rstrip("."))
            fs = {f, f[:-1]} if f.endswith("s") else {f}
            in_nach = person is not None and bool(fs & person.nachf)
            in_vor = person is not None and bool(fs & person.vorf)
            rollen.append("surname" if in_nach and not in_vor else "forename" if in_vor and not in_nach else "?")
    namen = [i for i, r in enumerate(rollen) if r in ("surname", "forename", "?")]
    for pos, i in enumerate(namen):
        if rollen[i] == "?":
            rollen[i] = "surname" if (pos == len(namen) - 1 and len(namen) > 1) else "forename"
    for i, r in enumerate(rollen):
        if r == "part":
            rollen[i] = "forename"
    out = []
    for (s, e, _), r in zip(toks, rollen):
        if out and out[-1][2] == r and text[out[-1][1]:s].strip() == "":
            out[-1] = (out[-1][0], e, r)
        else:
            out.append((s, e, r))
    return out


# ----------------------------------------------------------------------------------------------
# Verwandtschaft (PMB-Relationen, auf Verwandtschaft gekürzt)
# ----------------------------------------------------------------------------------------------

SCHNITZLER = "pmb2121"

# relation_type der PMB -> (Rolle des target für source, Rolle des source für target, Zusatz)
REL_TYPEN = {
    "ist verheiratet mit": ("Ehe", "Ehe", ""),
    "ist verheiratet mit (bis zum Tod)": ("Ehe", "Ehe", "bis zum Tod"),
    "ist verheiratet mit (verwitwet)": ("Ehe", "Ehe", "verwitwet"),
    "ist verheiratet mit (Scheidung)": ("Ehe", "Ehe", "geschieden"),
    "ist verlobt mit": ("Verlobung", "Verlobung", ""),
    "ist Kind von": ("Elternteil", "Kind", ""),
    "ist biologisches Kind von": ("Elternteil", "Kind", "biologisch"),
    "möglicherweise biologisches Kind von": ("Elternteil", "Kind", "möglicherweise"),
    "ist adoptiertes Kind von": ("Elternteil", "Kind", "adoptiert"),
    "ist Stiefkind von": ("Stiefelternteil", "Stiefkind", ""),
    "ist Schwiegerkind von": ("Schwiegerelternteil", "Schwiegerkind", ""),
    "ist Elternteil von": ("Kind", "Elternteil", ""),
    "ist biologisches Elternteil von": ("Kind", "Elternteil", "biologisch"),
    "ist durch Adoption Elternteil von": ("Kind", "Elternteil", "adoptiert"),
    "ist Stiefelternteil von": ("Stiefkind", "Stiefelternteil", ""),
    "ist Schwiegerelternteil von": ("Schwiegerkind", "Schwiegerelternteil", ""),
    "ist Großelternteil von": ("Enkel", "Großelternteil", ""),
    "ist Enkel/Enkelin von": ("Großelternteil", "Enkel", ""),
    "ist Geschwister von": ("Geschwister", "Geschwister", ""),
    "ist Halbgeschwister von": ("Halbgeschwister", "Halbgeschwister", ""),
    "ist Stiefgeschwister von": ("Stiefgeschwister", "Stiefgeschwister", ""),
    "ist Onkel/Tante von": ("Neffe/Nichte", "Onkel/Tante", ""),
    "ist Neffe/Nichte von": ("Onkel/Tante", "Neffe/Nichte", ""),
    "ist Großonkel/Großtante von": ("Großneffe/Großnichte", "Großonkel/Großtante", ""),
    "ist Großneffe/Großnichte von": ("Großonkel/Großtante", "Großneffe/Großnichte", ""),
    "ist Cousin/Cousine von": ("Cousin/Cousine", "Cousin/Cousine", ""),
    "ist verschwägert mit": ("Verschwägerter", "Verschwägerter", ""),
    "ist verwandt zu": ("Verwandter", "Verwandter", ""),
}

# gesuchte Grundrolle -> gespeicherte Rollen
ROLLEN_FUER = {
    "Ehe": ("Ehe",),
    "Kind": ("Kind", "Stiefkind"),
    "Elternteil": ("Elternteil", "Stiefelternteil"),
    "Geschwister": ("Geschwister", "Halbgeschwister", "Stiefgeschwister"),
    "Onkel/Tante": ("Onkel/Tante", "Großonkel/Großtante"),
    "Neffe/Nichte": ("Neffe/Nichte", "Großneffe/Großnichte"),
    "Cousin/Cousine": ("Cousin/Cousine",),
    "Großelternteil": ("Großelternteil",),
    "Enkel": ("Enkel",),
    "Schwiegerelternteil": ("Schwiegerelternteil",),
    "Schwiegerkind": ("Schwiegerkind",),
}

# Wort im Text -> (Grundrolle, Geschlecht der gesuchten Person oder None)
WORT_ROLLE = {
    "frau": ("Ehe", "female"), "gattin": ("Ehe", "female"), "gemahlin": ("Ehe", "female"),
    "mann": ("Ehe", "male"), "gatte": ("Ehe", "male"),
    "tochter": ("Kind", "female"), "töchter": ("Kind", "female"), "sohn": ("Kind", "male"), "söhne": ("Kind", "male"),
    "kinder": ("Kind", None), "kindern": ("Kind", None), "bub": ("Kind", "male"), "buben": ("Kind", "male"),
    "bruder": ("Geschwister", "male"), "brüder": ("Geschwister", "male"), "schwester": ("Geschwister", "female"),
    "geschwister": ("Geschwister", None), "geschwistern": ("Geschwister", None),
    "mutter": ("Elternteil", "female"), "vater": ("Elternteil", "male"), "eltern": ("Elternteil", None),
    "mama": ("Elternteil", "female"), "papa": ("Elternteil", "male"),
    "großmutter": ("Großelternteil", "female"), "großmama": ("Großelternteil", "female"),
    "großvater": ("Großelternteil", "male"), "großpapa": ("Großelternteil", "male"),
    "schwager": ("Schwager", "male"), "schwägerin": ("Schwager", "female"),
    "onkel": ("Onkel/Tante", "male"), "tante": ("Onkel/Tante", "female"),
    "neffe": ("Neffe/Nichte", "male"), "nichte": ("Neffe/Nichte", "female"),
    "cousin": ("Cousin/Cousine", "male"), "cousine": ("Cousin/Cousine", "female"), "vetter": ("Cousin/Cousine", "male"),
    "enkel": ("Enkel", None),
    "schwiegervater": ("Schwiegerelternteil", "male"), "schwiegermutter": ("Schwiegerelternteil", "female"),
    "schwiegersohn": ("Schwiegerkind", "male"), "schwiegertochter": ("Schwiegerkind", "female"),
}
GRUPPEN_WORTE = frozenset({"kinder", "kindern", "töchter", "söhne", "brüder", "geschwister", "geschwistern", "eltern", "buben"})


def wort_rolle(wort):
    """(Grundrolle, Geschlecht) für ein Verwandtschaftswort (auch im Genitiv: Vaters, Mamas), sonst None."""
    w = wort.lower().strip(_PUNKT)
    if w in WORT_ROLLE:
        return WORT_ROLLE[w]
    if w.endswith("s") and w[:-1] in WORT_ROLLE:
        return WORT_ROLLE[w[:-1]]
    return None


Rel = collections.namedtuple("Rel", "andere rolle zusatz von bis von_genau bis_genau pk typ")


def rel_status(r, tag, kopf, andere):
    """Gilt die Relation am Tag? -> 'gueltig' | 'nicht_am_leben' | 'zu_jung' | 'vor_beginn' | 'nach_ende'.
    Ehen prüfen den Zeitraum (jahresgenaue Angaben gelten für das ganze Jahr), alle anderen Relationen nur die Lebensdaten."""
    j = int(tag[:4])
    for x in (kopf, andere):
        if x is not None and ((x.geb and j < x.geb) or (x.tod and j > x.tod)):
            return "nicht_am_leben"
    if r.rolle == "Ehe" or r.rolle == "Verlobung":
        if r.von and tag < (r.von if r.von_genau else r.von[:4] + "-01-01"):
            return "vor_beginn"
        if r.bis and tag > (r.bis if r.bis_genau else r.bis[:4] + "-12-31"):
            return "nach_ende"
        for x in (kopf, andere):
            if x is not None and x.geb and j < x.geb + 16:
                return "zu_jung"
    return "gueltig"


def _rel_text(r):
    if r.rolle == "Ehe":
        z = f" ({r.zusatz})" if r.zusatz else ""
        von = (r.von if r.von_genau else (r.von or "")[:4]) if r.von else "?"
        bis = (r.bis if r.bis_genau else r.bis[:4]) if r.bis else ""
        return f"verheiratet{z} {von}–{bis}"
    return r.rolle + (f" ({r.zusatz})" if r.zusatz else "")


class Verwandtschaft:
    """Gekürzte PMB-Relationen (nur Verwandtschaft) mit Personen: Ehepartner, Kinder, Eltern, Geschwister usw.
    Daten: data/verwandtschaft-*.{csv,xml}; erzeugt mit `pa.py kuerzen` aus den ungekürzten PMB-Dateien."""

    def __init__(self):
        self.rel = collections.defaultdict(list)
        self.personen = {}
        self.vorhanden = R.verw_relationen.exists() and R.verw_personen.exists()
        if not self.vorhanden:
            return
        self.personen = lade_personen(R.verw_personen)
        with open(R.verw_relationen, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                typ = row["relation_type"]
                if typ not in REL_TYPEN:
                    continue
                a, b = "pmb" + row["source_id"], "pmb" + row["target_id"]
                r_ziel, r_quelle, zusatz = REL_TYPEN[typ]
                von = None if row["start"] in ("", "nodate") else row["start"]
                bis = None if row["end"] in ("", "nodate") else row["end"]
                vg, bg = len(row["start_written"]) == 10, len(row["end_written"]) == 10
                self.rel[a].append(Rel(b, r_ziel, zusatz, von, bis, vg, bg, row["relation_pk"], typ))
                self.rel[b].append(Rel(a, r_quelle, zusatz, von, bis, vg, bg, row["relation_pk"], typ))

    def verwandte(self, pid, grundrolle, tag, personen, geschlecht=None, nur_gueltige=True):
        """Personen, die am Tag in der gesuchten Grundrolle zu pid stehen: [{ref, name, jahre, sex, rolle, text, status, …}]."""
        rollen = ROLLEN_FUER.get(grundrolle, (grundrolle,))
        kopf = personen.get(pid)
        out, gesehen = [], set()
        for r in self.rel.get(pid, ()):
            if r.rolle not in rollen:
                continue
            p = personen.get(r.andere)
            if geschlecht and p is not None and p.sex and p.sex != geschlecht:
                continue
            status = rel_status(r, tag, kopf, p)
            if nur_gueltige and status != "gueltig":
                continue
            if (r.andere, status) in gesehen:
                continue
            gesehen.add((r.andere, status))
            out.append({"ref": r.andere, "name": p.anzeige if p else "?",
                        "jahre": f"{p.geb or ''}–{p.tod or ''}" if p else "", "sex": p.sex if p else None,
                        "rolle": r.rolle, "text": _rel_text(r), "status": status, "quelle": "PMB-Relation",
                        "datum_unsicher": r.rolle == "Ehe" and not r.von})
        return out

    def schwager(self, pid, tag, personen, geschlecht=None):
        """Verschwägerte am Tag: direkte Relation, Ehepartner der Geschwister, Geschwister der Ehepartner,
        Ehepartner der Geschwister der Ehepartner."""
        out = {}

        def add(ref, weg):
            p = personen.get(ref)
            if ref == pid or (geschlecht and p is not None and p.sex and p.sex != geschlecht):
                return
            if p is not None and ((p.geb and int(tag[:4]) < p.geb) or (p.tod and int(tag[:4]) > p.tod)):
                return
            out.setdefault(ref, {"ref": ref, "name": p.anzeige if p else "?",
                                 "jahre": f"{p.geb or ''}–{p.tod or ''}" if p else "", "sex": p.sex if p else None,
                                 "rolle": "Schwager/Schwägerin", "text": weg, "status": "gueltig",
                                 "quelle": "PMB-Relation", "datum_unsicher": False})

        for r in self.rel.get(pid, ()):
            if r.rolle == "Verschwägerter" and rel_status(r, tag, personen.get(pid), personen.get(r.andere)) == "gueltig":
                add(r.andere, "verschwägert (PMB)")
        gatten = self.verwandte(pid, "Ehe", tag, personen)
        for g in self.verwandte(pid, "Geschwister", tag, personen):
            for e in self.verwandte(g["ref"], "Ehe", tag, personen):
                add(e["ref"], f"Ehepartner von {g['name']} (Geschwister)")
        for e in gatten:
            for g in self.verwandte(e["ref"], "Geschwister", tag, personen):
                add(g["ref"], f"Geschwister von {e['name']} (Ehepartner)")
                for e2 in self.verwandte(g["ref"], "Ehe", tag, personen):
                    add(e2["ref"], f"Ehepartner von {g['name']}, Geschwister von {e['name']} (Ehepartner)")
        return list(out.values())

    def zu_wort(self, pid, wort, tag, personen):
        """Kandidaten für ein Verwandtschaftswort im Text, gesehen von pid: (Grundrolle, Gruppenwort?, [Kandidaten])."""
        wr = wort_rolle(wort)
        if wr is None:
            return None, False, []
        rolle, geschlecht = wr
        gruppe = wort.lower().strip(_PUNKT) in GRUPPEN_WORTE
        if rolle == "Schwager":
            return rolle, gruppe, self.schwager(pid, tag, personen, geschlecht)
        return rolle, gruppe, self.verwandte(pid, rolle, tag, personen, geschlecht)

    def alle(self, pid, personen, tag=None):
        """Alle Relationen einer Person (für `pa.py verwandte`), mit Status zum Tag."""
        out = []
        kopf = personen.get(pid)
        for r in sorted(self.rel.get(pid, ()), key=lambda x: (x.rolle, x.von or "")):
            p = personen.get(r.andere)
            out.append((r, p, rel_status(r, tag, kopf, p) if tag else None))
        return out


def pmb_zahl(ref):
    return ref[3:] if ref.startswith("pmb") else ref


def _person_kurz(el, n):
    """Gekürzter person-Eintrag (Namen, Geschlecht, Lebensdaten, Berufe, pmb-idno) als TEI-Text."""
    t = "{%s}" % TEI
    z = [f'      <person xml:id="pmb{n}">']
    for pn in el.findall(t + "persName"):
        typ = pn.get("type")
        if typ is None:
            teile = []
            for c in pn:
                ln = etree.QName(c).localname
                if ln in ("forename", "surname") and (c.text or "").strip():
                    teile.append(f"<{ln}>{xml_escape(c.text.strip())}</{ln}>")
            z.append("         <persName>" + "".join(teile) + "</persName>")
        elif (pn.text or "").strip():
            z.append(f'         <persName type="{xml_escape(typ)}">{xml_escape(pn.text.strip())}</persName>')
    for tagname in ("birth", "death"):
        d = el.find(f"{t}{tagname}/{t}date")
        if d is not None:
            attrs = "".join(f' {k}="{xml_escape(v)}"' for k, v in d.attrib.items())
            z.append(f"         <{tagname}><date{attrs}>{xml_escape((d.text or '').strip())}</date></{tagname}>")
    sx = el.find(t + "sex")
    if sx is not None and sx.get("value"):
        z.append(f'         <sex value="{xml_escape(sx.get("value"))}"/>')
    for o in el.findall(t + "occupation")[:2]:
        if (o.text or "").strip():
            z.append(f"         <occupation>{xml_escape(o.text.strip())}</occupation>")
    z.append(f'         <idno type="URL" subtype="pmb">https://pmb.acdh.oeaw.ac.at/entity/{n}/</idno>')
    z.append("      </person>")
    return "\n".join(z)


def cmd_kuerzen(args):
    """Kürzt die ungekürzten PMB-Dateien (relations.csv, listperson.xml) auf Verwandtschaft:
    nur Person→Person-Relationen der Verwandtschaftstypen und nur die daran beteiligten Personen."""
    quelle = Path(args.quelle) if args.quelle else R.pmb_quelle
    rel_pfad, lp_pfad = quelle / "relations.csv", quelle / "listperson.xml"
    for pf in (rel_pfad, lp_pfad):
        if not pf.exists():
            raise PaError(f"{pf} fehlt (PMB: https://pmb.acdh.oeaw.ac.at/media/relations.csv und .../media/listperson.xml)")
    csv.field_size_limit(10 ** 9)
    behalten, gesehen, typen, ids, zeilen = [], set(), collections.Counter(), set(), 0
    with open(rel_pfad, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            zeilen += 1
            if row.get("relation_class") != "Person -> Person" or row.get("relation_type") not in REL_TYPEN:
                continue
            key = (row["source_id"], row["target_id"], row["relation_type"], row["relation_start_date"], row["relation_end_date"])
            if key in gesehen:
                continue
            gesehen.add(key)
            behalten.append(row)
            typen[row["relation_type"]] += 1
            ids.add(row["source_id"])
            ids.add(row["target_id"])
    personen_xml, gefunden = [], set()
    for _, el in etree.iterparse(str(lp_pfad), events=("end",), tag="{%s}person" % TEI):
        xid = el.get(XMLID) or ""
        n = xid.split("__")[-1] if "__" in xid else re.sub(r"^pmb", "", xid)
        if n in ids:
            personen_xml.append(_person_kurz(el, n))
            gefunden.add(n)
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]
    fehlend = sorted(ids - gefunden, key=int)
    ziel = Path(args.ausgabe) if args.ausgabe else R.verw_dir
    ziel.mkdir(parents=True, exist_ok=True)
    spalten = ["relation_pk", "relation_type", "source_id", "target_id", "start", "end", "start_written", "end_written",
               "source", "target"]
    with open(ziel / "verwandtschaft-relationen.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(spalten)
        for row in sorted(behalten, key=lambda r: (int(r["source_id"]), int(r["target_id"]), r["relation_type"])):
            w.writerow([row["relation_pk"], row["relation_type"], row["source_id"], row["target_id"],
                        row["relation_start_date"], row["relation_end_date"], row["relation_start_date_written"],
                        row["relation_end_date_written"], row["source"], row["target"]])
    kopf = ('<?xml version="1.0" encoding="UTF-8"?>\n<TEI xmlns="http://www.tei-c.org/ns/1.0">\n'
            '   <teiHeader><fileDesc><titleStmt><title>Personen mit Verwandtschaftsrelationen (gekürzt aus der PMB)</title>'
            '</titleStmt><publicationStmt><p>Auszug aus pmb.acdh.oeaw.ac.at/media/listperson.xml; erzeugt mit pa.py kuerzen</p>'
            '</publicationStmt><sourceDesc><p>PMB – Personen der Moderne Basis</p></sourceDesc></fileDesc></teiHeader>\n'
            '   <text><body><listPerson>\n')
    personen_xml.sort(key=lambda z: int(re.search(r'xml:id="pmb(\d+)"', z).group(1)))
    schreibe(ziel / "verwandtschaft-personen.xml", kopf + "\n".join(personen_xml) + "\n   </listPerson></body></text>\n</TEI>\n")
    sha = lambda pf: hashlib.sha1(pf.read_bytes()).hexdigest()
    stand = ""
    m = re.search(r'when-iso="([^"]+)"', lp_pfad.read_bytes()[:3000].decode("utf-8", "ignore"))
    if m:
        stand = m.group(1)
    register = set(re.findall(r'xml:id="pmb(\d+)"', lies(R.listperson))) if R.listperson.exists() else set()
    info = {"erzeugt": dt.date.today().isoformat(), "quelle_stand": stand,
            "quelle": {"relations.csv": {"bytes": rel_pfad.stat().st_size, "sha1": sha(rel_pfad), "zeilen": zeilen},
                       "listperson.xml": {"bytes": lp_pfad.stat().st_size, "sha1": sha(lp_pfad)}},
            "relationen": len(behalten), "personen": len(gefunden), "personen_ohne_eintrag_in_liste": fehlend,
            "typen": dict(typen.most_common()),
            "davon_im_tagebuch_register": len(ids & register), "ausserhalb_register": len(ids - register),
            "hinweis": "Ungekürzte Quellen: PMB-Downloads relations.csv und listperson.xml; Befehl: pa.py kuerzen --quelle <Ordner>"}
    schreibe(ziel / "verwandtschaft-quelle.json", json.dumps(info, ensure_ascii=False, indent=1) + "\n")
    print(f"Quelle: {quelle} (relations.csv {zeilen} Zeilen; listperson.xml Stand {stand or '?'})")
    print(f"Verwandtschaftsrelationen: {len(behalten)} ({len(ids)} Personen, davon {len(gefunden)} in der Vollliste gefunden)")
    print(f"Personen im Tagebuch-Register: {len(ids & register)}; außerhalb des Registers: {len(ids - register)}")
    for k, v in typen.most_common(8):
        print(f"  {v:5d} {k}")
    for pf in ("verwandtschaft-relationen.csv", "verwandtschaft-personen.xml", "verwandtschaft-quelle.json"):
        print(f"geschrieben: {ziel / pf} ({(ziel / pf).stat().st_size / 1024:.0f} KB)")
    return 0


def cmd_verwandte(args):
    vw = Verwandtschaft()
    if not vw.vorhanden:
        raise PaError("Keine Verwandtschaftsdaten: zuerst `pa.py kuerzen --quelle temp-indices`")
    personen = dict(vw.personen)
    personen.update(lade_personen())
    register = set(re.findall(r'xml:id="(pmb\d+)"', lies(R.listperson)))
    pid = args.person if args.person.startswith("pmb") else "pmb" + args.person
    p = personen.get(pid)
    print(lebensinfo(p) if p else f"{pid}: nicht in den Personenlisten")
    if args.wort:
        rolle, gruppe, cands = vw.zu_wort(pid, args.wort, args.tag or "1900-01-01", personen)
        print(f"Wort »{args.wort}« → Rolle {rolle}{' (Gruppe)' if gruppe else ''} am {args.tag or '1900-01-01'}:")
        for c in cands:
            print(f"  {c['ref']} {c['name']} ({c['jahre']}) {c['text']}{'' if c['ref'] in register else '  [nicht im Register]'}")
        return 0
    for r, a, status in vw.alle(pid, personen, args.tag):
        name = a.anzeige if a else "?"
        z = f"  {r.rolle:22s} {r.andere:10s} {name} ({a.geb or ''}–{a.tod or ''}) " if a else f"  {r.rolle:22s} {r.andere:10s} ? "
        if r.rolle == "Ehe":
            z += _rel_text(r)
        if status:
            z += f"  [{status}]"
        if r.andere not in register:
            z += "  [nicht im Register]"
        print(z)
    return 0


# ----------------------------------------------------------------------------------------------
# Bearbeitungsplan je Datei
# ----------------------------------------------------------------------------------------------

class Plan:
    """Sammelt Einfügungen in den Rohtext einer Datei und setzt sie am Ende in einem Zug ein.
    Reihenfolge bei gleicher Position: erst schließende Tags (innere vor äußeren), dann Attribute,
    dann öffnende Tags (spätere Operation = weiter außen)."""

    def __init__(self, doc):
        self.doc = doc
        self.ins = []
        self.seq = 0
        self.intervalle = []
        self.neue_ids = []
        self.setref_ids = []

    def _s(self):
        self.seq += 1
        return self.seq

    def attr(self, pos, text):
        self.ins.append((pos, 1, self._s(), text))

    def umhuellen(self, raw_a, raw_b, offen, kinder=()):
        for a, b, rolle in kinder:
            s = self._s()
            self.ins.append((a, 2, -s, f"<{rolle}>"))
            self.ins.append((b, 0, s, f"</{rolle}>"))
        s = self._s()
        self.ins.append((raw_a, 2, -s, offen))
        self.ins.append((raw_b, 0, s, "</rs>"))
        self.intervalle.append((raw_a, raw_b))

    def pruefe_ueberlappung(self):
        iv = sorted(set(self.intervalle), key=lambda x: (x[0], -x[1]))
        stack = []
        for a, b in iv:
            while stack and stack[-1][1] <= a:
                stack.pop()
            if stack and b > stack[-1][1]:
                raise PaError(f"{self.doc.name}: zwei Anker überlappen sich teilweise ({self.doc.raw[stack[-1][0]:stack[-1][1]][:40]!r} / {self.doc.raw[a:b][:40]!r})", "anker")
            stack.append((a, b))

    def erzeuge(self):
        self.pruefe_ueberlappung()
        out, last = [], 0
        for pos, _, _, text in sorted(self.ins, key=lambda x: (x[0], x[1], x[2])):
            out.append(self.doc.raw[last:pos])
            out.append(text)
            last = pos
        out.append(self.doc.raw[last:])
        return "".join(out)


def _refstr(refs):
    return " ".join("#" + r for r in refs)


def normiert(doc, neue_ids, setref_ids):
    """Token-Folge einer Datei ohne die geplanten Einfügungen (neue rs samt Kindelementen, neue ref-Attribute);
    benachbarte Textknoten werden zusammengefasst."""
    skip_end, out = set(), []
    for kind, s, e, ref in doc.toks:
        tok = doc.raw[s:e]
        if kind in ("start", "end", "empty"):
            el = doc.els[ref]
            neu_rs = el.name == "rs" and el.attrs.get("xml:id") in neue_ids
            par = doc.els[el.parent] if el.parent >= 0 else None
            neu_kind = (el.name in ("forename", "surname", "roleName") and par is not None and par.name == "rs"
                        and par.attrs.get("xml:id") in neue_ids)
            if neu_rs or neu_kind:
                continue
            if kind != "end" and el.attrs.get("xml:id") in setref_ids and el.name == "rs":
                tok = re.sub(r'\s+ref="[^"]*"', "", tok, count=1)
        if kind == "text" and out and out[-1][0] == "text":
            out[-1] = ("text", out[-1][1] + tok)
        else:
            out.append((kind if kind == "text" else "tag", tok))
    return out


def pruefe_invarianten(alt, neu_raw, plan):
    neu = Doc(neu_raw, alt.name)
    try:
        etree.fromstring(neu_raw.encode("utf-8"))
    except etree.XMLSyntaxError as ex:
        raise PaError(f"{alt.name}: Ergebnis nicht wohlgeformt: {ex}", "invariante")
    if neu.flat != alt.flat:
        raise PaError(f"{alt.name}: Textfluss des body hat sich verändert", "invariante")
    if alt.raw[:alt.body.start] != neu_raw[:alt.body.start]:
        raise PaError(f"{alt.name}: Text vor dem body hat sich verändert", "invariante")
    if normiert(alt, set(), set()) != normiert(neu, set(plan.neue_ids), set(plan.setref_ids)):
        raise PaError(f"{alt.name}: Datei weicht über die geplanten Einfügungen hinaus ab", "invariante")
    return neu


# ----------------------------------------------------------------------------------------------
# Operationen
# ----------------------------------------------------------------------------------------------

class Kontext:
    def __init__(self):
        self.ids = Ids()
        self.implied = ImpliedListe()
        self.bekannt = set(re.findall(r'xml:id="(pmb\d+)"', lies(R.listperson)))
        self.vw_ids = set(re.findall(r'xml:id="(pmb\d+)"', lies(R.verw_personen))) if R.verw_personen.exists() else set()
        self.ausserhalb = set()          # genutzte PMB-Personen, die nicht im Tagebuch-Register stehen
        self.index = lies_index()
        self.index_neu = collections.defaultdict(list)
        self._personen = None

    @property
    def personen(self):
        if self._personen is None:
            self._personen = lade_personen()
        return self._personen

    def refs(self, op, doc, tag, geschlossen=True):
        roh = op.get("ref")
        liste = roh if isinstance(roh, list) else str(roh or "").replace("#", " ").split()
        liste = [x.strip().lstrip("#") for x in liste if x.strip()]
        if not liste:
            raise PaError(f"{tag}: Operation ohne ref", "ref")
        tagesindex = {r for r, _ in self.index.get(tag, [])}
        im_text = {r.lstrip("#") for el in doc.els if el.name == "rs" and doc.im_body(el)
                   for r in el.attrs.get("ref", "").split()}
        for r in liste:
            if not REF_RE.fullmatch(r):
                raise PaError(f"{tag}: ungültiger ref »{r}«", "ref")
            if r not in self.bekannt and r not in self.implied.ids() and r not in tagesindex and r not in self.vw_ids:
                raise PaError(f"{tag}: {r} steht weder in listperson.xml noch in implied-persons.txt noch im Index des Tages "
                              f"noch in den PMB-Verwandtschaftsdaten", "ref")
            if r not in self.bekannt and r in self.vw_ids and r not in tagesindex:
                self.ausserhalb.add(r)
            if geschlossen and not op.get("frei") and r not in tagesindex and r not in im_text:
                raise PaError(f"{tag}: {r} gehört nicht zu den Index-Refs oder Text-Refs dieses Tages (frei: true nur mit Begründung)", "ref")
        return liste


def _teile_aus_op(op, an):
    """Kindelemente (absolute Rohpositionen) aus op['teile'] (Liste »rolle:text«), sonst None."""
    teile = op.get("teile")
    if not teile:
        return None
    out, pos = [], 0
    for t in teile:
        rolle, _, txt = t.partition(":")
        if rolle not in ("roleName", "forename", "surname") or not txt:
            raise PaError(f"ungültiger Eintrag in teile: {t!r}", "teile")
        i = an.text.find(txt, pos)
        if i < 0:
            raise PaError(f"teile: »{txt}« nicht im Anker »{an.text}« (Reihenfolge beachten)", "teile")
        out.append((an.seg.raw_pos(an.a + i), an.seg.raw_pos(an.a + i + len(txt)), rolle))
        pos = i + len(txt)
    return out


def _kinder(op, doc, an, personen, refs, typ):
    """Kindelemente forename/surname/roleName für einen neuen Personen-rs (absolute Rohpositionen)."""
    if typ != "person" or op.get("ohne_teile") or op.get("teile") == []:
        return []
    if op.get("teile"):
        return _teile_aus_op(op, an) or []
    if len(refs) != 1 or not refs[0].startswith("pmb") or "&" in doc.raw[an.raw_a:an.raw_b]:
        return []
    p = personen.get(refs[0])
    if p is None:
        return []
    return [(an.seg.raw_pos(an.a + a), an.seg.raw_pos(an.a + b), r) for a, b, r in auto_teile(an.text, p)]


def op_set_ref(plan, op, ctx, tag):
    doc = plan.doc
    el = doc.finde_id(op.get("id", ""))
    if el.name != "rs" or el.attrs.get("type") not in ("person", "allusively"):
        raise PaError(f"{tag}: {op['id']} ist kein rs vom Typ person/allusively", "id")
    refs = ctx.refs(op, doc, tag)
    neu = _refstr(refs)
    if op["id"] in plan.setref_ids:
        raise PaError(f"{tag}: {op['id']} bekommt in diesem Lauf schon einen ref – mehrere Personen für dasselbe rs "
                      "als Liste in einer Operation angeben (\"ref\": [\"pmbA\", \"pmbB\"])", "ref")
    if "ref" in el.attrs:
        if el.attrs["ref"].split() == neu.split():
            return "übersprungen (ref schon gesetzt)", None
        raise PaError(f"{tag}: {op['id']} hat schon ref=\"{el.attrs['ref']}\"; bestehende Refs werden nie geändert", "ref")
    plan.attr(el.spans.get("xml:id", el.attr_end), f' ref="{neu}"')
    plan.setref_ids.append(op["id"])
    return "set_ref", (doc.text_von(el), refs)


def op_wrap(plan, op, ctx, tag):
    doc = plan.doc
    a = op.get("anker") or {}
    typ = op.get("typ", "person")
    if typ not in ("person", "allusively"):
        raise PaError(f"{tag}: typ muss person oder allusively sein", "typ")
    refs = ctx.refs(op, doc, tag)
    an = doc.finde_anker(a.get("text", ""), a.get("vorher", ""), a.get("nachher", ""), a.get("nr"),
                         a.get("teilwort", False), bereits_ref=refs)
    if an is None:
        return "übersprungen (schon ausgezeichnet)", None
    xid = ctx.ids.neu("pNt" if typ == "person" else "rst")
    offen = f'<rs type="{typ}" xml:id="{xid}" ref="{_refstr(refs)}">'
    plan.umhuellen(an.raw_a, an.raw_b, offen, _kinder(op, doc, an, ctx.personen if typ == "person" else {}, refs, typ))
    plan.neue_ids.append(xid)
    return "wrap", (an.text, refs)


def op_implied(plan, op, ctx, tag):
    doc = plan.doc
    if "neu" in op:
        ref, _neu = ctx.implied.holen(op["neu"])
        refs = [ref]
    else:
        refs = ctx.refs(op, doc, tag, geschlossen=False)
    if len(refs) != 1:
        raise PaError(f"{tag}: implied braucht genau einen ref", "ref")
    if "um_rs" in op:
        el = doc.finde_id(op["um_rs"])
        if el.name != "rs":
            raise PaError(f"{tag}: {op['um_rs']} ist kein rs", "id")
        for a in doc._vorfahren(el.parent):
            if a.name == "rs" and a.attrs.get("subtype") == "implied" and refs[0] in {r.lstrip("#") for r in a.attrs.get("ref", "").split()}:
                return "übersprungen (implied schon vorhanden)", None
        ra, rb, text = el.start, el.end, doc.text_von(el)
    else:
        a = op.get("anker") or {}
        an = doc.finde_anker(a.get("text", ""), a.get("vorher", ""), a.get("nachher", ""), a.get("nr"),
                             a.get("teilwort", False), bereits_ref=refs)
        if an is None:
            return "übersprungen (implied schon vorhanden)", None
        ra, rb, text = an.raw_a, an.raw_b, an.text
    xid = ctx.ids.neu("pNt")
    plan.umhuellen(ra, rb, f'<rs type="person" xml:id="{xid}" ref="#{refs[0]}" subtype="implied">')
    plan.neue_ids.append(xid)
    if op.get("index", True):
        ctx.index_neu[tag].append((refs[0], True))
    return "implied", (text, refs)


def op_index_add(plan, op, ctx, tag):
    refs = ctx.refs(op, plan.doc, tag, geschlossen=False)
    for r in refs:
        ctx.index_neu[tag].append((r, bool(op.get("implied", False))))
    return "index_add", ("", refs)


OPS = {"set_ref": op_set_ref, "wrap": op_wrap, "implied": op_implied, "index_add": op_index_add}


# ----------------------------------------------------------------------------------------------
# apply
# ----------------------------------------------------------------------------------------------

def git(*args):
    return subprocess.run(["git", "-C", str(R.root), *args], capture_output=True, text=True)


def unsaubere_dateien():
    r = git("status", "--porcelain")
    return {line[3:].strip().strip('"') for line in r.stdout.splitlines() if line.strip()}


def cmd_apply(args):
    verworfen_neu = set()
    ops, kfehler = lade_ops(args.dateien, verworfen_neu)
    fehler = [(-1, {}, m) for m in kfehler]
    if not ops and not verworfen_neu and not fehler:
        print("keine Operationen")
        return 0
    nach_tag = collections.OrderedDict()
    for i, op in enumerate(ops):
        tag = op.get("tag", "")
        if not TAG_RE.fullmatch(tag) or not R.entry(tag).exists():
            fehler.append((i, op, f"Tag »{tag}« unbekannt"))
            continue
        if op.get("op") not in OPS:
            fehler.append((i, op, f"unbekannte Operation »{op.get('op')}«"))
            continue
        nach_tag.setdefault(tag, []).append((i, op))
    if not args.unsauber:
        schmutz = unsaubere_dateien()
        ziel = {f"editions/entry__{t}.xml" for t in nach_tag} | {"indices/index_person_day.xml", "indices/implied-persons.txt"}
        offen = sorted(ziel & schmutz)
        if offen:
            print("Abbruch: uncommittete Änderungen an Zieldateien (erst committen oder --unsauber):", file=sys.stderr)
            for o in offen[:10]:
                print("  ", o, file=sys.stderr)
            return 2
    ctx = Kontext()
    ergebnisse, geschrieben = [], []
    for tag, liste in nach_tag.items():
        doc = Doc(lies(R.entry(tag)), tag)
        plan = Plan(doc)
        lokale = []
        for i, op in liste:
            try:
                art, info = OPS[op["op"]](plan, op, ctx, tag)
                lokale.append((i, op, art, info))
            except PaError as ex:
                fehler.append((i, op, str(ex)))
        if not plan.ins:
            ergebnisse += [(tag, i, op, art, info, doc) for i, op, art, info in lokale]
            continue
        try:
            neu_raw = plan.erzeuge()
            pruefe_invarianten(doc, neu_raw, plan)
        except PaError as ex:
            fehler.append((-1, {"tag": tag}, str(ex)))
            continue
        geschrieben.append((tag, neu_raw))
        ergebnisse += [(tag, i, op, art, info, doc) for i, op, art, info in lokale]
    if fehler and not args.weiter:
        print(f"{len(fehler)} Fehler, nichts geschrieben:", file=sys.stderr)
        for i, op, msg in fehler:
            print(f"  [{i}] {msg}", file=sys.stderr)
        return 1
    # Index
    index_neu_raw, index_neu = None, []
    if ctx.index_neu:
        index_neu_raw, index_neu = index_ergaenzen(lies(R.index), ctx.index_neu)
    # Ausgabe (--ruhig: nur Zusammenfassung, Hinweise und Fehler; spart in langen Läufen die zweite Ausgabe jeder Operation)
    ruhig = getattr(args, "ruhig", False)
    for tag, i, op, art, info, doc in ergebnisse:
        if ruhig:
            break
        if info:
            text, refs = info
            print(f"{tag}  {art:9s} {'/'.join(refs):14s} »{text[:50]}« {op.get('grund', '')[:70]}")
        else:
            print(f"{tag}  {art}")
    if ctx.implied.neue:
        for pid, beschr in ctx.implied.neue:
            print(f"neu in implied-persons.txt: {pid}|?? [{beschr}]")
    if ctx.ausserhalb:
        pv = lade_personen(R.verw_personen)
        print("Hinweis: PMB-Personen außerhalb von indices/listperson.xml (Seite erst nach Aufnahme in das Tagebuch-Register): " +
              "; ".join(f"{r} {pv[r].anzeige if r in pv else '?'}" for r in sorted(ctx.ausserhalb)))
    for tag, r, impl in index_neu:
        if not ruhig:
            print(f"Index {tag}: + {r}{' (implied)' if impl else ''}")
    for i, op, msg in fehler:
        print(f"FEHLER [{i}] {msg}", file=sys.stderr)
    zaehl = collections.Counter(art for _, _, _, art, _, _ in ergebnisse)
    print(f"\n{'Trockenlauf: ' if args.dry_run else ''}{dict(zaehl)}; Dateien: {len(geschrieben)}; Index-Zeilen: {len(index_neu)}")
    if args.dry_run:
        return 1 if fehler else 0
    for tag, neu_raw in geschrieben:
        schreibe(R.entry(tag), neu_raw)
    if index_neu_raw is not None and index_neu:
        schreibe(R.index, index_neu_raw)
    ctx.implied.speichern()
    protokolliere(ergebnisse, index_neu, ctx, _bereich_aus_dateien(args.dateien))
    reg = lade_registry()
    for tag, _ in geschrieben:
        reg["tage"].pop(tag, None)          # Kandidaten dieser Tage sind nach dem Schreiben veraltet
    _json_speichern("kandidaten.json", reg)
    if verworfen_neu:
        _json_speichern("verworfen.json", sorted(lade_verworfen() | verworfen_neu))
        print(f"{len(verworfen_neu)} Vorschläge als verworfen vermerkt")
    return 1 if fehler else 0


def _bereich_aus_dateien(dateien):
    """Liegt eine Eingabedatei in temp/personen-auszeichnen/<Bereich>/, ist <Bereich> der Ordner für das Protokoll
    (sonst teilte sich das Protokoll auf Tagesordner auf, wenn ein apply nur einen Tag berührt)."""
    for f in dateien:
        p = Path(f).resolve()
        if p.parent.parent == R.temp.resolve():
            return p.parent.name
    return None


def protokolliere(ergebnisse, index_neu, ctx, bereich=None):
    tage = sorted({e[0] for e in ergebnisse})
    ordner = R.temp / (bereich or bereich_name(tage))
    ordner.mkdir(parents=True, exist_ok=True)
    zeit = dt.datetime.now().isoformat(timespec="seconds")
    with open(ordner / "protokoll.jsonl", "a", encoding="utf-8") as f:
        for tag, i, op, art, info, doc in ergebnisse:
            f.write(json.dumps({"zeit": zeit, "tag": tag, "art": art, "text": info[0] if info else None,
                                "refs": info[1] if info else None, "grund": op.get("grund"),
                                "op": op}, ensure_ascii=False) + "\n")
        for tag, r, impl in index_neu:
            f.write(json.dumps({"zeit": zeit, "tag": tag, "art": "index", "refs": [r], "implied": impl},
                               ensure_ascii=False) + "\n")
        if ctx.ausserhalb:
            f.write(json.dumps({"zeit": zeit, "art": "ausserhalb_register", "refs": sorted(ctx.ausserhalb)}, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------------------------------------
# Korpus: Gelerntes (Namensformen, allusively-Zuordnung, Oberflächen je Jahr)
# ----------------------------------------------------------------------------------------------

def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def allus_schluessel(text):
    ws = [fold(w.strip(_PUNKT)) for w in woerter(text)]
    k = " ".join(w for w in ws if w)
    k = {"kindern": "kinder", "geschwistern": "geschwister"}.get(k, k)
    return k[:-1] if len(k) > 4 and k.endswith("s") else k


def oberflaechen_schluessel(text):
    ws = [fold(w.strip(_PUNKT)) for w in woerter(text) if not ist_titel(w) and not ist_partikel(w)]
    return " ".join(w for w in ws if w)


class Korpus:
    VERSION = 5

    def __init__(self):
        self.lern = {}            # pid -> {gefaltetes Wort: Anzahl}      (aus rs mit ref)
        self.oberfl_jahr = {}     # Oberflächenschlüssel -> {Jahr: {ref: Anzahl}}
        self.allus_tage = {}      # allusively-Schlüssel -> Zahl der Tage
        self.allus_paar = {}      # allusively-Schlüssel -> {pid: Tage, an denen Wort und pid im Index stehen}
        self.kleinwoerter = {}    # gefaltetes Kleinwort -> Anzahl (Gattungswort-Test)
        self.gross = {}           # gefaltetes Großwort -> Anzahl im Text
        self.benannt = {}         # gefaltetes Wort -> Anzahl in Personen-rs
        self.idx = {}             # Tag -> [(ref, implied)]
        self.idx_tage = {}        # pid -> {Tage}
        self.zahlen = {}


def _fingerprint():
    """Der Lernstand hängt nur von Version, Zahl der Einträge und Personenregister ab. Änderungen durch `apply` (neue Refs,
    Index) bauen ihn bewusst nicht neu: Der Lauf lernt vom Ausgangszustand, das hält Monat für Monat 30 s Aufbauzeit
    und Rückkopplung der eigenen Entscheidungen in die Statistik heraus. `scan --neu` baut ihn neu."""
    n = sum(1 for _ in R.editions.glob("entry__*.xml"))
    lp = R.listperson.stat().st_mtime_ns if R.listperson.exists() else 0
    return (Korpus.VERSION, n, lp)


def baue_korpus():
    k = Korpus()
    k.idx = lies_index()
    idx_tage = collections.defaultdict(set)
    for tag, refs in k.idx.items():
        for r, _ in refs:
            idx_tage[r].add(tag)
    k.idx_tage = dict(idx_tage)
    lern = collections.defaultdict(collections.Counter)
    ober = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    a_tage, a_paar = collections.Counter(), collections.defaultdict(collections.Counter)
    klein, gross = collections.Counter(), collections.Counter()
    for f in sorted(R.editions.glob("entry__*.xml")):
        tag = f.stem[7:]
        jahr = int(tag[:4])
        doc = Doc(lies(f), tag)
        klein.update(fold(w) for w in re.findall(r"\b[a-zäöüß]{3,}\b", doc.flat))
        gross.update(fold(w) for w in re.findall(r"\b[A-ZÄÖÜ][a-zäöüß]{2,}\b", doc.flat))
        allus = set()
        for el in doc.elemente("rs"):
            typ = el.attrs.get("type")
            if typ not in ("person", "allusively"):
                continue
            refs = [r.lstrip("#") for r in el.attrs.get("ref", "").split()]
            txt = norm_ws(doc.text_von(el))
            if typ == "allusively":
                allus.add(allus_schluessel(txt))
                continue
            if not refs:
                continue
            ws = [fold(w.rstrip(".")) for w in woerter(txt) if not ist_titel(w) and not ist_partikel(w)]
            for r in refs:
                for w in ws:
                    lern[r][w] += 1
            if len(refs) == 1 and el.attrs.get("subtype") != "implied":
                ober[oberflaechen_schluessel(txt)][jahr][refs[0]] += 1
        for key in allus:
            if not key:
                continue
            a_tage[key] += 1
            for r, impl in k.idx.get(tag, []):
                if not impl:
                    a_paar[key][r] += 1
    k.lern = {p: dict(c) for p, c in lern.items()}
    k.oberfl_jahr = {s: {j: dict(c) for j, c in d.items()} for s, d in ober.items()}
    k.allus_tage = dict(a_tage)
    k.allus_paar = {s: dict(c) for s, c in a_paar.items()}
    k.kleinwoerter = {w: n for w, n in klein.items() if n >= 5}
    k.gross = {w: n for w, n in gross.items() if n >= 5}
    benannt = collections.Counter()
    for c in k.lern.values():
        for w, n in c.items():
            benannt[w] += n
    k.benannt = dict(benannt)
    k.zahlen = {"tage": len(k.idx), "personen_im_index": len(k.idx_tage)}
    return k


def ist_gattungswort(korpus, text):
    """Kommt das Wort überwiegend als gewöhnliches Wort vor (Zimmer, Mann, ganz) statt als Name?"""
    fw = fold(text.strip(_PUNKT + "."))
    if korpus.kleinwoerter.get(fw, 0) >= 20:
        return True
    g = korpus.gross.get(fw, 0)
    return g >= 30 and korpus.benannt.get(fw, 0) / g < 0.35


def lade_korpus(neu=False):
    cache = R.temp / "korpus.pkl"
    fp = _fingerprint()
    if cache.exists() and not neu:
        try:
            with open(cache, "rb") as f:
                d = pickle.load(f)
            if d.get("fp") == fp:
                k = Korpus()
                k.__dict__.update(d["d"])
                k.idx = lies_index()                       # der Index ist klein und immer aktuell
                idx_tage = collections.defaultdict(set)
                for tag, refs in k.idx.items():
                    for r, _ in refs:
                        idx_tage[r].add(tag)
                k.idx_tage = dict(idx_tage)
                return k
        except Exception:
            pass
    k = baue_korpus()
    cache.parent.mkdir(parents=True, exist_ok=True)
    with open(cache, "wb") as f:
        pickle.dump({"fp": fp, "d": dict(k.__dict__)}, f)     # nur Daten, keine Klasse (unabhängig vom Modulnamen)
    return k


# ----------------------------------------------------------------------------------------------
# Haushalte (von der Redaktion bestätigte Paare), Ehepartner-Kandidaten
# ----------------------------------------------------------------------------------------------

_HH_RE = re.compile(r"^\s*[-*]?\s*(pmb\d+)\s*(?:->|→)\s*(pmb\d+)\s*\|\s*([\d-]*)\s*\.\.\s*([\d-]*)\s*\|\s*(\S+)")


def lade_haushalte():
    out = []
    if R.haushalte.exists():
        for z in lies(R.haushalte).splitlines():
            m = _HH_RE.match(z)
            if m:
                out.append({"kopf": m.group(1), "partner": m.group(2), "von": m.group(3), "bis": m.group(4),
                            "beziehung": m.group(5)})
    return out


def baue_nach_index(personen):
    idx = collections.defaultdict(set)
    for p in personen.values():
        for w in p.nachf:
            if len(w) >= 3:
                idx[w].add(p.pid)
    return idx


def tage_nah(tag, tage, spanne=3):
    j = int(tag[:4])
    return sum(1 for t in tage if abs(int(t[:4]) - j) <= spanne)


def ehepartner_kandidaten(korpus, personen, nach_index, haushalte, kopf, tag, idx_set, maximal=6):
    h = personen.get(kopf)
    if h is None or not h.nachf:
        return []
    jahr = int(tag[:4])
    seltenstes = min(h.nachf, key=lambda w: len(nach_index.get(w, ())))
    pool = [personen[p] for p in nach_index.get(seltenstes, ()) if p != kopf and p in personen]
    hh = {(x["kopf"], x["partner"]) for x in haushalte if (not x["von"] or tag >= x["von"]) and (not x["bis"] or tag <= x["bis"])}
    hh |= {(b, a) for a, b in hh}
    out = []
    for p in pool:
        if not h.nachf <= p.nachf:
            continue
        if h.sex and p.sex and h.sex == p.sex and (kopf, p.pid) not in hh:
            continue
        if p.geb and jahr < p.geb + 16:
            continue
        if p.tod and jahr > p.tod:
            continue
        if h.geb and p.geb and abs(h.geb - p.geb) > 40:
            continue
        tage_k = korpus.idx_tage.get(kopf, set())
        tage_p = korpus.idx_tage.get(p.pid, set())
        both = tage_k & tage_p
        out.append({"ref": p.pid, "name": p.anzeige, "jahre": f"{p.geb or ''}–{p.tod or ''}", "sex": p.sex,
                    "im_tag": p.pid in idx_set, "ko_nah": tage_nah(tag, both), "ko_alle": len(both),
                    "haushalt": (kopf, p.pid) in hh})
    out.sort(key=lambda c: (c["haushalt"], c["im_tag"], c["ko_nah"], c["ko_alle"]), reverse=True)
    return out[:maximal]


def beziehungswort(wort, kopf):
    """Beziehungswort für die Beschreibung neuer implied-Personen (»Frau von …«)."""
    w = fold(wort)
    if w in ("frau", "gattin", "gemahlin"):
        return "Frau"
    if w in ("mann", "gatte"):
        return "Mann"
    if w in ("tochter", "tochter"):
        return "Tochter"
    if w in ("sohn", "sohne"):
        return "Sohn"
    if w in ("bruder", "schwester", "mutter", "vater"):
        return wort.capitalize()
    if kopf is not None and kopf.sex == "male":
        return "Frau"
    if kopf is not None and kopf.sex == "female":
        return "Mann"
    return "Ehepartner"


# ----------------------------------------------------------------------------------------------
# Analyse eines Tages
# ----------------------------------------------------------------------------------------------

RsInfo = collections.namedtuple("RsInfo", "el id typ sub refs text tiefe")

FOLGE_RE = re.compile(
    r"(?:\s*\([^)]{0,40}\))?\s*(?:,|und|u\.|mit|sowie|samt|nebst)\s+(?:(?:seiner|ihrer|seine|ihre|dessen|deren)\s+)?"
    r"(?P<w>Frau|Gattin|Gemahlin|Mann|Gatte|Tochter|Töchter|Sohn|Söhne|Bruder|Schwester|Mutter|Vater|Kinder|Kindern|Familie)\b"
    r"(?!\s+[A-ZÄÖÜ])")
POSS_RE = re.compile(
    r"\b(?P<p>seine|seiner|seinen|seinem|ihre|ihrer|ihren|ihrem|dessen|deren)\s+"
    r"(?P<w>Frau|Gattin|Gemahlin|Mann|Gatte|Tochter|Sohn|Bruder|Schwester|Mutter|Vater)\b(?!\s+[A-ZÄÖÜ])")
PRAEPOSITIONEN = frozenset({"bei", "zu", "mit", "von", "nach", "an", "auf", "in", "für", "durch", "über", "zum", "zur", "beim",
                           "vom", "ins", "um", "bis", "aus", "unter", "vor", "neben", "samt", "nebst", "ohne"})
GRUPPENWOERTER = frozenset({"familie", "kinder", "kindern", "töchter", "söhne"})   # in Version 1 nur melden
VERWANDTSCHAFT = frozenset({"mama", "papa", "mutter", "vater", "eltern", "kinder", "kindern", "bruder", "brüder", "schwester",
                            "schwager", "schwägerin", "sohn", "tochter", "onkel", "tante", "neffe", "nichte", "großmama",
                            "großpapa", "geschwister", "buben", "bub", "enkel", "schwiegervater", "schwiegermutter"})
GRUPPE_RE = re.compile(r"\bwir\s+(?P<w>zwei|drei|vier|fünf|sechs|sieben|alle|beide)\b")
_TOK_RE = re.compile(r"[^\s,;:!?()\[\]»«„“”‚‘―–—]+")
STOPP_TOKEN = frozenset({"nm", "vm", "abd", "abds", "mg", "mitt", "dann", "dort", "noch", "auch", "und", "mit", "bei", "zu",
                         "der", "die", "das", "den", "dem", "ein", "eine", "im", "in", "an", "auf", "von", "für", "nach",
                         "ich", "wir", "sie", "er", "es", "ihr", "ihm", "ihn", "uns", "mir", "mich", "dir", "dich"})


class TagDaten:
    def __init__(self, tag, korpus):
        self.tag = tag
        self.raw = lies(R.entry(tag))
        self.doc = Doc(self.raw, tag)
        self.rs = []
        for el in self.doc.elemente("rs"):
            tiefe = sum(1 for a in self.doc._vorfahren(el.parent) if a.name == "rs")
            self.rs.append(RsInfo(el, el.attrs.get("xml:id", ""), el.attrs.get("type", ""), el.attrs.get("subtype", ""),
                                  [r.lstrip("#") for r in el.attrs.get("ref", "").split()],
                                  norm_ws(self.doc.text_von(el)), tiefe))
        self.index = korpus.idx.get(tag, [])
        self.idx_set = {r for r, _ in self.index}
        self.idx_impl = {r for r, i in self.index if i}
        self.eintrag_refs = {r for x in self.rs if x.typ in ("person", "allusively") for r in x.refs}
        self.fehlt = []
        for r, impl in self.index:
            if not impl and r not in self.eintrag_refs and r not in self.fehlt:
                self.fehlt.append(r)
        self.implied_offen = [r for r, impl in self.index if impl and r not in self.eintrag_refs]

    def markiert(self):
        """Textfluss mit eingebetteten Markierungen der Personen-/allusively-rs: ⟦Text|pmb123⟧, ⟦Text|?pNt_…⟧."""
        ev = []
        for x in self.rs:
            if x.typ not in ("person", "allusively"):
                continue
            pre = "i:" if x.sub == "implied" else "a:" if x.typ == "allusively" else ""
            lab = pre + ("+".join(x.refs) if x.refs else "?" + x.id)
            ev.append((x.el.fs, 1, x.tiefe, "⟦"))
            ev.append((x.el.fe, 0, -x.tiefe, "|" + lab + "⟧"))
        flat, out, last = self.doc.flat, [], 0
        for pos, _, _, s in sorted(ev):
            out.append(flat[last:pos])
            out.append(s)
            last = pos
        out.append(flat[last:])
        return "".join(out)

    def kontext(self, a, b, n=36):
        f = self.doc.flat
        t = f[max(0, a - n):a] + "«" + f[a:b] + "»" + f[b:b + n]
        return re.sub(r"[ \t]*\n\s*", " ↵ ", t)

    def tokens(self):
        """(a, b, Wort) aller Wörter in noch nicht ausgezeichnetem Text."""
        for sg in self.doc.segs:
            if not sg.eligible:
                continue
            t = self.doc.flat[sg.fs:sg.fe]
            for m in _TOK_RE.finditer(t):
                yield sg.fs + m.start(), sg.fs + m.end(), m.group(0)


def fingerabdruck(tag, op):
    """Identifiziert eine vorgeschlagene Operation unabhängig von ref/neu/grund (für verworfene Kandidaten)."""
    kern = {k: v for k, v in op.items() if k not in ("ref", "neu", "grund", "tag", "k", "frei", "index", "teile")}
    return hashlib.sha1(json.dumps({"tag": tag, "op": kern}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


class Sammler:
    """Kandidaten eines Tages mit Kennungen »Tag#n« und der Operation, die sie bei Zustimmung ausführen.
    Bereits verworfene Vorschläge (fingerabdruck in `verworfen`) werden nicht erneut angeboten (add -> None)."""

    def __init__(self, tag, verworfen=frozenset()):
        self.tag, self.liste, self.n, self.verworfen, self.unterdrueckt = tag, [], 0, verworfen, 0

    def add(self, op, **meta):
        op = dict(op, tag=self.tag)
        if fingerabdruck(self.tag, op) in self.verworfen:
            self.unterdrueckt += 1
            return None
        self.n += 1
        kid = f"{self.tag}#{self.n}"
        self.liste.append({"id": kid, "op": op, **meta})
        return kid


def lebensinfo(p):
    if p is None:
        return "?"
    s = f"{p.anzeige} ({p.geb or ''}–{p.tod or ''}, {p.sex or '?'}"
    if p.beruf:
        s += ", " + "/".join(b.split("/")[0] for b in p.beruf[:2])
    return s + ")"


def allus_info(korpus, schluessel, pid):
    n = korpus.allus_paar.get(schluessel, {}).get(pid, 0)
    d = korpus.allus_tage.get(schluessel, 0)
    return n, d, (n / d if d else 0.0)


def schwelle_stark(n, rate):
    return n >= 20 and rate >= 0.9


def spans_fuer(td, P, lern, mit_titel=True):
    """Spannen unmarkierten Texts, die zu Person P passen: [(a, b, Stufe)]. Titel davor und weitere
    passende Namenswörter daneben werden einbezogen."""
    toks = list(td.tokens())
    flat = td.doc.flat
    lv = []
    for a, b, w in toks:
        k = w.strip(_PUNKT)
        if not k or not k[0].isupper() or fold(k) in STOPP_TOKEN or len(k) < 2:
            lv.append(0)
            continue
        l = stufe_wort(k, P.formen, lern)
        if l < 2 and w.endswith(".") and len(k) <= 6:
            l = stufe_wort(k + ".", P.formen, lern)
        lv.append(l if l >= 2 else 0)
    spans = []
    i = 0
    while i < len(toks):
        if not lv[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(toks) and lv[j + 1] and flat[toks[j][1]:toks[j + 1][0]] in (" ", "\n", "  ") :
            j += 1
        s = i
        if mit_titel:
            for _ in range(2):
                if s > 0 and flat[toks[s - 1][1]:toks[s][0]] in (" ", "\n") and ist_titel(toks[s - 1][2]):
                    s -= 1
        a, b = toks[s][0], toks[j][1]
        txt = flat[a:b]
        b2 = b
        if txt.endswith(".") and not stufe_wort(txt.rstrip("."), P.formen, lern):
            pass
        elif txt.endswith(".") and stufe_wort(txt.rstrip("."), P.formen, lern) >= 3:
            b2 = b - 1
        spans.append((a, b2, max(lv[i:j + 1])))
        i = j + 1
    return spans


def schnitzler_rollen(vw, personen, tag):
    """pid -> Rollen, in denen die Person am Tag zu Arthur Schnitzler steht (aus den PMB-Relationen, einschließlich
    Schwager/Schwägerin und Schwiegereltern). Leer, wenn keine Verwandtschaftsdaten vorliegen."""
    out = collections.defaultdict(list)
    if vw is None or not vw.vorhanden:
        return out
    kopf = personen.get(SCHNITZLER)
    for r in vw.rel.get(SCHNITZLER, ()):
        if rel_status(r, tag, kopf, personen.get(r.andere)) == "gueltig":
            out[r.andere].append(r.rolle)
    for c in vw.schwager(SCHNITZLER, tag, personen):
        out[c["ref"]].append("Schwager")
    for e in vw.verwandte(SCHNITZLER, "Ehe", tag, personen):
        for q in vw.verwandte(e["ref"], "Elternteil", tag, personen):
            out[q["ref"]].append("Schwiegerelternteil")
    return out


def rolle_passt(rollen, geschlecht_person, wort):
    """Passt eines der Rollen (pid -> Rollenliste) zu einem Verwandtschaftswort? -> Rollentext oder None."""
    wr = wort_rolle(wort)
    if wr is None or not rollen:
        return None
    grund, sex = wr
    if sex and geschlecht_person and sex != geschlecht_person:
        return None
    gesucht = {"Schwager"} if grund == "Schwager" else set(ROLLEN_FUER.get(grund, (grund,)))
    treffer = [r for r in rollen if r in gesucht]
    return f"{wort.strip(_PUNKT)} = {treffer[0]} von Arthur Schnitzler (PMB-Relation)" if treffer else None


def kandidaten_aufgabe2(td, korpus, personen, sammler, auto, vw=None):
    """Index-Personen, die im Eintrag nicht als ref vorkommen (Aufgabe 2), und Wiederholungen (1b).
    Gibt ein Dict mit den Ergebnissen für Bericht und Arbeitspaket zurück."""
    res = {"fehlt": [], "ohne_kandidat": [], "auto": 0}
    lern = korpus.lern
    _rollen = {}

    def rollen_von(pid):
        if "r" not in _rollen:
            _rollen["r"] = schnitzler_rollen(vw, personen, td.tag)
        return _rollen["r"].get(pid, [])
    rs_noref = [x for x in td.rs if not x.refs and x.typ in ("person", "allusively") and x.sub != "implied"]
    erledigt = set()
    marked_by_key = collections.defaultdict(set)
    for x in td.rs:
        if x.typ == "person" and len(x.refs) == 1 and x.sub != "implied":
            marked_by_key[oberflaechen_schluessel(x.text)].add(x.refs[0])
    fehlt_p = [personen[r] for r in td.fehlt if r in personen]
    # Welche Personen (fehlende und ausgezeichnete) passen auf welches rs ohne ref?
    ver_pids = {p.pid for p in fehlt_p} | {r for x in td.rs if x.typ == "person" for r in x.refs}
    def pids_fuer(x):
        if x.typ == "person":
            return {pid for pid in ver_pids if pid in personen and stufe(x.text, personen[pid], lern.get(pid)) >= 2}
        key = allus_schluessel(x.text)
        return {pid for pid in td.idx_set - td.idx_impl if schwelle_stark(*allus_info(korpus, key, pid)[::2])}
    # (1b) Wiederkehr eines schon ausgezeichneten Namens am selben Tag: eindeutige Oberfläche -> set_ref
    for x in rs_noref:
        if x.typ != "person":
            continue
        refs = marked_by_key.get(oberflaechen_schluessel(x.text), set())
        if len(refs) == 1 and not any(stufe(x.text, p, lern.get(p.pid)) >= 2 for p in fehlt_p):
            auto.append({"op": "set_ref", "tag": td.tag, "id": x.id, "ref": next(iter(refs)),
                         "grund": f"gleiche Oberfläche »{x.text}« wie ein ausgezeichnetes rs desselben Tages (Stufe A, Wiederkehr)"})
            erledigt.add(x.id)
    # allusively-rs mit eindeutig starker Zuordnung (Wort <-> Index-Person), auch wenn die Person schon im Text steht
    abgedeckt_allus = set()
    for x in rs_noref:
        if x.typ != "allusively" or x.id in erledigt:
            continue
        key = allus_schluessel(x.text)
        starke = [pid for pid in td.idx_set - td.idx_impl if schwelle_stark(*allus_info(korpus, key, pid)[::2])]
        mittlere = [pid for pid in td.idx_set - td.idx_impl if allus_info(korpus, key, pid)[2] >= 0.5 and allus_info(korpus, key, pid)[0] >= 5]
        if len(starke) == 1 and len(mittlere) == 1:
            n, d, r = allus_info(korpus, key, starke[0])
            auto.append({"op": "set_ref", "tag": td.tag, "id": x.id, "ref": starke[0],
                         "grund": f"allusively »{x.text}«: {n} von {d} Tagen mit diesem Wort haben {starke[0]} im Index (Stufe A)"})
            erledigt.add(x.id)
            abgedeckt_allus.add(starke[0])
    # allusively-rs (Schwager, Tante, Bruder …) mit eindeutiger PMB-Relation zu Arthur Schnitzler unter den Index-Personen
    # ohne ref: Stufe A. Gruppenwörter (Kinder, Eltern, Geschwister) bleiben Stufe B (Mehrfach-ref).
    if vw is not None and vw.vorhanden:
        for x in rs_noref:
            if x.typ != "allusively" or x.id in erledigt or x.text.lower().strip(_PUNKT) in GRUPPEN_WORTE:
                continue
            kand = [p for p in fehlt_p if p.pid not in abgedeckt_allus and rolle_passt(rollen_von(p.pid), p.sex, x.text)]
            if len(kand) == 1:
                p = kand[0]
                auto.append({"op": "set_ref", "tag": td.tag, "id": x.id, "ref": p.pid,
                             "grund": f"allusively »{x.text}« ↔ {rolle_passt(rollen_von(p.pid), p.sex, x.text)}: {p.anzeige}, einzige passende Index-Person ohne ref (Stufe A)"})
                erledigt.add(x.id)
                abgedeckt_allus.add(p.pid)
    # Index-Personen ohne ref im Text
    abgedeckt = set(abgedeckt_allus)
    for p in fehlt_p:
        if p.pid in abgedeckt_allus:
            continue
        lp = lern.get(p.pid)
        cands = []
        for x in rs_noref:
            if x.id in erledigt:
                continue
            if x.typ == "person":
                lv = stufe(x.text, p, lp)
                if lv:
                    cands.append(("rs_ohne_ref", x, lv, None))
            else:
                n, d, r = allus_info(korpus, allus_schluessel(x.text), p.pid)
                rel_txt = rolle_passt(rollen_von(p.pid), p.sex, x.text)
                if n >= 2 or rel_txt:
                    cands.append(("allusively", x, 0, {"assoc": (n, d, r) if n >= 2 else None, "relation": rel_txt}))
        # Stufe A: rs-Kandidaten vom Typ person mit strenger Stufe >= 2, denen sonst keine andere Person passt
        def ist_sicher(c):
            return (c[0] == "rs_ohne_ref" and stufe_streng(c[1].text, p, lp) >= 2 and pids_fuer(c[1]) == {p.pid})
        sicher = [c for c in cands if ist_sicher(c)]
        if sicher and all(ist_sicher(c) for c in cands if c[2] >= 2):
            for c in sicher:
                auto.append({"op": "set_ref", "tag": td.tag, "id": c[1].id, "ref": p.pid,
                             "grund": f"»{c[1].text}« passt eindeutig zu {p.anzeige} (Namensform, Stufe {c[2]}; Stufe A)"})
                erledigt.add(c[1].id)
            abgedeckt.add(p.pid)
            continue
        # unmarkierte Namenstoken
        for a, b, lv in spans_fuer(td, p, lp):
            cands.append(("unmarkiert", (a, b), lv, None))
        # unmarkierte Verwandtschafts-/Rollenwörter, die laut Korpus zu dieser Person gehören
        wanted = {k: allus_info(korpus, k, p.pid) for k in korpus.allus_paar if korpus.allus_paar[k].get(p.pid, 0) >= 3}
        wanted = {k: v for k, v in wanted.items() if v[2] >= 0.3}
        rolle_p = rollen_von(p.pid)
        if wanted or rolle_p:
            for a, b, w in td.tokens():
                if not w[0].isupper():
                    continue
                k = allus_schluessel(w.strip(_PUNKT))
                rel_txt = rolle_passt(rolle_p, p.sex, w) if rolle_p else None
                if k in wanted or rel_txt:
                    cands.append(("verwandtschaft", (a, b), 0, {"assoc": wanted.get(k), "relation": rel_txt}))
        if not cands:
            res["ohne_kandidat"].append(p.pid)
            continue
        eintrag = {"pid": p.pid, "info": lebensinfo(p), "kandidaten": []}
        for art, x, lv, extra in cands[:8]:
            extra = extra if isinstance(extra, dict) else {"assoc": extra, "relation": None}
            if art in ("rs_ohne_ref", "allusively"):
                kid = sammler.add({"op": "set_ref", "id": x.id, "ref": p.pid}, art=art, text=x.text, stufe_name=lv,
                                  assoc=extra["assoc"], relation=extra["relation"], kontext=td.kontext(x.el.fs, x.el.fe))
                if kid:
                    eintrag["kandidaten"].append(kid)
            else:
                a, b = x
                anker = td.doc.anker_fuer(a, b)
                if anker is None:
                    continue
                typ = "person" if art == "unmarkiert" else "allusively"
                gattung = art == "unmarkiert" and ist_gattungswort(korpus, td.doc.flat[a:b])
                kid = sammler.add({"op": "wrap", "anker": anker, "ref": p.pid, "typ": typ}, art=art, text=td.doc.flat[a:b],
                                  stufe_name=lv, assoc=extra["assoc"], relation=extra["relation"], gattungswort=gattung,
                                  kontext=td.kontext(a, b))
                if kid:
                    eintrag["kandidaten"].append(kid)
        if eintrag["kandidaten"]:
            res["fehlt"].append(eintrag)
        else:
            res["ohne_kandidat"].append(p.pid)
    for r in td.fehlt:
        if r not in personen and r not in abgedeckt:
            res["ohne_kandidat"].append(r)
    # (1b) Wiederkehr: unmarkierter Text, der zu einer schon ausgezeichneten Person desselben Tages passt
    res["wiederkehr"] = []
    gesehen = set()
    for x in td.rs:
        if x.typ != "person" or x.sub == "implied" or len(x.refs) != 1 or x.refs[0] in gesehen:
            continue
        r = x.refs[0]
        gesehen.add(r)
        P = personen.get(r)
        if P is None:
            continue
        for a, b, lv in spans_fuer(td, P, lern.get(r), mit_titel=False):
            text = td.doc.flat[a:b]
            if lv < 3 or len(text.strip(_PUNKT)) < 4:
                continue
            andere = [q for q in ver_pids if q != r and q in personen and stufe(text, personen[q], lern.get(q)) >= 2]
            anker = td.doc.anker_fuer(a, b)
            if anker is None:
                continue
            gattung = ist_gattungswort(korpus, text)
            kid = sammler.add({"op": "wrap", "anker": anker, "ref": r, "typ": "person"}, art="wiederkehr", text=text,
                              stufe_name=lv, mehrdeutig=bool(andere), gattungswort=gattung, bekannt_als=P.anzeige,
                              kontext=td.kontext(a, b))
            if kid:
                res["wiederkehr"].append(kid)
    res["hinweis_woerter"] = []
    if res["ohne_kandidat"]:
        for a, b, w in td.tokens():
            k = w.strip(_PUNKT).lower()
            if k in VERWANDTSCHAFT or k.rstrip("s") in VERWANDTSCHAFT:
                res["hinweis_woerter"].append(f"»{w.strip(_PUNKT)}« …{td.kontext(a, b, 14)}…")
    res["auto"] = len(auto)
    res["abgedeckt_auto"] = sorted(abgedeckt)
    return res


def flags_aufgabe1(td, korpus, personen, impl_ids, register=None):
    """Auffälligkeiten bestehender Auszeichnung (nur melden)."""
    out = []
    jahr = int(td.tag[:4])
    for x in td.rs:
        if x.typ not in ("person", "allusively") or not x.refs:
            continue
        for r in x.refs:
            p = personen.get(r)
            if p is None and r not in impl_ids and r not in td.idx_impl:
                out.append({"art": "ref_unbekannt", "rs": x.id, "text": x.text, "ref": r})
            elif p is not None and p.geb and jahr < p.geb:
                out.append({"art": "vor_geburt", "rs": x.id, "text": x.text, "ref": r, "name": p.anzeige, "geb": p.geb})
            if p is not None and register is not None and r not in register and r not in impl_ids:
                out.append({"art": "nicht_im_register", "rs": x.id, "text": x.text, "ref": r, "name": p.anzeige})
        if x.typ == "person" and x.sub != "implied" and len(x.refs) == 1:
            r = x.refs[0]
            if r not in td.idx_set:
                out.append({"art": "nicht_im_index", "rs": x.id, "text": x.text, "ref": r})
            key = oberflaechen_schluessel(x.text)
            jahre = korpus.oberfl_jahr.get(key, {})
            nah = collections.Counter()
            for j in range(jahr - 2, jahr + 3):
                for rr, n in jahre.get(j, {}).items():
                    nah[rr] += n
            nah[r] -= 1
            tot = sum(v for v in nah.values() if v > 0)
            if tot >= 5:
                top, n = max(nah.items(), key=lambda kv: kv[1])
                if top != r and n / tot >= 0.95:
                    out.append({"art": "ausreisser", "rs": x.id, "text": x.text, "ref": r, "ueblich": top,
                                "belege": f"{n}/{tot}"})
    for r, _ in td.index:
        if not REF_RE.fullmatch(r):
            out.append({"art": "alt_id_im_index", "ref": r})
    return out


def kandidaten_aufgabe3(td, korpus, personen, nach_index, haushalte, sammler, vw=None, register=frozenset()):
    """Implizite Personen: Auslöser, Kopfpersonen und Kandidaten (Aufgabe 3). Kandidaten kommen vorrangig aus den
    PMB-Relationen (vw), sonst aus Namen und gemeinsamer Erwähnung."""
    trig, gruppen = [], []
    doc = td.doc
    marked = [x for x in td.rs if x.typ == "person" and x.refs and x.sub != "implied"]

    def schon_implied(el):
        return any(a.name == "rs" and a.attrs.get("subtype") == "implied" for a in doc._vorfahren(el.parent))

    hh_paare = {(x["kopf"], x["partner"]) for x in haushalte if (not x["von"] or td.tag >= x["von"]) and (not x["bis"] or td.tag <= x["bis"])}
    hh_paare |= {(b_, a_) for a_, b_ in hh_paare}

    def anreichern(c, kopf_pid):
        tage_k = korpus.idx_tage.get(kopf_pid, set())
        tage_p = korpus.idx_tage.get(c["ref"], set())
        both = tage_k & tage_p
        c.setdefault("im_tag", c["ref"] in td.idx_set)
        c.setdefault("ko_nah", tage_nah(td.tag, both))
        c.setdefault("ko_alle", len(both))
        c.setdefault("haushalt", (kopf_pid, c["ref"]) in hh_paare)
        c["im_register"] = c["ref"] in register or not register
        return c

    def vorschlag(kopf_refs, wort, tag_idx_implied):
        kopf = personen.get(kopf_refs[0]) if kopf_refs else None
        rel = beziehungswort(wort, kopf)
        cands, voris, notiz = [], None, None
        nutze_rel = kopf is not None and vw is not None and vw.vorhanden
        grundrolle = None
        if nutze_rel:
            wort_f = wort or ("Mann" if kopf.sex == "female" else "Frau")
            grundrolle, gruppe, rc = vw.zu_wort(kopf.pid, wort_f, td.tag, personen)
            cands = [anreichern(c, kopf.pid) for c in rc]
            if not cands and grundrolle:
                ungueltig = vw.verwandte(kopf.pid, grundrolle if grundrolle != "Schwager" else "Ehe", td.tag, personen,
                                         wort_rolle(wort_f)[1] if wort_rolle(wort_f) else None, nur_gueltige=False)
                ungueltig = [c for c in ungueltig if c["status"] != "gueltig"]
                if ungueltig:
                    notiz = "PMB kennt, aber nicht gültig am Datum: " + "; ".join(
                        f"{c['name']} ({c['text']}, {c['status']})" for c in ungueltig[:3])
        # Haushalt (haushalte.md) und Index-implied des Tages haben Vorrang
        hh = [c for c in cands if c["haushalt"]]
        if len(hh) == 1:
            voris = {"ref": hh[0]["ref"], "grund": "Haushalt bestätigt (haushalte.md)"}
        if voris is None and kopf is not None:
            for r in td.implied_offen:
                pr = personen.get(r)
                if pr is None or not (kopf.sex and pr.sex) or kopf.sex != pr.sex or grundrolle not in (None, "Ehe"):
                    voris = {"ref": r, "grund": "Index nennt diese Person als implied für den Tag"}
                    break
        if voris is None and cands:
            if len(cands) == 1:
                c = cands[0]
                voris = {"ref": c["ref"], "grund": f"PMB-Relation: {c['text']}" + (" (Datum unsicher)" if c.get("datum_unsicher") else "")}
            else:
                imtag = [c for c in cands if c["im_tag"]]
                if len(imtag) == 1:
                    voris = {"ref": imtag[0]["ref"], "grund": f"PMB-Relation ({imtag[0]['text']}), steht im Index des Tages"}
                else:
                    voris = {"unklar": True, "grund": f"{len(cands)} Personen in dieser Rolle laut PMB: ref wählen oder neu angeben"}
        if voris is None and kopf is not None and (grundrolle in (None, "Ehe")):
            # keine PMB-Relation verfügbar oder bekannt: Namen und gemeinsame Erwähnung (schwächer)
            relat_bekannt = bool(nutze_rel and vw.verwandte(kopf.pid, "Ehe", td.tag, personen, nur_gueltige=False))
            if not relat_bekannt and rel in ("Frau", "Mann", "Ehepartner"):
                nc = ehepartner_kandidaten(korpus, personen, nach_index, haushalte, kopf.pid, td.tag, td.idx_set)
                for c in nc:
                    c["quelle"] = "Name/Ko-Erwähnung (keine PMB-Relation bekannt)"
                    c["im_register"] = True
                cands = nc
                starke = [c for c in cands if c["haushalt"] or c["im_tag"]]
                if len(starke) == 1:
                    voris = {"ref": starke[0]["ref"], "grund": "steht im Index des Tages"}
                elif len(cands) == 1:
                    voris = {"ref": cands[0]["ref"], "grund": "einziger Kandidat mit gleichem Nachnamen (keine PMB-Relation bekannt)"}
                elif len(cands) > 1 and cands[0]["ko_nah"] >= 3 and cands[0]["ko_nah"] >= 2 * max(1, cands[1]["ko_nah"]):
                    voris = {"ref": cands[0]["ref"], "grund": f"deutlich häufigste gemeinsame Erwähnung ({cands[0]['ko_nah']} Tage ±3 Jahre; keine PMB-Relation bekannt)"}
        if voris is None and kopf is not None:
            if any(c.get("ko_nah", 0) >= 3 or c.get("im_tag") or c.get("haushalt") for c in cands):
                voris = {"unklar": True, "grund": "mehrere plausible Kandidaten ohne klaren Sieger: ref wählen oder neu angeben"}
            else:
                voris = {"neu": f"{rel} von {kopf.anzeige}", "grund": "kein passender Treffer in PMB-Relationen/listperson.xml" + (f" ({notiz})" if notiz else "")}
        elif voris is not None and notiz and "ref" not in voris:
            voris["grund"] += f" ({notiz})"
        return rel, cands, voris

    # (a) Familien-/Genitivform eines ausgezeichneten Namens
    for x in marked:
        if len(x.refs) != 1 or schon_implied(x.el):
            continue
        p = personen.get(x.refs[0])
        if p is None or not p.nach:
            continue
        toks = [t for t in x.text.split() if not ist_titel(t) and not ist_partikel(t)]
        if len(toks) != 1:
            continue
        kinder = {e.name for e in doc.els if e.parent == x.el.idx}
        if "forename" in kinder and "surname" not in kinder:
            continue            # Vorname im Genitiv (»Jacobs Gespräch«), keine Familienform
        ft = fold(toks[0].strip(_PUNKT)).replace("-", "").replace("’", "").replace("'", "")
        pn = fold(p.nach).replace("-", "").replace(" ", "")
        if ft.endswith("s") and ft[:-1] == pn and not pn.endswith("s"):
            rel, cands, voris = vorschlag([p.pid], "", None)
            op = {"op": "implied", "um_rs": x.id}
            op.update({k: v for k, v in (voris or {}).items() if k in ("ref", "neu")})
            vorwort = re.findall(r"[\wÄÖÜäöüß]+", doc.flat[max(0, x.el.fs - 25):x.el.fs])
            praep = bool(vorwort) and vorwort[-1].lower() in PRAEPOSITIONEN
            kid = sammler.add(op, art="familienform", kopf=p.pid, kopf_name=p.anzeige, text=x.text,
                              kontext=td.kontext(x.el.fs, x.el.fe, 50), kandidaten=cands, vorschlag=voris, beziehung=rel,
                              nach_praep=praep)
            if kid:
                trig.append(kid)
    # (b) Folgewort direkt hinter einer ausgezeichneten Person ("X und Frau")
    for x in marked:
        m = FOLGE_RE.match(doc.flat, x.el.fe)
        if not m:
            continue
        a, b = m.start("w"), m.end("w")
        k = bisect.bisect_right(doc._seg_fs, a) - 1
        if k < 0 or not doc.segs[k].eligible or b > doc.segs[k].fe:
            continue
        if m.group("w").lower() in GRUPPENWOERTER:
            gruppen.append({"text": f"{x.text} … {m.group('w')}", "kontext": td.kontext(x.el.fs, b, 40)})
            continue
        anker = doc.anker_fuer(a, b)
        if anker is None:
            continue
        rel, cands, voris = vorschlag(x.refs, m.group("w"), None)
        op = {"op": "implied", "anker": anker}
        op.update({k2: v for k2, v in (voris or {}).items() if k2 in ("ref", "neu")})
        kid = sammler.add(op, art="folgewort", kopf=x.refs[0], kopf_name=lebensinfo(personen.get(x.refs[0])),
                          text=m.group("w"), kontext=td.kontext(x.el.fs, b, 40), kandidaten=cands, vorschlag=voris,
                          beziehung=rel)
        if kid:
            trig.append(kid)
    # (c) Besitzanzeigende Fügung ("mit seiner Frau"): Kopf = letzte ausgezeichnete Person davor
    for m in POSS_RE.finditer(doc.flat):
        a, b = m.start("w"), m.end("w")
        k = bisect.bisect_right(doc._seg_fs, a) - 1
        if k < 0 or not doc.segs[k].eligible or b > doc.segs[k].fe:
            continue
        vor = [x for x in marked if x.el.fe <= m.start() and m.start() - x.el.fe <= 250]
        pron = m.group("p").lower()
        mann = pron.startswith(("sein", "dessen"))
        vor = [x for x in vor if (personen.get(x.refs[0]) is None or not personen[x.refs[0]].sex
                                  or personen[x.refs[0]].sex == ("male" if mann else "female"))]
        anker = doc.anker_fuer(a, b)
        if anker is None:
            continue
        kopf = vor[-1].refs if vor else []
        rel, cands, voris = vorschlag(kopf, m.group("w"), None) if kopf else (beziehungswort(m.group("w"), None), [], None)
        op = {"op": "implied", "anker": anker}
        if voris:
            op.update({k2: v for k2, v in voris.items() if k2 in ("ref", "neu")})
        kid = sammler.add(op, art="besitz", kopf=kopf[0] if kopf else None,
                          kopf_name=lebensinfo(personen.get(kopf[0])) if kopf else "unklar", text=m.group(0),
                          kontext=td.kontext(m.start(), b, 50), kandidaten=cands, vorschlag=voris, beziehung=rel,
                          unsicher=True)
        if kid:
            trig.append(kid)
    # (d) Gruppenwörter (nur melden)
    for m in GRUPPE_RE.finditer(doc.flat):
        a, b = m.start("w"), m.end("w")
        k = bisect.bisect_right(doc._seg_fs, a) - 1
        if k < 0 or not doc.segs[k].eligible or b > doc.segs[k].fe:
            continue
        gruppen.append({"text": m.group(0), "kontext": td.kontext(m.start(), b, 60)})
    return {"ausloeser": trig, "gruppen": gruppen, "implied_ohne_rs": td.implied_offen}


# ----------------------------------------------------------------------------------------------
# Kandidaten-Register (Verbindung zwischen scan und apply)
# ----------------------------------------------------------------------------------------------

def sha1_datei(tag):
    return hashlib.sha1(lies(R.entry(tag)).encode("utf-8")).hexdigest()


def _json_datei(name, standard):
    p = R.temp / name
    if p.exists():
        try:
            return json.loads(lies(p))
        except Exception:
            pass
    return standard


def _json_speichern(name, data):
    R.temp.mkdir(parents=True, exist_ok=True)
    schreibe(R.temp / name, json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def lade_registry():
    return _json_datei("kandidaten.json", {"tage": {}})


def lade_verworfen():
    return set(_json_datei("verworfen.json", []))


def loese_kandidat(it, reg, verworfen_neu):
    """Entscheidung {"k": "Tag#n", ["ref"|"neu"], ["verwerfen"], …} -> vollständige Operation (oder None)."""
    kid = it["k"]
    tag = kid.split("#", 1)[0]
    tagrec = reg.get("tage", {}).get(tag)
    if not tagrec or kid not in tagrec["kandidaten"]:
        raise PaError(f"Kandidat {kid} unbekannt – erst `pa.py scan` für diesen Tag ausführen", "kandidat")
    if tagrec["sha1"] != sha1_datei(tag):
        raise PaError(f"Kandidat {kid}: entry__{tag}.xml hat sich seit dem scan geändert – scan wiederholen", "kandidat")
    cand = tagrec["kandidaten"][kid]
    if it.get("verwerfen"):
        verworfen_neu.add(fingerabdruck(tag, cand["op"]))
        return None
    op = dict(cand["op"])
    for key in ("ref", "typ", "teile", "ohne_teile", "frei", "index", "grund", "um_rs", "anker"):
        if key in it:
            op[key] = it[key]
    if "neu" in it:
        op.pop("ref", None)
        op["neu"] = it["neu"]
    if op["op"] == "implied" and "ref" not in op and "neu" not in op:
        raise PaError(f"Kandidat {kid}: implied ohne ref/neu – Vorschlag fehlt, ref oder neu angeben", "kandidat")
    op["k"] = kid
    return op


def lade_ops(dateien, verworfen_neu=None):
    verworfen_neu = verworfen_neu if verworfen_neu is not None else set()
    items = []
    for f in dateien:
        data = json.loads(lies(f))
        lst = data.get("ops") if isinstance(data, dict) else data
        if not isinstance(lst, list):
            raise PaError(f"{f}: erwartet {{\"ops\": [...]}} oder eine Liste", "json")
        items += lst
    reg = lade_registry()
    ops, fehler = [], []
    for it in items:
        if "k" in it:
            try:
                op = loese_kandidat(it, reg, verworfen_neu)
            except PaError as ex:
                fehler.append(str(ex))
                continue
            if op is not None:
                ops.append(op)
        else:
            ops.append(it)
    return ops, fehler


# ----------------------------------------------------------------------------------------------
# scan
# ----------------------------------------------------------------------------------------------

def _kurz(s, n=70):
    s = re.sub(r"\s+", " ", s)
    return s if len(s) <= n else s[:n - 1] + "…"


GRUPPEN_ZEIGEN = False
register_gl = frozenset()


def render_tag(td, personen, sam, auto, r2, f1, r3):
    z = []
    z.append(f"### {td.tag}")
    z.append(re.sub(r"\s*\n\s*", " ", td.markiert()).strip())
    st = []
    for r, impl in td.index:
        p = personen.get(r)
        name = p.anzeige if p else "?"
        ok = r in td.eintrag_refs
        st.append(f"{r} {name}{' (implied)' if impl else ''} {'✓' if ok else '✗'}")
    if st:
        z.append("Index: " + " | ".join(st))
    by_id = {c["id"]: c for c in sam.liste}
    if r2:
        if auto:
            z.append(f"Stufe A (automatisch, steht in auto.json): {len(auto)}× " +
                     "; ".join(f"{a['id']}→{a['ref']} »{_kurz(next((x.text for x in td.rs if x.id == a['id']), ''), 24)}«" for a in auto[:6]) +
                     ("; …" if len(auto) > 6 else ""))
        geteilt = collections.defaultdict(list)
        for e in r2["fehlt"]:
            for kid in e["kandidaten"]:
                if by_id[kid]["op"]["op"] == "set_ref":
                    geteilt[by_id[kid]["op"]["id"]].append(e["pid"])
        for e in r2["fehlt"]:
            z.append(f"- fehlt: {e['pid']} {e['info']}")
            for kid in e["kandidaten"]:
                c = by_id[kid]
                extra = ""
                if c.get("assoc"):
                    n, d, rate = c["assoc"]
                    extra = f" (Wort↔Person: {n}/{d} Tage)"
                if c.get("relation"):
                    extra += f" [{c['relation']}]"
                if c.get("gattungswort"):
                    extra += " GATTUNGSWORT?"
                andere = [q for q in geteilt.get(c["op"].get("id"), []) if q != e["pid"]]
                if andere:
                    extra += f" (dasselbe rs ist auch Kandidat für {', '.join(andere)}: bei beiden Personen ref als Liste in EINER Entscheidung)"
                z.append(f"  - [{kid}] {c['art']} »{_kurz(c['text'], 40)}« Stufe {c.get('stufe_name', 0)}{extra}  …{c['kontext']}…")
        for kid in r2.get("wiederkehr", []):
            c = by_id[kid]
            extra = (" MEHRDEUTIG (passt auch auf eine andere Person des Tages)" if c.get("mehrdeutig") else "") + \
                    (" GATTUNGSWORT?" if c.get("gattungswort") else "")
            z.append(f"- Wiederkehr? [{kid}] »{_kurz(c['text'], 30)}« → {c['op']['ref']} {c['bekannt_als']} (am selben Tag schon ausgezeichnet){extra}  …{c['kontext']}…")
        if r2["ohne_kandidat"]:
            z.append("- ohne Kandidat im Text: " + "; ".join(f"{pid} {lebensinfo(personen.get(pid))}" for pid in r2["ohne_kandidat"]))
            if r2.get("hinweis_woerter"):
                z.append("  Hinweis, unmarkierte Verwandtschaftswörter (ggf. freie Operation mit typ allusively): " + "; ".join(r2["hinweis_woerter"][:5]))
    if f1:
        for f in f1:
            z.append("- Prüfung: " + f["art"] + " " + " ".join(f"{k}={v}" for k, v in f.items() if k != "art"))
    if r3:
        for kid in r3["ausloeser"]:
            c = by_id[kid]
            vs = c.get("vorschlag") or {}
            hinweis = ""
            if c["art"] == "familienform":
                hinweis = " (nach Präposition)" if c.get("nach_praep") else " (KEINE Präposition davor – eher Possessiv?)"
            z.append(f"- implied? [{kid}] {c['art']} »{_kurz(c['text'], 40)}«{hinweis} Kopf: {c.get('kopf_name')}  …{c['kontext']}…")
            if vs.get("ref"):
                pr = personen.get(vs["ref"])
                ausserhalb = " – NICHT im Tagebuch-Register (in der PMB der Sammlung hinzufügen)" if register_gl and vs["ref"] not in register_gl else ""
                z.append(f"    Vorschlag: ref {vs['ref']} {pr.anzeige if pr else '?'} – {vs['grund']}{ausserhalb}")
            elif vs.get("neu"):
                z.append(f"    Vorschlag: neue Person »{vs['neu']}« – {vs['grund']}")
            elif vs.get("unklar"):
                z.append(f"    Kein Vorschlag: {vs['grund']}")
            for k in c.get("kandidaten", [])[:4]:
                quelle = f"{k['text']}" if k.get("quelle") == "PMB-Relation" else k.get("quelle", "")
                z.append(f"    Kandidat {k['ref']} {k['name']} ({k['jahre']}; {quelle}{', im Index des Tages' if k['im_tag'] else ''}, "
                         f"zusammen erwähnt {k['ko_nah']} Tage ±3 J., {k['ko_alle']} gesamt{', Haushalt bestätigt' if k['haushalt'] else ''}"
                         f"{', NICHT im Tagebuch-Register' if not k.get('im_register', True) else ''})")
        if r3["implied_ohne_rs"]:
            z.append("- Index-implied ohne rs im Text: " + "; ".join(f"{r} {lebensinfo(personen.get(r))}" for r in r3["implied_ohne_rs"]))
        if r3["gruppen"] and GRUPPEN_ZEIGEN:
            for g in r3["gruppen"]:
                z.append(f"- Gruppenwort (nur melden): »{g['text']}« …{g['kontext']}…")
        elif r3["gruppen"]:
            z.append(f"- Gruppenwörter (nur melden, mit --gruppen aufgelistet): {len(r3['gruppen'])}")
    z.append("")
    return "\n".join(z)


def lade_personenmodell():
    """-> (Verwandtschaft, Personen (Register + Verwandte der gekürzten PMB-Liste), Register-IDs, Nachnamen-Index).
    Das Register (indices/listperson.xml) hat Vorrang; Verwandte außerhalb des Registers sind nur zum Nachschlagen da."""
    vw = Verwandtschaft()
    reg = lade_personen()
    personen = dict(vw.personen)
    personen.update(reg)
    return vw, personen, set(reg), baue_nach_index(reg)


def cmd_scan(args):
    tage = bereich_tage(args.bereich)
    if not tage:
        print(f"Keine Einträge für »{args.bereich}«", file=sys.stderr)
        return 2
    global GRUPPEN_ZEIGEN, register_gl
    GRUPPEN_ZEIGEN = bool(args.gruppen)
    aufg = {int(x) for x in str(args.aufgaben).split(",") if x.strip()}
    korpus = lade_korpus(args.neu)
    vw, personen, register, nach_index = lade_personenmodell()
    register_gl = frozenset(register)
    if not vw.vorhanden and 3 in aufg:
        print("Hinweis: keine Verwandtschaftsdaten (data/verwandtschaft-*): Ehepartner nur über Namen; "
              "`pa.py kuerzen --quelle temp-indices` erzeugt sie.", file=sys.stderr)
    haushalte = lade_haushalte()
    impl_ids = ImpliedListe().ids()
    verworfen = lade_verworfen()
    name = bereich_name(tage, args.bereich)
    ordner = R.temp / name
    ordner.mkdir(parents=True, exist_ok=True)
    reg = lade_registry()
    md, auto_alle, st = [], [], collections.Counter()
    tage_mit = []
    for tag in tage:
        td = TagDaten(tag, korpus)
        sam, auto = Sammler(tag, verworfen), []
        r2 = kandidaten_aufgabe2(td, korpus, personen, sam, auto, vw) if 2 in aufg else None
        f1 = flags_aufgabe1(td, korpus, personen, impl_ids, register) if 1 in aufg else None
        r3 = kandidaten_aufgabe3(td, korpus, personen, nach_index, haushalte, sam, vw, register) if 3 in aufg else None
        arbeit = bool(auto or sam.liste or f1 or (r2 and r2["ohne_kandidat"]) or (r3 and r3["implied_ohne_rs"]))
        reg["tage"].pop(tag, None)
        if not arbeit:
            continue
        tage_mit.append(tag)
        reg["tage"][tag] = {"sha1": sha1_datei(tag), "kandidaten": {c["id"]: c for c in sam.liste}}
        auto_alle += auto
        md.append(render_tag(td, personen, sam, auto, r2, f1, r3))
        st["auto (Stufe A)"] += len(auto)
        st["Kandidaten (Stufe B)"] += sum(1 for c in sam.liste if c["op"]["op"] != "implied")
        st["implied-Auslöser"] += sum(1 for c in sam.liste if c["op"]["op"] == "implied")
        st["Index-Personen ohne Kandidat (Stufe C)"] += len(r2["ohne_kandidat"]) if r2 else 0
        st["Prüfbefunde Aufgabe 1"] += len(f1 or [])
        st["Index-implied ohne rs"] += len(r3["implied_ohne_rs"]) if r3 else 0
    _json_speichern("kandidaten.json", reg)
    kopf = [f"# Arbeitspaket {name}", "",
            "Legende: ⟦Text|pmb123⟧ = ausgezeichnet; ⟦Text|?pNt_…⟧ = rs ohne ref (xml:id nach ?); a: = allusively; i: = implied;",
            "Index: ✓ = Person steht im Text, ✗ = fehlt. Entscheidungen per Kandidaten-Kennung [Tag#n] (siehe SKILL.md).", "",
            f"Tage mit Arbeit: {len(tage_mit)} von {len(tage)}", ""]
    schreibe(ordner / "arbeitspaket.md", "\n".join(kopf + md) + "\n")
    schreibe(ordner / "auto.json", json.dumps({"ops": auto_alle}, ensure_ascii=False, indent=1) + "\n")
    print(f"Bereich {name}: {len(tage)} Tage, davon {len(tage_mit)} mit Arbeit")
    for k, v in st.items():
        print(f"  {k}: {v}")
    print(f"Arbeitspaket: {ordner / 'arbeitspaket.md'}")
    print(f"Stufe A (zum Anwenden): {ordner / 'auto.json'}")
    return 0


# ----------------------------------------------------------------------------------------------
# verify
# ----------------------------------------------------------------------------------------------

def git_roh(relpfad):
    r = subprocess.run(["git", "-C", str(R.root), "show", f"HEAD:{relpfad}"], capture_output=True)
    return r.stdout.decode("utf-8") if r.returncode == 0 else None


def geaenderte_tage():
    r = git("diff", "--name-only", "HEAD", "--", "editions")
    return sorted(re.findall(r"entry__(\d{4}-\d{2}-\d{2})\.xml", r.stdout))


def cmd_verify(args):
    probleme, notizen = [], []
    nur = set(bereich_tage(args.bereich)) if args.bereich else None
    tage = [t for t in geaenderte_tage() if nur is None or t in nur]
    register = set(re.findall(r'xml:id="(pmb\d+)"', lies(R.listperson)))
    bekannt = register | (set(re.findall(r'xml:id="(pmb\d+)"', lies(R.verw_personen))) if R.verw_personen.exists() else set())
    impl = ImpliedListe().ids()
    idx_neu = lies_index()
    neue_ids_alle = set()
    ausserhalb = set()
    for tag in tage:
        alt_raw = git_roh(f"editions/entry__{tag}.xml")
        if alt_raw is None:
            continue
        try:
            alt, neu = Doc(alt_raw, tag), Doc(lies(R.entry(tag)), tag)
        except PaError as ex:
            probleme.append(f"{tag}: {ex}")
            continue
        if alt.raw == neu.raw:
            continue
        if neu.flat != alt.flat:
            probleme.append(f"{tag}: Textfluss des body verändert")
        if alt.raw[:alt.body.start] != neu.raw[:neu.body.start] or alt.raw[alt.body.end:] != neu.raw[neu.body.end:]:
            probleme.append(f"{tag}: Text außerhalb des body verändert")
        ids_alt = {el.attrs.get("xml:id") for el in alt.els if el.name == "rs" and el.attrs.get("xml:id")}
        neue = {el.attrs["xml:id"] for el in neu.els if el.name == "rs" and el.attrs.get("xml:id") and el.attrs["xml:id"] not in ids_alt}
        gesetzt = {el.attrs["xml:id"] for el in neu.els if el.name == "rs" and el.attrs.get("xml:id") in ids_alt
                   and el.attrs.get("ref") and not next(a for a in alt.els if a.attrs.get("xml:id") == el.attrs["xml:id"]).attrs.get("ref")}
        if normiert(alt, set(), set()) != normiert(neu, neue, gesetzt):
            probleme.append(f"{tag}: Änderung über neue rs, neue Kindelemente und neue ref-Attribute hinaus")
        neue_ids_alle |= neue
        tagesindex = {r for r, _ in idx_neu.get(tag, [])}
        for el in neu.els:
            xid = el.attrs.get("xml:id")
            if el.name != "rs" or xid not in neue | gesetzt:
                continue
            typ = el.attrs.get("type")
            if typ not in ("person", "allusively"):
                probleme.append(f"{tag}: {xid} hat type={typ!r}")
            if xid in neue and not re.fullmatch(r"pNt_\d{5,}" if typ == "person" else r"rst_\d{5,}", xid):
                probleme.append(f"{tag}: {xid} passt nicht zum Schema für type={typ}")
            if el.attrs.get("subtype") not in (None, "implied"):
                probleme.append(f"{tag}: {xid} hat subtype={el.attrs.get('subtype')!r}")
            refs = [r.lstrip("#") for r in el.attrs.get("ref", "").split()]
            if not refs:
                probleme.append(f"{tag}: {xid} ohne ref")
            for r in refs:
                if not REF_RE.fullmatch(r) or (r not in bekannt and r not in impl and r not in tagesindex):
                    probleme.append(f"{tag}: {xid} ref {r} nicht auflösbar")
                elif r.startswith("pmb") and r not in register:
                    ausserhalb.add(r)
    if neue_ids_alle:
        zaehler = collections.Counter()
        rx = re.compile(r'xml:id="((?:pNt|rst)_\d+)"')
        for f in R.editions.glob("entry__*.xml"):
            for i in rx.findall(lies(f)):
                if i in neue_ids_alle:
                    zaehler[i] += 1
        for i, n in zaehler.items():
            if n > 1:
                probleme.append(f"xml:id {i} kommt {n}× im Korpus vor")
    # Index gegen HEAD
    alt_idx_raw = git_roh("indices/index_person_day.xml")
    if alt_idx_raw is not None and alt_idx_raw != lies(R.index):
        alt_idx = lies_index(alt_idx_raw)
        for tag, refs in alt_idx.items():
            if tag not in idx_neu or not set(refs) <= set(idx_neu[tag]):
                probleme.append(f"Index {tag}: vorhandene Refs wurden entfernt oder verändert")
        if list(idx_neu) != sorted(idx_neu):
            probleme.append("Index: Items nicht mehr in Datumsreihenfolge")
        for tag, refs in idx_neu.items():
            if tag in alt_idx and refs != alt_idx[tag]:
                rs_ = [r for r, _ in refs]
                if len(rs_) != len(set(rs_)) and len(set(r for r, _ in alt_idx[tag])) == len([r for r, _ in alt_idx[tag]]):
                    probleme.append(f"Index {tag}: neue doppelte Refs")
        notizen.append("Index gegen HEAD geprüft")
    alt_impl = git_roh("indices/implied-persons.txt")
    if R.implied.exists():
        zeilen = [z for z in lies(R.implied).splitlines() if z.strip()]
        ids = [m.group(1) for z in zeilen if (m := ImpliedListe.ZEILE.match(z))]
        if len(ids) != len(zeilen):
            probleme.append("implied-persons.txt: Zeilen im falschen Format")
        if len(ids) != len(set(ids)):
            probleme.append("implied-persons.txt: doppelte Kennungen")
        if alt_impl is not None and not lies(R.implied).startswith(alt_impl.rstrip("\n") + "\n") and lies(R.implied) != alt_impl:
            notizen.append("implied-persons.txt: bestehende Zeilen weichen von HEAD ab (Redaktion hat sie bearbeitet?)")
    if ausserhalb:
        notizen.append(f"{len(ausserhalb)} neu verwendete PMB-Personen stehen nicht in indices/listperson.xml "
                       f"(`pa.py register-luecken` listet sie): " + ", ".join(sorted(ausserhalb)[:8]) + (" …" if len(ausserhalb) > 8 else ""))
    print(f"{len(tage)} geänderte Tage geprüft" + (" (Bereich eingeschränkt)" if nur else ""))
    for n in notizen:
        print("  Hinweis:", n)
    if probleme:
        print(f"{len(probleme)} Probleme:")
        for p in probleme[:60]:
            print("  ", p)
        return 1
    print("keine Verstöße")
    return 0


# ----------------------------------------------------------------------------------------------
# bericht, namensformen, implied-liste
# ----------------------------------------------------------------------------------------------

def cmd_bericht(args):
    tage = bereich_tage(args.bereich)
    name = bereich_name(tage, args.bereich)
    ordner = R.temp / name
    prot = []
    pf = ordner / "protokoll.jsonl"
    if pf.exists():
        prot = [json.loads(z) for z in lies(pf).splitlines() if z.strip()]
    korpus = lade_korpus()
    vw, personen, register, nach_index = lade_personenmodell()
    haushalte = lade_haushalte()
    impl = ImpliedListe()
    verworfen = lade_verworfen()
    offen = collections.defaultdict(list)
    for tag in tage:
        td = TagDaten(tag, korpus)
        sam, auto = Sammler(tag, verworfen), []
        r2 = kandidaten_aufgabe2(td, korpus, personen, sam, auto, vw)
        f1 = flags_aufgabe1(td, korpus, personen, impl.ids(), register)
        r3 = kandidaten_aufgabe3(td, korpus, personen, nach_index, haushalte, sam, vw, register)
        for e in r2["fehlt"]:
            offen["B: Index-Person mit Kandidaten, nicht entschieden"].append(f"{tag} {e['pid']} {e['info']}")
        for pid in r2["ohne_kandidat"]:
            offen["C: Index-Person ohne Anker im Text"].append(f"{tag} {pid} {lebensinfo(personen.get(pid))}")
        for f in f1:
            offen["Auffälligkeit bestehender Auszeichnung (Aufgabe 1)"].append(f"{tag} " + " ".join(f"{k}={v}" for k, v in f.items()))
        for kid in r3["ausloeser"]:
            c = next(c for c in sam.liste if c["id"] == kid)
            offen["implied-Auslöser, nicht entschieden"].append(f"{kid} {c['art']} »{_kurz(c['text'], 30)}« Kopf {c.get('kopf_name')}")
        for r in r3["implied_ohne_rs"]:
            offen["Index-implied ohne Textanker"].append(f"{tag} {r} {lebensinfo(personen.get(r))}")
        if auto:
            offen["Stufe A noch nicht angewendet"].append(f"{tag}: {len(auto)} Operationen")
    z = [f"# Bericht {name}", ""]
    z.append("## Angewendet")
    zaehl = collections.Counter(p["art"] for p in prot)
    z.append(", ".join(f"{k}: {v}" for k, v in zaehl.items()) or "nichts")
    z.append("")
    mit_grund = [p for p in prot if p.get("grund") and p["art"] != "index"]
    auto_n = sum(1 for p in mit_grund if "(Stufe A" in p["grund"] or "Stufe A)" in p["grund"] or "; Stufe A" in p["grund"])
    manuell = [p for p in mit_grund if not ("(Stufe A" in p["grund"] or "Stufe A)" in p["grund"] or "; Stufe A" in p["grund"])]
    if auto_n:
        z.append(f"Automatisch (Stufe A, Grund im Protokoll): {auto_n}")
        z.append("")
    if manuell:
        z.append("### Entscheidungen mit Begründung (Stufe B und implizite Personen, zur Prüfung)")
        for p in manuell:
            z.append(f"- {p['tag']} {p['art']} {'/'.join(p.get('refs') or [])} »{_kurz(p.get('text') or '', 40)}« – {p['grund']}")
        z.append("")
    neu_impl = [ (pid, t) for pid, (pmb, t) in impl.eintraege.items() ]
    if neu_impl:
        z.append("## Liste implied-persons.txt (aktueller Stand)")
        z += [f"- {pid}|?? [{t}]" for pid, t in neu_impl]
        z.append("")
    for k, v in offen.items():
        z.append(f"## {k} ({len(v)})")
        z += [f"- {x}" for x in v[:200]]
        if len(v) > 200:
            z.append(f"- … {len(v) - 200} weitere")
        z.append("")
    ordner.mkdir(parents=True, exist_ok=True)
    schreibe(ordner / "bericht.md", "\n".join(z) + "\n")
    print(f"Bericht: {ordner / 'bericht.md'}")
    for k, v in offen.items():
        print(f"  {k}: {len(v)}")
    return 0


def cmd_namensformen(args):
    korpus = lade_korpus(args.neu)
    personen = lade_personen()
    if args.person:
        pid = args.person.lstrip("#")
        p = personen.get(pid)
        print(lebensinfo(p) if p else f"{pid}: nicht in listperson.xml")
        if p:
            print("  PMB-Namensformen:", ", ".join(sorted(p.formen)))
        print("  gelernte Wörter (Anzahl):", ", ".join(f"{w}:{n}" for w, n in sorted(korpus.lern.get(pid, {}).items(), key=lambda x: -x[1])[:25]))
        print(f"  Tage im Index: {len(korpus.idx_tage.get(pid, ()))}")
        zu = [(k, n, korpus.allus_tage[k]) for k, d in korpus.allus_paar.items() for p2, n in d.items() if p2 == pid and n >= 3]
        for k, n, d in sorted(zu, key=lambda x: -x[1])[:15]:
            print(f"  allusively »{k}«: {n} von {d} Tagen mit diesem Wort")
    if args.wort:
        k = allus_schluessel(args.wort)
        d = korpus.allus_tage.get(k, 0)
        print(f"allusively »{k}«: {d} Tage")
        for pid, n in sorted(korpus.allus_paar.get(k, {}).items(), key=lambda x: -x[1])[:12]:
            print(f"  {pid} {lebensinfo(personen.get(pid))}: {n} Tage ({n / d:.0%})")
    if not args.person and not args.wort:
        print(f"Korpus: {len(korpus.idx)} Index-Tage, {len(korpus.lern)} Personen mit gelernten Namensformen, "
              f"{len(korpus.allus_tage)} allusively-Wörter, {sum(korpus.allus_tage.values())} Tag/Wort-Paare")
    return 0


def cmd_register_luecken(args):
    """PMB-Personen, die in den Einträgen oder im Index vorkommen, aber nicht in indices/listperson.xml stehen:
    die Redaktion nimmt sie in der PMB in die Sammlung des Tagebuchs auf, damit sie in der Edition erscheinen."""
    register = set(re.findall(r'xml:id="(pmb\d+)"', lies(R.listperson)))
    vw = Verwandtschaft()
    pv = dict(vw.personen)
    text, impl = collections.Counter(), collections.Counter()
    rs_re = re.compile(r"<rs\b[^>]*>")
    ref_re = re.compile(r'\bref="([^"]*)"')
    for f in R.editions.glob("entry__*.xml"):
        for m in rs_re.finditer(lies(f)):
            tag_s = m.group(0)
            if 'type="person"' not in tag_s and 'type="allusively"' not in tag_s:
                continue                       # Orte, Werke, Institutionen teilen sich den PMB-ID-Raum
            rm = ref_re.search(tag_s)
            if not rm:
                continue
            sub_impl = 'subtype="implied"' in tag_s
            for r in rm.group(1).split():
                r = r.lstrip("#")
                if r.startswith("pmb") and r not in register:
                    (impl if sub_impl else text)[r] += 1
    idx = collections.Counter()
    for tag, refs in lies_index().items():
        for r, _ in refs:
            if r.startswith("pmb") and r not in register:
                idx[r] += 1
    alle = sorted(set(text) | set(impl) | set(idx), key=lambda r: -(text[r] + impl[r] + idx[r]))
    print(f"{len(alle)} PMB-Personen in Einträgen/Index, die nicht in indices/listperson.xml stehen")
    for r in alle:
        p = pv.get(r)
        bez = ""
        if vw.vorhanden:
            for rel, anderer, _ in vw.alle(r, {**pv, **lade_personen()}):
                if rel.andere in register and rel.rolle in ("Ehe", "Kind", "Elternteil", "Geschwister"):
                    q = anderer.anzeige if anderer else rel.andere
                    bez = f"{rel.rolle} von {q}" if rel.rolle != "Ehe" else f"Ehepartner von {q}"
                    break
        print(f"{r}|{p.anzeige if p else '?'}|{bez or '-'}|Text {text[r]}×, implied {impl[r]}×, Index {idx[r]} Tage")
    return 0


def _fortschritt_lesen():
    pf = R.lauf / "fortschritt.txt"
    out = {}
    if pf.exists():
        for z in lies(pf).splitlines():
            if z.strip() and not z.startswith("#"):
                teile = z.split("\t")
                out[teile[0]] = teile[1:] if len(teile) > 1 else []
    return out


def cmd_sichern(args):
    """Hält einen fertigen Durchgang fest: kopiert Entscheidungen, Bericht und Protokoll nach lauf/<Bereich>/ und
    trägt den Bereich in lauf/fortschritt.txt ein (Grundlage für `fortschritt` und das Wiederaufnehmen eines Laufs)."""
    tage = bereich_tage(args.bereich)
    if not tage:
        raise PaError(f"Keine Einträge für »{args.bereich}«")
    name = bereich_name(tage, args.bereich)
    kopiert = []
    if not args.keine_arbeit:
        quelle, ziel = R.temp / name, R.lauf / name
        ziel.mkdir(parents=True, exist_ok=True)
        for muster in ("entscheidungen-*.json", "bericht.md", "protokoll.jsonl"):
            for f in sorted(quelle.glob(muster)):
                shutil.copy2(f, ziel / f.name)
                kopiert.append(f.name)
    fort = _fortschritt_lesen()
    fort[name] = [dt.datetime.now().isoformat(timespec="seconds"), args.notiz or ("keine Arbeit" if args.keine_arbeit else "")]
    R.lauf.mkdir(parents=True, exist_ok=True)
    schreibe(R.lauf / "fortschritt.txt", "# Bereich\tZeit\tNotiz\n" + "".join(f"{k}\t" + "\t".join(v) + "\n" for k, v in sorted(fort.items())))
    print(f"{name}: festgehalten ({', '.join(kopiert) if kopiert else 'ohne Dateien'}); lauf/fortschritt.txt aktualisiert")
    return 0


def cmd_fortschritt(args):
    """Welche Monate sind erledigt, welche kommen als Nächstes? Mit --tage reicht die Auswahl bis zu dieser Zahl von
    Einträgen (mindestens ein Monat, höchstens --anzahl Monate): dünn besetzte Monate werden so zusammen bearbeitet."""
    fort = _fortschritt_lesen()
    alle = alle_tage()
    monate = sorted({t[:7] for t in alle})
    erledigt = [m for m in monate if any(m.startswith(k) for k in fort)]
    offen = [m for m in monate if m not in erledigt and (not args.ab or m >= args.ab)]
    print(f"{len(erledigt)} von {len(monate)} Monaten erledigt; {len([m for m in monate if m not in erledigt])} offen")
    if not offen:
        return 0
    tage = getattr(args, "tage", None)
    if not tage:
        print("nächste: " + ", ".join(offen[:args.anzahl]))
        return 0
    je_monat = {}
    for t in alle:
        je_monat[t[:7]] = je_monat.get(t[:7], 0) + 1
    wahl, summe = [], 0
    for m in offen:
        if len(wahl) >= args.anzahl or (wahl and summe >= tage):
            break
        wahl.append(m)
        summe += je_monat[m]
    print("nächste: " + ", ".join(wahl))
    print(f"{len(wahl)} Monate, {summe} Einträge")
    return 0


def cmd_implied_liste(args):
    impl = ImpliedListe()
    if not impl.zeilen:
        print("(leer – indices/implied-persons.txt existiert noch nicht)")
    for z in impl.zeilen:
        print(z)
    return 0


# ----------------------------------------------------------------------------------------------
# Kommandozeile
# ----------------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan", help="Arbeitspaket erzeugen (liest nur)")
    p.add_argument("bereich", help="Tag, Monat, Jahr, von..bis oder alle")
    p.add_argument("--aufgaben", default="1,2,3")
    p.add_argument("--neu", action="store_true", help="Korpus-Cache neu aufbauen")
    p.add_argument("--gruppen", action="store_true", help="Gruppenwörter (»wir vier«, »und Familie«) auflisten")
    p.set_defaults(fn=cmd_scan)
    p = sub.add_parser("apply", help="Operationen anwenden (einziger Schreibweg)")
    p.add_argument("dateien", nargs="+")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--weiter", action="store_true", help="gültige Operationen anwenden, Fehler nur melden")
    p.add_argument("--unsauber", action="store_true", help="uncommittete Änderungen an Zieldateien erlauben")
    p.add_argument("--ruhig", action="store_true", help="keine Zeile je Operation (nach einem Trockenlauf mit Ausgabe)")
    p.set_defaults(fn=cmd_apply)
    p = sub.add_parser("verify", help="Arbeitsstand gegen git HEAD prüfen")
    p.add_argument("bereich", nargs="?")
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("bericht", help="bericht.md für einen Bereich")
    p.add_argument("bereich")
    p.set_defaults(fn=cmd_bericht)
    p = sub.add_parser("namensformen", help="Gelerntes aus dem Korpus anzeigen")
    p.add_argument("--person")
    p.add_argument("--wort")
    p.add_argument("--neu", action="store_true")
    p.set_defaults(fn=cmd_namensformen)
    p = sub.add_parser("implied-liste", help="indices/implied-persons.txt anzeigen")
    p.set_defaults(fn=cmd_implied_liste)
    p = sub.add_parser("sichern", help="fertigen Durchgang festhalten (lauf/<Bereich>/, lauf/fortschritt.txt)")
    p.add_argument("bereich")
    p.add_argument("--keine-arbeit", action="store_true", help="Monat ohne Arbeit nur im Fortschritt vermerken")
    p.add_argument("--notiz")
    p.set_defaults(fn=cmd_sichern)
    p = sub.add_parser("fortschritt", help="erledigte und nächste Monate eines Gesamtlaufs")
    p.add_argument("--ab", help="frühester Monat (YYYY-MM)")
    p.add_argument("--anzahl", type=int, default=12, help="höchstens so viele Monate nennen")
    p.add_argument("--tage", type=int, help="Auswahl bis zu dieser Zahl von Einträgen (mindestens ein Monat)")
    p.set_defaults(fn=cmd_fortschritt)
    p = sub.add_parser("register-luecken", help="PMB-Personen in Einträgen/Index, die nicht in listperson.xml stehen")
    p.set_defaults(fn=cmd_register_luecken)
    p = sub.add_parser("kuerzen", help="PMB-Dateien (relations.csv, listperson.xml) auf Verwandtschaft kürzen")
    p.add_argument("--quelle", help="Ordner mit relations.csv und listperson.xml (Standard: temp-indices/)")
    p.add_argument("--ausgabe", help="Zielordner (Standard: .claude/skills/personen-auszeichnen/data/)")
    p.set_defaults(fn=cmd_kuerzen)
    p = sub.add_parser("verwandte", help="Verwandtschaftsrelationen einer Person nachschlagen")
    p.add_argument("person", help="pmbN oder N")
    p.add_argument("--tag", help="Datum YYYY-MM-DD: Status der Relationen an diesem Tag")
    p.add_argument("--wort", help="Verwandtschaftswort (Frau, Tochter, Schwager …): Kandidaten für diese Person am Tag")
    p.set_defaults(fn=cmd_verwandte)
    args = ap.parse_args(argv)
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)      # `pa.py … | head` ohne Traceback
    except (ImportError, AttributeError, ValueError):
        pass
    try:
        return args.fn(args)
    except PaError as ex:
        print(f"Fehler: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
