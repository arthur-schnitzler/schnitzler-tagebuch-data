#!/usr/bin/env python3
"""Offene Fragen des Gesamtlaufs sammeln und als Arbeitswerkzeug (eine HTML-Datei) ausgeben.

Aufruf (im Repo-Wurzelverzeichnis, auf dem Branch mit dem Endstand):

    python3 .claude/skills/personen-auszeichnen/scripts/offene_fragen.py [--ausgabe ORDNER]

Schreibt nach ORDNER (Standard: temp/personen-auszeichnen/offene-fragen/):
    offene-fragen.html        das Werkzeug (Daten eingebettet, funktioniert ohne Netz, Entscheidungen im Browser gespeichert)
    neue-personen.csv         implied-person_N mit Beziehung, Bezugsperson (pmb) und Belegen
    register-luecken.csv      PMB-Personen, die verwendet werden, aber nicht im Tagebuch-Register stehen
    offene-fragen.json        alle Daten (auch als Eingabe für die HTML-Datei)

Quellen: indices/*.xml, editions/*.xml im Endstand und lauf/<Monat>/bericht.md (die offenen Punkte, die der Lauf
nicht entschieden hat). Das Skript liest nur; es ändert keine Daten.
"""
import argparse
import collections
import csv
import html
import io
import json
import os
import re
import sys
import contextlib
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import pa  # noqa: E402  (liest PA_REPO bzw. findet die Repo-Wurzel selbst)

R = pa.R
PMB = "https://pmb.acdh.oeaw.ac.at/entity/{n}/detail"
WEB = "https://schnitzler-tagebuch.acdh.oeaw.ac.at/entry__{tag}.html"
GH_XML = "https://github.com/arthur-schnitzler/schnitzler-tagebuch-data/blob/claude/personen-lauf/editions/entry__{tag}.xml"

REL_PMB = {"Frau": "Ehepartner von", "Mann": "Ehepartner von", "Mutter": "Elternteil von", "Vater": "Elternteil von",
           "Sohn": "Kind von", "Tochter": "Kind von", "Bruder": "Geschwister von", "Schwester": "Geschwister von"}


def kurz(p):
    if p is None:
        return None
    return {"name": p.anzeige, "jahre": f"{p.geb or ''}–{p.tod or ''}" if (p.geb or p.tod) else "",
            "sex": p.sex, "beruf": ", ".join(p.beruf)}


def refs_aus_attr(wert):
    return [r.lstrip("#") for r in (wert or "").split() if r.strip()]


def lade_tag(tag, cache={}):
    if tag not in cache:
        raw = pa.lies(R.entry(tag))
        cache[tag] = pa.Doc(raw, f"entry__{tag}.xml")
    return cache[tag]


def rs_spans(doc):
    """Textfluss-Spannen der rs-Elemente: [fs, fe, type, subtype, ref, xml:id]"""
    out = []
    for el in doc.elemente("rs"):
        out.append([el.fs, el.fe, el.attrs.get("type", ""), el.attrs.get("subtype", ""), el.attrs.get("ref", ""),
                    el.attrs.get("xml:id", "")])
    return out


def gesperrt(doc):
    """Textfluss-Spannen, die der Skill nicht umschließen darf (rs, date, fw, bibl …): [[fs, fe], …]"""
    out = []
    for sg in doc.segs:
        if sg.eligible:
            continue
        if out and out[-1][1] == sg.fs:
            out[-1][1] = sg.fe
        else:
            out.append([sg.fs, sg.fe])
    return out


def sammle(args):
    vw, personen, register, _ = pa.lade_personenmodell()
    index = pa.lies_index()
    tage = pa.alle_tage()
    daten = {"erzeugt": __import__("datetime").datetime.now().isoformat(timespec="minutes")}

    # ------------------------------------------------------------------------------------------
    # Refs je Tag im Text, implied-Vorkommen
    # ------------------------------------------------------------------------------------------
    refs_text = {}
    impl_vork = collections.defaultdict(list)       # implied-person_N -> [(tag, text, ctx, Kopf-Kandidaten)]
    for tag in tage:
        raw = pa.lies(R.entry(tag))
        rs = set()
        for m in re.finditer(r'<rs\b[^>]*\bref="([^"]+)"', raw):
            rs.update(refs_aus_attr(m.group(1)))
        refs_text[tag] = rs
        if "implied-person_" not in raw:
            continue
        doc = lade_tag(tag)
        spans = [(el, refs_aus_attr(el.attrs.get("ref", ""))) for el in doc.elemente("rs") if el.attrs.get("ref")]
        for el, refs in spans:
            for r in refs:
                if not r.startswith("implied-person_"):
                    continue
                kand = []
                for el2, refs2 in spans:                # Kopfkandidaten: eingeschlossene und vorangehende rs
                    if el2 is el:
                        continue
                    innen = el.fs <= el2.fs and el2.fe <= el.fe
                    davor = el2.fe <= el.fs and el.fs - el2.fe <= 160
                    if innen or davor:
                        kand += [x for x in refs2 if x.startswith("pmb") and x not in kand]
                a, b = max(0, el.fs - 70), min(len(doc.flat), el.fe + 70)
                impl_vork[r].append({"tag": tag, "text": doc.text_von(el), "ctx": doc.flat[a:b].replace("\n", " "),
                                     "von": el.fs - a, "bis": el.fe - a, "kopf": kand})

    # ------------------------------------------------------------------------------------------
    # 1. Neue Personen (implied-person_N)
    # ------------------------------------------------------------------------------------------
    name_index = collections.defaultdict(list)
    for pid, p in personen.items():
        name_index[pa.fold(p.anzeige)].append(pid)

    def beziehungen(pid):
        out = []
        for r in vw.rel.get(pid, ()):
            q = personen.get(r.andere)
            out.append({"pmb": r.andere, "rolle": r.rolle, "von": r.von or "", "bis": r.bis or "",
                        "name": q.anzeige if q else "?", "jahre": f"{q.geb or ''}–{q.tod or ''}" if q else "",
                        "im_register": r.andere in register})
        return out

    neue = []
    for zeile in pa.lies(R.implied).splitlines():
        m = re.match(r"^(implied-person_\d+)\|\?\? \[(.+)\]\s*$", zeile.strip())
        if not m:
            continue
        pid, beschr = m.groups()
        rel, _, kopfname = beschr.partition(" von ")
        vork = impl_vork.get(pid, [])
        cands = collections.Counter(x for v in vork for x in v["kopf"])
        for x in name_index.get(pa.fold(kopfname), []):
            cands[x] += 0
        # Kopf: Kandidat, dessen Name zum Namen in der Beschreibung passt; bei Gleichstand der häufigste
        passend = [c for c in cands if c in personen and pa.fold(personen[c].anzeige) == pa.fold(kopfname)]
        if not passend:
            kw = {pa.fold(w) for w in pa.woerter(kopfname) if not pa.ist_partikel(w)}
            passend = [c for c in cands if c in personen and kw and kw <= {pa.fold(w) for w in pa.woerter(personen[c].anzeige)}]
        # am Tag im Index genannte Kandidaten bevorzugen
        tage_v = sorted({v["tag"] for v in vork})
        def im_index(c):
            return sum(1 for t in tage_v if any(r == c for r, _ in index.get(t, [])))
        passend.sort(key=lambda c: (-im_index(c), -cands[c]))
        kopf = passend[0] if passend else None
        daten_k = kurz(personen.get(kopf)) if kopf else None
        neue.append({
            "id": pid, "beschreibung": beschr, "beziehung": rel, "kopf_name": kopfname, "kopf": kopf,
            "kopf_info": daten_k, "kopf_im_register": bool(kopf and kopf in register),
            "pmb_beziehung": (REL_PMB.get(rel.split()[0], rel) + " " + kopfname + (f" ({kopf})" if kopf else "")),
            "anzahl": len(vork), "tage": tage_v, "erster": tage_v[0] if tage_v else "", "letzter": tage_v[-1] if tage_v else "",
            "belege": [{k: v[k] for k in ("tag", "text", "ctx", "von", "bis")} for v in vork[:6]],
            "kopf_beziehungen": beziehungen(kopf) if kopf else [],
        })
    daten["neue_personen"] = neue

    # ------------------------------------------------------------------------------------------
    # 2. PMB-Personen außerhalb des Registers
    # ------------------------------------------------------------------------------------------
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        pa.cmd_register_luecken(argparse.Namespace())
    luecken = []
    for z in puffer.getvalue().splitlines():
        t = z.split("|")
        if len(t) == 4 and t[0].startswith("pmb"):
            tg = sorted(tag for tag, rs in index.items() if any(r == t[0] for r, _ in rs))
            luecken.append({"pmb": t[0], "name": t[1], "beziehung": t[2], "zaehlung": t[3], "tage": tg})
    daten["register_luecken"] = luecken

    # ------------------------------------------------------------------------------------------
    # 3. Index-Personen ohne Textanker (C), Index-implied ohne Anker
    # ------------------------------------------------------------------------------------------
    c_items, tage_text = [], set()
    for tag in tage:
        im_text = refs_text.get(tag, set())
        fehlend = [(r, impl) for r, impl in index.get(tag, []) if r.startswith("pmb") and r not in im_text]
        if not fehlend:
            continue
        doc = lade_tag(tag)
        vorhanden = [r for r in im_text if r.startswith("pmb")]
        for r, impl in fehlend:
            p = personen.get(r)
            verw = []
            for x in vorhanden:
                for rel in vw.rel.get(r, ()):
                    if rel.andere == x:
                        q = personen.get(x)
                        verw.append({"pmb": x, "name": q.anzeige if q else "?", "rolle": rel.rolle})
            hint = []
            if p is not None:
                formen = {w for w in [p.vor, p.nach] + list(p.varianten) for w in pa.woerter(w)}
                for w in sorted(formen, key=len, reverse=True):
                    w = w.strip(".")
                    if len(w) < 3 or pa.ist_partikel(w):
                        continue
                    for m in re.finditer(r"(?<!\w)" + re.escape(w) + r"\w{0,2}(?!\w)", doc.flat):
                        hint.append([m.start(), m.end()])
            hint = sorted({tuple(h) for h in hint})[:12]
            kand_rs = [{"id": r[5], "text": doc.flat[r[0]:r[1]]} for r in rs_spans(doc)
                       if not r[4] and r[2] in ("person", "allusively") and r[5] and any(r[0] < h[1] and h[0] < r[1] for h in hint)][:6]
            gs = gesperrt(doc)
            hint = [h for h in hint if not any(h[0] < g[1] and g[0] < h[1] for g in gs)]
            c_items.append({"tag": tag, "pmb": r, "implied_index": impl, "info": kurz(p) or {"name": "?", "jahre": "", "sex": None, "beruf": ""},
                            "im_register": r in register, "verwandt": verw[:4], "hint": [list(h) for h in hint], "kand_rs": kand_rs})
            tage_text.add(tag)
    daten["index_ohne_anker"] = c_items

    # ------------------------------------------------------------------------------------------
    # 4. Aus den Monatsberichten: Prüfbefunde, nicht entschiedene Auslöser, B-Fälle
    # ------------------------------------------------------------------------------------------
    pruef, ausloeser, b_items, a_rest = [], [], [], []
    lauf = R.lauf if any(R.lauf.glob("*/bericht.md")) else R.root / ".claude" / "skills" / "personen-auszeichnen" / "lauf"
    for f in sorted(lauf.glob("*/bericht.md")):
        sec = None
        for z in pa.lies(f).splitlines():
            if z.startswith("## "):
                sec = z[3:]
                continue
            if not z.startswith("- "):
                continue
            if sec and sec.startswith("Auffälligkeit bestehender"):
                m = re.match(r"- (\d{4}-\d\d-\d\d) art=(\S+)(?: rs=(\S+))?(?: text=(.*?))?(?: ref=(\S+))?( \S+=.*)?$", z)
                if not m:
                    continue
                tag, art, rs, text, ref, rest = m.groups()
                if art == "nicht_im_register":
                    continue                      # steht unter Register-Lücken
                zus = dict(re.findall(r"(\w+)=(\S+)", rest or ""))
                pruef.append({"tag": tag, "art": art, "rs": rs or "", "text": text or "", "ref": ref or "", "zus": zus})
            elif sec and sec.startswith("implied-Auslöser"):
                m = re.match(r"- (\d{4}-\d\d-\d\d)#(\d+) (\S+) »(.+?)« (.*)$", z)
                if m:
                    tag, n, art, text, rest = m.groups()
                    ausloeser.append({"tag": tag, "k": f"{tag}#{n}", "art": art, "text": text, "rest": rest})
            elif sec and sec.startswith("B: Index-Person"):
                m = re.match(r"- (\d{4}-\d\d-\d\d) (pmb\d+) (.*)$", z)
                if m:
                    b_items.append({"tag": m.group(1), "pmb": m.group(2), "text": m.group(3)})
            elif sec and sec.startswith("Stufe A noch nicht"):
                m = re.match(r"- (\d{4}-\d\d-\d\d): (\d+) Operationen", z)
                if m:
                    a_rest.append({"tag": m.group(1), "n": int(m.group(2))})
    # Stufe-A-Vorschläge, die der Lauf nicht angewendet hat: frisch scannen und auto.json lesen
    stufe_a = []
    for monat in sorted({x["tag"][:7] for x in a_rest}):
        with contextlib.redirect_stdout(io.StringIO()):
            pa.cmd_scan(argparse.Namespace(bereich=monat, aufgaben="1,2", neu=False, gruppen=False))
        af = R.temp / monat / "auto.json"
        if not af.exists():
            continue
        a = json.loads(pa.lies(af))
        for o in (a["ops"] if isinstance(a, dict) else a):
            if o.get("op") == "set_ref" and o.get("id"):
                doc = lade_tag(o["tag"])
                try:
                    txt = doc.text_von(doc.finde_id(o["id"]))
                except Exception:
                    txt = ""
                stufe_a.append({"tag": o["tag"], "id": o["id"], "ref": o["ref"], "text": txt, "grund": o.get("grund", "")})
                tage_text.add(o["tag"])
    for x in ausloeser:
        doc = lade_tag(x["tag"]) if R.entry(x["tag"]).exists() else None
        if doc is None:
            continue
        m = re.search(r"\s+".join(re.escape(w) for w in x["text"].split()), doc.flat)
        x["pos"] = [m.start(), m.end()] if m else None
    daten["pruefbefunde"] = pruef
    daten["ausloeser"] = ausloeser
    daten["b_fall"] = b_items
    daten["stufe_a"] = stufe_a

    # ------------------------------------------------------------------------------------------
    # 5. Texte der betroffenen Tage
    # ------------------------------------------------------------------------------------------
    tage_noetig = set(tage_text) | {x["tag"] for x in pruef} | {x["tag"] for x in ausloeser} | {x["tag"] for x in b_items} \
        | {x["tag"] for x in stufe_a} | {t for n in neue for t in n["tage"]}
    texte = {}
    for tag in sorted(tage_noetig):
        if not R.entry(tag).exists():
            continue
        doc = lade_tag(tag)
        kopf = re.search(r"<head[^>]*>(.*?)</head>", doc.raw, re.S)
        texte[tag] = {"t": doc.flat, "rs": rs_spans(doc), "idx": [r for r, _ in index.get(tag, [])], "gs": gesperrt(doc)}
    daten["texte"] = texte
    # Personenkurzinfo für alle vorkommenden Refs (Anzeige, Suche im Werkzeug)
    gebraucht = {x["pmb"] for x in c_items} | {x["pmb"] for x in luecken} | {x["pmb"] for x in b_items}
    gebraucht |= {x["ref"] for x in pruef if x["ref"].startswith("pmb")} | {x["zus"].get("ueblich") for x in pruef if x["zus"].get("ueblich")}
    for n in neue:
        if n["kopf"]:
            gebraucht.add(n["kopf"])
    daten["personen"] = {p: kurz(personen.get(p)) for p in sorted(g for g in gebraucht if g)}
    # Suchliste: Register-Personen (für die Auswahl einer Person im Werkzeug)
    daten["register_suche"] = [[pid, p.anzeige, f"{p.geb or ''}–{p.tod or ''}" if (p.geb or p.tod) else ""]
                               for pid, p in sorted(personen.items(), key=lambda kv: kv[1].anzeige) if pid in register]
    return daten


def schreibe_csv(daten, ordner):
    with open(ordner / "neue-personen.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["implied-person", "Beschreibung", "Beziehung", "Bezugsperson", "pmb Bezugsperson", "Bezugsperson Lebensdaten",
                    "Vorschlag Relation in der PMB", "Zahl Belege", "erster Tag", "letzter Tag", "Tage (bis 6)", "Beispielstelle",
                    "neue pmb-Nummer (auszufüllen)"])
        for n in daten["neue_personen"]:
            b = n["belege"][0] if n["belege"] else {}
            w.writerow([n["id"], n["beschreibung"], n["beziehung"], n["kopf_name"], n["kopf"] or "",
                        (n["kopf_info"] or {}).get("jahre", ""), n["pmb_beziehung"], n["anzahl"], n["erster"], n["letzter"],
                        " ".join(n["tage"][:6]), (b.get("ctx", "") if b else ""), ""])
    with open(ordner / "register-luecken.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["pmb", "Name", "Beziehung zu einer Registerperson", "Häufigkeit", "Zahl Tage", "erster Tag", "letzter Tag"])
        for l in daten["register_luecken"]:
            w.writerow([l["pmb"], l["name"], l["beziehung"], l["zaehlung"], len(l["tage"]),
                        l["tage"][0] if l["tage"] else "", l["tage"][-1] if l["tage"] else ""])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ausgabe", help="Zielordner (Standard: temp/personen-auszeichnen/offene-fragen/)")
    ap.add_argument("--vorlage", default=str(HIER / "offene_fragen.html"), help="HTML-Vorlage")
    args = ap.parse_args()
    ordner = Path(args.ausgabe) if args.ausgabe else R.temp / "offene-fragen"
    ordner.mkdir(parents=True, exist_ok=True)
    daten = sammle(args)
    (ordner / "offene-fragen.json").write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    schreibe_csv(daten, ordner)
    vorlage = Path(args.vorlage)
    if vorlage.exists():
        t = vorlage.read_text(encoding="utf-8")
        eingebettet = json.dumps(daten, ensure_ascii=False).replace("</", "<\\/")
        t = t.replace("/*__DATEN__*/null", eingebettet)
        # Datei zum lokalen Öffnen: vollständiges Dokument; Fassung für claude.ai (Artifact): nur der Inhalt ohne Gerüst
        kopf, _, rumpf = t.partition("<!--BODY-->")
        (ordner / "offene-fragen.html").write_text(
            '<!doctype html>\n<html lang="de">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            + kopf + "</head>\n<body>\n" + rumpf + "</body>\n</html>\n", encoding="utf-8")
        (ordner / "offene-fragen-artifact.html").write_text(
            t.replace("<!--BODY-->", "").replace("/*__ARTIFACT__*/false", "true"), encoding="utf-8")
    n = daten
    print(f"neue Personen: {len(n['neue_personen'])}; Register-Lücken: {len(n['register_luecken'])}; "
          f"Index ohne Anker: {len(n['index_ohne_anker'])}; Prüfbefunde: {len(n['pruefbefunde'])}; "
          f"Auslöser: {len(n['ausloeser'])}; B: {len(n['b_fall'])}; Stufe A offen: {len(n['stufe_a'])}; "
          f"Texte: {len(n['texte'])} Tage")
    print("geschrieben nach", ordner)
    return 0


if __name__ == "__main__":
    sys.exit(main())
