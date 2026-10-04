#!/usr/bin/env python3
"""Regressionstest für pa.py und schreibschutz.py – mit erfundenem XML, ohne echte Einträge zu verändern.

Aufruf (aus dem Repo-Wurzelverzeichnis):
    python3 .claude/skills/personen-auszeichnen/scripts/test_skill.py

Nach jeder Änderung an einem der beiden Skripte laufen lassen. Die Tests legen ein Wegwerf-Repo in einem
temporären Ordner an (mit git) und lesen nur zur Stichprobe aus den echten Einträgen (Tokenizer-Probe).
"""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True          # kein __pycache__ im Repo (auch nicht in Cloud-Läufen)
HIER = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pa", HIER / "pa.py")
pa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pa)
ECHT = pa.R          # das echte Repo (nur lesend)

fehler = 0


def pruefe(name, bedingung):
    global fehler
    print(("  ok      " if bedingung else "  FEHLER  ") + name)
    fehler += not bedingung


def wirft(fn, code=None, enthaelt=None):
    try:
        fn()
    except pa.PaError as ex:
        return (code is None or ex.code == code) and (enthaelt is None or enthaelt in str(ex))
    return False


# ----------------------------------------------------------------------------------------------
# Wegwerf-Repo
# ----------------------------------------------------------------------------------------------

TEI_KOPF = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xml:id="entry__{tag}.xml">
   <teiHeader>
      <fileDesc>
         <titleStmt>
            <title type="main">Test {tag}</title>
         </titleStmt>
      </fileDesc>
   </teiHeader>
   <text>
      <body>
         <div type="diary-day" xml:id="entry__{tag}">
{body}
         </div>
      </body>
   </text>
</TEI>
"""

TAG1 = ('            <p xml:space="preserve"><date when="1900-01-01">1/1</date> Mit <rs type="person" xml:id="pNt_00001" '
        'ref="#pmb11740"><surname>Hofmannsthal</surname></rs> und Frau bei <rs type="person" xml:id="pNt_00002">'
        '<forename>Richard</forename></rs>. <rs type="allusively" xml:id="rst_00001">Mama</rs> kam. Abends mit Salten &amp; Dilly\n'
        'und Frau Reich, auch Mama.</p>')
TAG2 = ('            <p xml:space="preserve"><date when="1900-01-02">2/1</date> Bei Hofmannsthal und Anna Reich; '
        '<rs type="work" xml:id="bibl_00001">Elektra</rs> gelesen. Salten kam<pb n="2"/> auch.</p>')
TAG3 = ('            <p xml:space="preserve"><date when="1900-01-05">5/1</date> <rs type="person" xml:id="pNt_00003" '
        'ref="#pmb11740"><surname>Hofmannsthals</surname></rs> sind da.</p>')

PERSONEN = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt><title>x</title></titleStmt></fileDesc></teiHeader><text><body><div><listPerson>
<person xml:id="pmb11740"><persName><forename>Hugo von</forename><surname>Hofmannsthal</surname></persName><sex value="male"/><birth><date when-iso="1874-02-01">1874-02-01</date></birth><death><date when-iso="1929-07-15">1929-07-15</date></death></person>
<person xml:id="pmb2292"><persName><forename>Gertrude von</forename><surname>Hofmannsthal</surname></persName><persName type="person_rufname_vorname">Gerty</persName><sex value="female"/><birth><date when-iso="1880-03-16">1880-03-16</date></birth></person>
<person xml:id="pmb10863"><persName><forename>Richard</forename><surname>Beer-Hofmann</surname></persName><sex value="male"/><birth><date when-iso="1866-07-11">1866-07-11</date></birth></person>
<person xml:id="pmb12701"><persName><forename>Louise</forename><surname>Schnitzler</surname></persName><sex value="female"/></person>
<person xml:id="pmb2167"><persName><forename>Felix</forename><surname>Salten</surname></persName><sex value="male"/></person>
<person xml:id="pmb2589"><persName><forename>Johanna Simonetta</forename><surname>Sandrock</surname></persName><persName type="person_rufname_vorname">Dilly</persName><sex value="female"/></person>
<person xml:id="pmb23001"><persName><forename>Anna</forename><surname>Reich</surname></persName><sex value="female"/></person>
</listPerson></div></body></text></TEI>
"""

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<list>
   <item target="1900-01-01">
      <ref>pmb11740</ref>
      <ref>pmb10863</ref>
      <ref>pmb12701</ref>
      <ref>pmb2167</ref>
      <ref>pmb2589</ref>
      <ref>pmb23001</ref>
   </item>
   <item target="1900-01-02">
      <ref>pmb11740</ref>
      <ref>pmb23001</ref>
      <ref>pmb2167</ref>
   </item>
   <item target="1900-01-05">
      <ref>pmb11740</ref>
   </item>
</list>
"""


def git(root, *a):
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                          capture_output=True, text=True)


def baue_repo(mit_git=True):
    root = Path(tempfile.mkdtemp(prefix="pa-test-"))
    (root / "editions").mkdir()
    (root / "indices").mkdir()
    for tag, body in (("1900-01-01", TAG1), ("1900-01-02", TAG2), ("1900-01-05", TAG3)):
        (root / "editions" / f"entry__{tag}.xml").write_text(TEI_KOPF.format(tag=tag, body=body), encoding="utf-8")
    (root / "indices" / "listperson.xml").write_text(PERSONEN, encoding="utf-8")
    (root / "indices" / "index_person_day.xml").write_text(INDEX, encoding="utf-8")
    (root / ".gitignore").write_text("/temp\n", encoding="utf-8")
    if mit_git:
        git(root, "init", "-q")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "baseline")
    pa.R = pa.Repo(root)
    pa.R.verw_dir = root / "data"          # hermetisch: keine echten Verwandtschaftsdaten
    pa.R.verw_relationen = pa.R.verw_dir / "verwandtschaft-relationen.csv"
    pa.R.verw_personen = pa.R.verw_dir / "verwandtschaft-personen.xml"
    pa.R.verw_quelle = pa.R.verw_dir / "verwandtschaft-quelle.json"
    pa.R.pmb_quelle = root / "temp-indices"
    pa.R.lauf = root / "lauf"                # hermetisch: nicht in den echten Skill-Ordner schreiben
    return root


def lese(root, tag):
    return (root / "editions" / f"entry__{tag}.xml").read_text(encoding="utf-8")


def apply_ops(ops, dry=False, weiter=False, dateiname="ops.json"):
    d = pa.R.temp
    d.mkdir(parents=True, exist_ok=True)
    f = d / dateiname
    f.write_text(json.dumps({"ops": ops}, ensure_ascii=False), encoding="utf-8")
    ns = argparse.Namespace(dateien=[str(f)], dry_run=dry, unsauber=False, weiter=weiter)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = pa.cmd_apply(ns)
    return rc, out.getvalue(), err.getvalue()


# ----------------------------------------------------------------------------------------------
print("Tokenizer und Dokumentmodell")
raw = TEI_KOPF.format(tag="1900-01-01", body=TAG1)
d = pa.Doc(raw, "t")
pruefe("Tokens decken die Datei lückenlos ab", "".join(raw[s:e] for _, s, e, _ in d.toks) == raw)
from lxml import etree  # noqa: E402
body = etree.fromstring(raw.encode("utf-8")).find(".//{http://www.tei-c.org/ns/1.0}body")
pruefe("Textfluss = lxml-Text des body (inkl. &amp;)", d.flat == "".join(body.itertext()))
pruefe("Entität &amp; im Textfluss decodiert", "Salten & Dilly" in d.flat)
an = d.finde_anker("Salten", "mit ")
pruefe("Anker vor einer Entität: Rohposition stimmt", raw[an.raw_a:an.raw_b] == "Salten")
an = d.finde_anker("Dilly", "& ")
pruefe("Anker hinter einer Entität: Rohposition stimmt", raw[an.raw_a:an.raw_b] == "Dilly")
pruefe("mehrdeutiger Anker wird abgelehnt", wirft(lambda: d.finde_anker("und"), "anker", "mehrdeutig"))
pruefe("nr wählt unter mehreren freien Treffern", d.finde_anker("und", nr=2).a > d.finde_anker("und", nr=1).a)
pruefe("Mama im rs ist gesperrt, das freie Mama eindeutig", d.finde_anker("Mama") is not None)
pruefe("Anker in ausgezeichnetem Text wird abgelehnt", wirft(lambda: d.finde_anker("Richard"), "anker", "ausgezeichnet"))
pruefe("Anker über Elementgrenze wird abgelehnt", wirft(lambda: d.finde_anker("und Frau bei Richard"), "anker"))
pruefe("Wortgrenze: »Mam« trifft nicht in »Mama«", wirft(lambda: d.finde_anker("Mam"), "anker"))
a1 = d.anker_fuer(d.flat.index("Salten"), d.flat.index("Salten") + 6)
pruefe("anker_fuer liefert eindeutigen Anker", a1 is not None and d.finde_anker(a1["text"], a1.get("vorher", ""), a1.get("nachher", "")).a == d.flat.index("Salten"))
real = ECHT.editions.glob("entry__*.xml")
probe = sorted(real)[:150:3] + [p for p in sorted(ECHT.editions.glob("entry__190[78]-*.xml"))[:40]]
if probe:
    ok = True
    for f in probe:
        r = pa.lies(f)
        dd = pa.Doc(r, f.name)
        b = etree.fromstring(r.encode("utf-8")).find(".//{http://www.tei-c.org/ns/1.0}body")
        ok &= dd.flat == "".join(b.itertext())
    pruefe(f"Tokenizer-Probe an {len(probe)} echten Einträgen (Textfluss = lxml)", ok)

# ----------------------------------------------------------------------------------------------
print("Index im Rohtext")
r, ein = pa.index_ergaenzen(INDEX, {"1900-01-01": [("pmb2292", True)]})
pruefe("Ref ans Ende des vorhandenen Items", '      <ref ana="implied">pmb2292</ref>\n   </item>\n   <item target="1900-01-02">' in r)
pruefe("bereits vorhandener Ref wird nicht doppelt eingefügt", pa.index_ergaenzen(INDEX, {"1900-01-01": [("pmb2167", False)]})[0] == INDEX)
r, _ = pa.index_ergaenzen(INDEX, {"1900-01-03": [("pmb1", False)]})
pruefe("neuer Tag zwischen zwei Items in Datumsreihenfolge", list(pa.lies_index(r)) == ["1900-01-01", "1900-01-02", "1900-01-03", "1900-01-05"])
r, _ = pa.index_ergaenzen(INDEX, {"1899-12-31": [("pmb1", True)], "1900-02-01": [("pmb2", False)]})
pruefe("neuer Tag am Anfang und am Ende", list(pa.lies_index(r)) == ["1899-12-31", "1900-01-01", "1900-01-02", "1900-01-05", "1900-02-01"])
pruefe("neues Item wohlgeformt", etree.fromstring(r.encode("utf-8")) is not None and '<ref ana="implied">pmb1</ref>' in r)
leer = INDEX.replace('<item target="1900-01-05">\n      <ref>pmb11740</ref>\n   </item>', '<item target="1900-01-05"/>')
r, _ = pa.index_ergaenzen(leer, {"1900-01-05": [("pmb7", False)]})
pruefe("leeres Item <item …/> wird aufgeklappt", pa.lies_index(r)["1900-01-05"] == [("pmb7", False)])

# ----------------------------------------------------------------------------------------------
print("Auszeichnen (apply)")
root = baue_repo()
vorher = {t: lese(root, t) for t in ("1900-01-01", "1900-01-02", "1900-01-05")}
OPS1 = [
    {"op": "set_ref", "tag": "1900-01-01", "id": "pNt_00002", "ref": "pmb10863", "grund": "Richard"},
    {"op": "set_ref", "tag": "1900-01-01", "id": "rst_00001", "ref": "pmb12701"},
    {"op": "wrap", "tag": "1900-01-01", "anker": {"text": "Salten", "vorher": "mit "}, "ref": "pmb2167"},
    {"op": "wrap", "tag": "1900-01-01", "anker": {"text": "Dilly", "vorher": "& "}, "ref": "pmb2589"},
    {"op": "wrap", "tag": "1900-01-01", "anker": {"text": "Frau Reich"}, "ref": "pmb23001"},
    {"op": "wrap", "tag": "1900-01-01", "anker": {"text": "Mama", "vorher": "auch "}, "ref": "pmb12701", "typ": "allusively"},
    {"op": "implied", "tag": "1900-01-01", "anker": {"text": "Frau", "vorher": "Hofmannsthal und "}, "ref": "pmb2292"},
    {"op": "implied", "tag": "1900-01-01", "um_rs": "pNt_00002", "neu": "Frau von Richard Beer-Hofmann"},
    {"op": "implied", "tag": "1900-01-05", "um_rs": "pNt_00003", "ref": "pmb2292"},
]
rc, out, err = apply_ops(OPS1, dry=True)
pruefe("Trockenlauf meldet Erfolg", rc == 0 and "Trockenlauf" in out)
pruefe("Trockenlauf schreibt nichts", all(lese(root, t) == v for t, v in vorher.items()) and not (root / "indices" / "implied-persons.txt").exists())
rc, out, err = apply_ops(OPS1)
pruefe("apply läuft durch (rc 0)", rc == 0)
x1 = lese(root, "1900-01-01")
pruefe("set_ref an person-rs: Attributfolge type, xml:id, ref", '<rs type="person" xml:id="pNt_00002" ref="#pmb10863">' in x1 or 'xml:id="pNt_00002" ref="#pmb10863"' in x1)
pruefe("set_ref an allusively-rs: type bleibt", '<rs type="allusively" xml:id="rst_00001" ref="#pmb12701">Mama</rs>' in x1)
pruefe("wrap: forename/surname nach PMB (Salten → surname)", "<surname>Salten</surname>" in x1)
pruefe("wrap: Rufname Dilly → forename", "<forename>Dilly</forename>" in x1)
pruefe("wrap: Anrede → roleName, Name → surname", "<roleName>Frau</roleName> <surname>Reich</surname>" in x1)
pruefe("wrap allusively: rst_-ID, kein Kindelement", '<rs type="allusively" xml:id="rst_00002" ref="#pmb12701">Mama</rs>' in x1)
pruefe("implied auf Wort: type, xml:id, ref, subtype", 'xml:id="pNt_' in x1 and 'ref="#pmb2292" subtype="implied">Frau</rs>' in x1)
pruefe("implied um bestehenden rs (Verschachtelung)", 'ref="#implied-person_1" subtype="implied"><rs type="person" xml:id="pNt_00002"' in x1)
pruefe("&amp; bleibt im Rohtext erhalten", "Salten</surname></rs> &amp; " in x1)
pruefe("Zeilenumbruch im Text unangetastet", "Dilly</forename></rs>\nund " in x1)
pruefe("implied-persons.txt angelegt", (root / "indices" / "implied-persons.txt").read_text() == "implied-person_1|?? [Frau von Richard Beer-Hofmann]\n")
idx = pa.lies_index(pa.lies(pa.R.index))
pruefe("Index: implied-Refs ergänzt", ("pmb2292", True) in idx["1900-01-01"] and ("implied-person_1", True) in idx["1900-01-01"] and ("pmb2292", True) in idx["1900-01-05"])
x5 = lese(root, "1900-01-05")
pruefe("Familienform: implied um bestehenden rs, Hofmannsthals bleibt", 'subtype="implied"><rs type="person" xml:id="pNt_00003" ref="#pmb11740"><surname>Hofmannsthals</surname></rs></rs>' in x5)
neue = sorted(set(pa.re.findall(r'xml:id="((?:pNt|rst)_\d+)"', x1 + x5)))
pruefe("neue IDs ab globalem Maximum + 1", "pNt_00004" in neue and "rst_00002" in neue)
with contextlib.redirect_stdout(io.StringIO()):
    rc = pa.cmd_verify(argparse.Namespace(bereich=None))
pruefe("verify nach apply: keine Verstöße", rc == 0)
git(root, "add", "-A")
git(root, "commit", "-q", "-m", "nach apply")
rc, out, err = apply_ops(OPS1, dateiname="ops2.json")
pruefe("zweiter Lauf ist ein No-op (Idempotenz)", rc == 0 and "übersprungen" in out and "Dateien: 0" in out)
pruefe("zweiter Lauf ändert die Dateien nicht", lese(root, "1900-01-01") == x1 and lese(root, "1900-01-05") == x5)

print("Ablehnungen")
rc, out, err = apply_ops([{"op": "set_ref", "tag": "1900-01-01", "id": "pNt_00001", "ref": "pmb10863"}], dateiname="a.json")
pruefe("bestehendes ref wird nie geändert", rc == 1 and "nie geändert" in err)
rc, out, err = apply_ops([{"op": "set_ref", "tag": "1900-01-02", "id": "bibl_00001", "ref": "pmb2167"}], dateiname="b.json")
pruefe("set_ref nur an person/allusively-rs", rc == 1 and "kein rs" in err)
rc, out, err = apply_ops([{"op": "wrap", "tag": "1900-01-02", "anker": {"text": "Salten"}, "ref": "pmb9999999"}], dateiname="c.json")
pruefe("unbekannter ref wird abgelehnt", rc == 1 and "weder in listperson" in err)
rc, out, err = apply_ops([{"op": "wrap", "tag": "1900-01-02", "anker": {"text": "Salten"}, "ref": "pmb12701"}], dateiname="d.json")
pruefe("ref außerhalb der Index-Refs des Tages wird abgelehnt (geschlossene Menge)", rc == 1 and "gehört nicht zu den Index-Refs" in err)
rc, out, err = apply_ops([{"op": "wrap", "tag": "1900-01-02", "anker": {"text": "Salten"}, "ref": "pmb12701", "frei": True}], dry=True, dateiname="e.json")
pruefe("frei: true hebt die Schließung auf", rc == 0)
rc, out, err = apply_ops([{"op": "wrap", "tag": "1900-01-02", "anker": {"text": "kam auch"}, "ref": "pmb2167"}], dry=True, dateiname="f.json")
pruefe("Anker über Elementgrenze (pb) wird abgelehnt", rc == 1 and "Elementgrenze" in err)
rc, out, err = apply_ops([{"op": "wrap", "tag": "1900-01-02", "anker": {"text": "Hofmannsthal und"}, "ref": "pmb11740"},
                          {"op": "wrap", "tag": "1900-01-02", "anker": {"text": "und Anna"}, "ref": "pmb23001"}], dry=True, dateiname="g.json")
pruefe("sich überlappende Anker werden abgelehnt", rc == 1 and "überlappen" in err)
rc, out, err = apply_ops([{"op": "wrap", "tag": "1900-01-02", "anker": {"text": "Salten", "nachher": " kam"}, "ref": "pmb2167", "teile": ["surname:Salten"]},
                          {"op": "wrap", "tag": "1900-01-02", "anker": {"text": "Anna Reich"}, "ref": "pmb23001", "teile": ["forename:Anna", "surname:Reich"]}], dateiname="h.json")
x2 = lese(root, "1900-01-02")
pruefe("teile aus der Operation werden verwendet", "<forename>Anna</forename> <surname>Reich</surname>" in x2 and "<surname>Salten</surname>" in x2)
pruefe("pb im Text bleibt unangetastet", 'Salten</surname></rs> kam<pb n="2"/> auch.' in x2)

print("Invarianten")
alt = pa.Doc(lese(root, "1900-01-02"), "t")
plan = pa.Plan(alt)
plan.neue_ids = ["pNt_99999"]
kaputt = alt.raw.replace("gelesen", "gelesn")
pruefe("Textänderung wird erkannt", wirft(lambda: pa.pruefe_invarianten(alt, kaputt, plan), "invariante"))
unwohl = alt.raw.replace("</div>", "")
pruefe("nicht wohlgeformtes Ergebnis wird erkannt", wirft(lambda: pa.pruefe_invarianten(alt, unwohl, plan)))
umgebaut = alt.raw.replace('<rs type="work" xml:id="bibl_00001">', '<rs type="work" xml:id="bibl_00009">')
pruefe("unerlaubte Attributänderung wird erkannt", wirft(lambda: pa.pruefe_invarianten(alt, umgebaut, plan), "invariante"))

print("verify erkennt Manipulationen")
p2 = root / "editions" / "entry__1900-01-02.xml"
git(root, "add", "-A")
git(root, "commit", "-q", "-m", "teile")
p2.write_text(p2.read_text(encoding="utf-8").replace("Bei Hofmannsthal", "Bei Hofmannsthall"), encoding="utf-8")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = pa.cmd_verify(argparse.Namespace(bereich=None))
pruefe("verify meldet veränderten Text", rc == 1 and "Textfluss" in buf.getvalue())
git(root, "checkout", "-q", "--", "editions")

print("scan, Kandidaten, verwerfen")
rc = 0
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = pa.cmd_scan(argparse.Namespace(bereich="1900-01-02", aufgaben="1,2,3", neu=True, gruppen=False))
reg = pa.lade_registry()
pruefe("scan legt ein Kandidaten-Register an", rc == 0 and "1900-01-02" in reg["tage"])
kands = reg["tage"].get("1900-01-02", {}).get("kandidaten", {})
pruefe("scan findet Index-Person (Hofmannsthal) als unmarkierten Kandidaten", any(c["art"] == "unmarkiert" and c["text"] == "Hofmannsthal" for c in kands.values()))
kid = next((k for k, c in kands.items() if c["art"] == "unmarkiert" and c["text"] == "Hofmannsthal"), None)
pruefe("Kandidat enthält einen eindeutigen Anker", kid is not None and kands[kid]["op"]["anker"]["text"] == "Hofmannsthal")
assert kid, "ohne Kandidat kein Weitertesten"
entsch = pa.R.temp / "entsch.json"
entsch.write_text(json.dumps([{"k": kid, "grund": "Test"}]), encoding="utf-8")
ns = argparse.Namespace(dateien=[str(entsch)], dry_run=True, unsauber=False, weiter=False)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = pa.cmd_apply(ns)
pruefe("apply löst Kandidaten-Kennung auf (Trockenlauf)", rc == 0 and "pmb11740" in buf.getvalue())
p2.write_text(p2.read_text(encoding="utf-8").replace("gelesen", "gelesen "), encoding="utf-8")
buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    rc = pa.cmd_apply(argparse.Namespace(dateien=[str(entsch)], dry_run=True, unsauber=True, weiter=False))
pruefe("veralteter Kandidat (Datei seit scan geändert) wird abgelehnt", rc == 1 and "seit dem scan geändert" in buf.getvalue())
git(root, "checkout", "-q", "--", "editions")
with contextlib.redirect_stdout(io.StringIO()):
    pa.cmd_scan(argparse.Namespace(bereich="1900-01-02", aufgaben="1,2,3", neu=False, gruppen=False))
reg = pa.lade_registry()
kid = next(k for k, c in reg["tage"]["1900-01-02"]["kandidaten"].items() if c["art"] == "unmarkiert" and c["text"] == "Hofmannsthal")
entsch.write_text(json.dumps([{"k": kid, "verwerfen": True, "grund": "Test"}]), encoding="utf-8")
with contextlib.redirect_stdout(io.StringIO()):
    pa.cmd_apply(argparse.Namespace(dateien=[str(entsch)], dry_run=False, unsauber=False, weiter=False))
with contextlib.redirect_stdout(io.StringIO()):
    pa.cmd_scan(argparse.Namespace(bereich="1900-01-02", aufgaben="1,2,3", neu=False, gruppen=False))
reg = pa.lade_registry()
pruefe("verworfener Vorschlag wird nicht erneut angeboten", not any(c["art"] == "unmarkiert" and c["text"] == "Hofmannsthal" for c in reg["tage"].get("1900-01-02", {}).get("kandidaten", {}).values()))

print("Schutz vor uncommitteten Änderungen")
p2.write_text(p2.read_text(encoding="utf-8") + "\n", encoding="utf-8")
rc, out, err = apply_ops([{"op": "wrap", "tag": "1900-01-02", "anker": {"text": "Hofmannsthal"}, "ref": "pmb11740"}], dry=True, dateiname="dirty.json")
pruefe("apply bricht bei uncommitteten Änderungen an Zieldateien ab", rc == 2 and "uncommittete" in err)
git(root, "checkout", "-q", "--", "editions")

print("implied-Liste")
il = pa.ImpliedListe(root / "indices" / "x.txt")
i1, n1 = il.holen("Frau von A")
i2, n2 = il.holen("frau  von a")
i3, n3 = il.holen("Mann von B")
pruefe("Nummerierung fortlaufend, Beschreibung als Schlüssel", (i1, n1, i2, n2, i3, n3) == ("implied-person_1", True, "implied-person_1", False, "implied-person_2", True))
pruefe("ungültige Beschreibung wird abgelehnt", wirft(lambda: il.holen("a|b"), "implied"))
il.speichern()
il2 = pa.ImpliedListe(root / "indices" / "x.txt")
pruefe("Liste wird gespeichert und wieder eingelesen", il2.ids() == {"implied-person_1", "implied-person_2"} and il2.holen("Mann von B") == ("implied-person_2", False))

# ----------------------------------------------------------------------------------------------
print("Schreibschutz-Hook")
hook = HIER / "schreibschutz.py"


def hook_antwort(werkzeug, eingabe):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    r = subprocess.run([sys.executable, str(hook)], input=json.dumps({"tool_name": werkzeug, "tool_input": eingabe, "cwd": str(root)}),
                       capture_output=True, text=True, env=env)
    return "deny" in r.stdout


ed = str(root / "editions" / "entry__1900-01-01.xml")
pruefe("Edit auf editions/*.xml wird verweigert", hook_antwort("Edit", {"file_path": ed}))
pruefe("Write auf den Index wird verweigert", hook_antwort("Write", {"file_path": str(root / "indices" / "index_person_day.xml")}))
pruefe("Write auf implied-persons.txt wird verweigert", hook_antwort("Write", {"file_path": str(root / "indices" / "implied-persons.txt")}))
pruefe("Write nach temp/ ist erlaubt", not hook_antwort("Write", {"file_path": str(root / "temp" / "personen-auszeichnen" / "x.json")}))
pruefe("Edit auf listperson.xml ist nicht Sache des Hooks", not hook_antwort("Edit", {"file_path": str(root / "indices" / "listperson.xml")}))
pruefe("Bash: sed -i auf editions wird verweigert", hook_antwort("Bash", {"command": "sed -i 's/a/b/' editions/entry__1900-01-01.xml"}))
pruefe("Bash: Umleitung in editions wird verweigert", hook_antwort("Bash", {"command": "echo x > editions/entry__1900-01-01.xml"}))
pruefe("Bash: Python-Schreibzugriff wird verweigert", hook_antwort("Bash", {"command": "python3 -c \"open('editions/entry__1900-01-01.xml','w').write('')\""}))
pruefe("Bash: git checkout -- verweigert", hook_antwort("Bash", {"command": "git checkout -- editions"}))
pruefe("Bash: lesen ist erlaubt", not hook_antwort("Bash", {"command": "grep -c rs editions/entry__1900-01-01.xml"}))
pruefe("Bash: pa.py apply ist der erlaubte Schreibweg", not hook_antwort("Bash", {"command": "python3 .claude/skills/personen-auszeichnen/scripts/pa.py apply temp/x.json"}))
pruefe("Bash: pa.py schützt nicht den Rest der Kette", hook_antwort("Bash", {"command": "python3 .claude/skills/personen-auszeichnen/scripts/pa.py scan 1900 && sed -i s/a/b/ editions/entry__1900-01-01.xml"}))

# ----------------------------------------------------------------------------------------------
print("PMB-Relationen: Kürzen")
SPALTEN = ("relation_pk,relation_type,relation_class,relation_name,relation_start_date,relation_end_date,"
           "relation_start_date_written,relation_end_date_written,source,source_id,source_type,source_start_date,"
           "source_start_date_written,source_color,target,target_id,target_type,target_start_date,"
           "target_start_date_written,target_color").split(",")


def csv_zeile(pk, typ, klasse, von, bis, vw, bw, quelle, qid, ziel, zid):
    d = dict.fromkeys(SPALTEN, "")
    d.update(relation_pk=pk, relation_type=typ, relation_class=klasse, relation_start_date=von, relation_end_date=bis,
             relation_start_date_written=vw, relation_end_date_written=bw, source=quelle, source_id=qid, source_type="Person",
             target=ziel, target_id=zid, target_type="Person")
    return [d[k] for k in SPALTEN]


def pmb_person(n, vor, nach, sex, geb, tod=None, extra=""):
    todx = f'<death><date when-iso="{tod}">{tod}</date><settlement key="1"><placeName type="pref">Wien</placeName></settlement></death>' if tod else ""
    return (f'<person xml:id="person__{n}"><persName><forename>{vor}</forename><surname>{nach}</surname></persName>{extra}'
            f'<birth><date when-iso="{geb}">{geb}</date><settlement key="2"><placeName type="pref">Wien</placeName>'
            f'<location><geo>48 16</geo></location></settlement></birth>{todx}<sex value="{sex}"/>'
            f'<occupation key="9">Schriftsteller/Schriftstellerin</occupation>'
            f'<idno type="URL" subtype="pmb">https://pmb.acdh.oeaw.ac.at/entity/{n}/</idno></person>')


def baue_repo_relationen():
    import csv as _csv
    root2 = baue_repo()
    q = root2 / "temp-indices"
    q.mkdir()
    zeilen = [
        csv_zeile("1", "ist verheiratet mit (verwitwet)", "Person -> Person", "1901-06-08", "1929-07-15", "1901-06-08", "1929-07-15", "Hofmannsthal, Gertrude von", "2292", "Hofmannsthal, Hugo von", "11740"),
        csv_zeile("2", "ist verheiratet mit", "Person -> Person", "1890-05-01", "nodate", "1890-05-01", "nodate", "Salten, Ottilie", "99002", "Salten, Felix", "2167"),
        csv_zeile("3", "ist verheiratet mit (verwitwet)", "Person -> Person", "1889-01-06", "1941-04-04", "1889-01-06", "1941-04-04", "Hajek, Gisela", "2461", "Hajek, Markus", "2284"),
        csv_zeile("4", "ist Geschwister von", "Person -> Person", "nodate", "nodate", "nodate", "nodate", "Schnitzler, Arthur", "2121", "Hajek, Gisela", "2461"),
        csv_zeile("5", "ist Elternteil von", "Person -> Person", "nodate", "nodate", "nodate", "nodate", "Schnitzler, Johann", "12695", "Schnitzler, Arthur", "2121"),
        csv_zeile("6", "arbeitet für", "Person -> Person", "1900-01-01", "nodate", "1900", "nodate", "Hajek, Markus", "2284", "Salten, Felix", "2167"),
        csv_zeile("7", "ist Kind von", "Person -> Ort", "nodate", "nodate", "nodate", "nodate", "Hajek, Markus", "2284", "Wien", "50"),
    ]
    with open(q / "relations.csv", "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(SPALTEN)
        w.writerows(zeilen)
    personen = "".join([
        pmb_person(11740, "Hugo von", "Hofmannsthal", "male", "1874-02-01", "1929-07-15"),
        pmb_person(2292, "Gertrude von", "Hofmannsthal", "female", "1880-03-16", "1959-11-09", '<persName type="person_rufname_vorname">Gerty</persName>'),
        pmb_person(2167, "Felix", "Salten", "male", "1869-09-06", "1945-10-08"),
        pmb_person(99002, "Ottilie", "Salten", "female", "1868-03-07", "1933-01-01"),
        pmb_person(2284, "Markus", "Hajek", "male", "1861-09-23", "1941-04-04"),
        pmb_person(2461, "Gisela", "Hajek", "female", "1867-08-12", "1953-01-01"),
        pmb_person(2121, "Arthur", "Schnitzler", "male", "1862-05-15", "1931-10-21"),
        pmb_person(12695, "Johann", "Schnitzler", "male", "1835-04-10", "1893-05-02"),
        pmb_person(55555, "Unbeteiligt", "Person", "male", "1850-01-01"),
    ])
    (q / "listperson.xml").write_text('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt><title>L</title></titleStmt></fileDesc>'
                                      '<revisionDesc><change when-iso="2026-10-04">serialized</change></revisionDesc></teiHeader>'
                                      f'<text><body><listPerson>{personen}</listPerson></body></text></TEI>', encoding="utf-8")
    # Register um Markus Hajek ergänzen, zusätzliche Tage
    lp = (root2 / "indices" / "listperson.xml").read_text(encoding="utf-8")
    lp = lp.replace("</listPerson>", '<person xml:id="pmb2284"><persName><forename>Markus</forename><surname>Hajek</surname></persName><sex value="male"/></person>\n</listPerson>')
    (root2 / "indices" / "listperson.xml").write_text(lp, encoding="utf-8")
    tage = {
        "1899-03-01": ('            <p xml:space="preserve"><date when="1899-03-01">1/3</date> Mit <rs type="person" xml:id="pNt_00010" ref="#pmb11740"><surname>Hofmannsthal</surname></rs> und Frau spaziert.</p>', ["pmb11740"]),
        "1905-03-01": ('            <p xml:space="preserve"><date when="1905-03-01">1/3</date> Mit <rs type="person" xml:id="pNt_00011" ref="#pmb11740"><surname>Hofmannsthal</surname></rs> und Frau; <rs type="person" xml:id="pNt_00012" ref="#pmb2167"><surname>Salten</surname></rs> und Frau.</p>', ["pmb11740", "pmb2167"]),
        "1905-03-02": ('            <p xml:space="preserve"><date when="1905-03-02">2/3</date> Mit dem <rs type="allusively" xml:id="rst_00010">Schwager</rs> spazieren.</p>', ["pmb2284"]),
    }
    idx = (root2 / "indices" / "index_person_day.xml").read_text(encoding="utf-8")
    zusatz = ""
    for tag, (body, refs) in sorted(tage.items()):
        (root2 / "editions" / f"entry__{tag}.xml").write_text(TEI_KOPF.format(tag=tag, body=body), encoding="utf-8")
        zusatz += f'   <item target="{tag}">\n' + "".join(f"      <ref>{r}</ref>\n" for r in refs) + "   </item>\n"
    idx = idx.replace('   <item target="1900-01-01">', zusatz.split('   <item target="1905-03-01">')[0] + '   <item target="1900-01-01">', 1)
    idx = idx.replace("</list>", '   <item target="1905-03-01">' + zusatz.split('   <item target="1905-03-01">')[1] + "</list>")
    (root2 / "indices" / "index_person_day.xml").write_text(idx, encoding="utf-8")
    return root2


root2 = baue_repo_relationen()
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = pa.cmd_kuerzen(argparse.Namespace(quelle=None, ausgabe=None))
pruefe("kuerzen läuft durch", rc == 0)
rel_txt = pa.lies(pa.R.verw_relationen)
pers_txt = pa.lies(pa.R.verw_personen)
pruefe("nur Verwandtschaftsrelationen bleiben (5 von 7)", rel_txt.count("\n") == 6 and "arbeitet für" not in rel_txt and "Person -> Ort" not in rel_txt)
pruefe("nur beteiligte Personen bleiben (8 von 9), IDs als pmbN", pers_txt.count("<person ") == 8 and 'xml:id="pmb2292"' in pers_txt and "person__" not in pers_txt and "55555" not in pers_txt)
pruefe("Orte und Berufsschlüssel fallen weg, Lebensdaten und Rufname bleiben", "settlement" not in pers_txt and 'when-iso="1880-03-16"' in pers_txt and ">Gerty<" in pers_txt)
quelle = json.loads(pa.lies(pa.R.verw_quelle))
pruefe("Herkunftsdatei vermerkt Zahlen und Stand", quelle["relationen"] == 5 and quelle["personen"] == 8 and quelle["quelle_stand"] == "2026-10-04")
pruefe("Originaldateien bleiben unverändert", (root2 / "temp-indices" / "relations.csv").read_text(encoding="utf-8").count("\n") == 8)

print("PMB-Relationen: Nachschlagen")
vw = pa.Verwandtschaft()
pers_voll = dict(vw.personen)
pers_voll.update(pa.lade_personen())
pruefe("Verwandtschaft geladen", vw.vorhanden and "pmb2292" in vw.personen)
g99 = vw.zu_wort("pmb11740", "Frau", "1899-03-01", pers_voll)
g05 = vw.zu_wort("pmb11740", "Frau", "1905-03-01", pers_voll)
pruefe("Ehe vor der Heirat (1899) ist nicht gültig", g99[2] == [])
pruefe("Ehe nach der Heirat (1905) liefert Gerty", [c["ref"] for c in g05[2]] == ["pmb2292"] and g05[0] == "Ehe")
pruefe("Ehe nach dem Tod des Partners ist nicht gültig", vw.zu_wort("pmb11740", "Frau", "1930-01-01", pers_voll)[2] == [])
pruefe("Geschlecht filtert (»Mann« bei Hofmannsthal)", vw.zu_wort("pmb11740", "Mann", "1905-03-01", pers_voll)[2] == [])
sw = vw.zu_wort("pmb2121", "Schwager", "1905-03-01", pers_voll)[2]
pruefe("Schwager = Ehepartner der Schwester (2 Schritte)", [c["ref"] for c in sw] == ["pmb2284"])
pruefe("Elternteil über ist-Elternteil-von (Vater)", [c["ref"] for c in vw.zu_wort("pmb2121", "Vater", "1880-01-01", pers_voll)[2]] == ["pmb12695"])
pruefe("Elternteil nach dem Tod nicht mehr gültig", vw.zu_wort("pmb2121", "Vater", "1900-01-01", pers_voll)[2] == [])
pruefe("Gruppenwort wird erkannt (Kinder)", vw.zu_wort("pmb2121", "Kinder", "1905-03-01", pers_voll)[1] is True)
pruefe("Genitivform wird erkannt (Vaters)", pa.wort_rolle("Vaters") == ("Elternteil", "male") and pa.wort_rolle("Quark") is None)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pa.cmd_verwandte(argparse.Namespace(person="pmb11740", tag="1899-01-01", wort=None))
pruefe("verwandte zeigt Status zum Datum", "Gertrude" in buf.getvalue() and "[vor_beginn]" in buf.getvalue())

print("PMB-Relationen: Aufgabe 3 (implizite Personen)")
git(root2, "add", "-A")
git(root2, "commit", "-q", "-m", "relationen")
with contextlib.redirect_stdout(io.StringIO()):
    pa.cmd_scan(argparse.Namespace(bereich="1905-03", aufgaben="2,3", neu=True, gruppen=False))
reg2 = pa.lade_registry()
k1 = reg2["tage"]["1905-03-01"]["kandidaten"]
kh = next(c for c in k1.values() if c["art"] == "folgewort" and c["kopf"] == "pmb11740")
ks = next(c for c in k1.values() if c["art"] == "folgewort" and c["kopf"] == "pmb2167")
pruefe("Vorschlag Hofmannsthal und Frau: Gerty aus der PMB-Relation", kh["vorschlag"]["ref"] == "pmb2292" and kh["vorschlag"]["grund"].startswith("PMB-Relation"))
pruefe("Vorschlag Salten und Frau: Ehefrau außerhalb des Registers", ks["vorschlag"]["ref"] == "pmb99002" and ks["kandidaten"][0]["im_register"] is False)
with contextlib.redirect_stdout(io.StringIO()):
    pa.cmd_scan(argparse.Namespace(bereich="1899-03-01", aufgaben="3", neu=False, gruppen=False))
k99 = pa.lade_registry()["tage"]["1899-03-01"]["kandidaten"]
c99 = next(iter(k99.values()))
pruefe("vor der Heirat: neue Person statt Gerty, mit Hinweis auf die PMB", "neu" in c99["vorschlag"] and "vor_beginn" in c99["vorschlag"]["grund"])
with contextlib.redirect_stdout(io.StringIO()):
    pa.cmd_scan(argparse.Namespace(bereich="1905-03-01", aufgaben="3", neu=False, gruppen=False))
reg2 = pa.lade_registry()
k1 = reg2["tage"]["1905-03-01"]["kandidaten"]
entsch2 = pa.R.temp / "entsch-rel.json"
entsch2.write_text(json.dumps([{"k": k, "grund": "Test"} for k in k1]), encoding="utf-8")
buf, err = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
    rc = pa.cmd_apply(argparse.Namespace(dateien=[str(entsch2)], dry_run=False, unsauber=False, weiter=False))
pruefe("apply akzeptiert PMB-Personen außerhalb des Registers (implied)", rc == 0 and "außerhalb von indices/listperson.xml" in buf.getvalue() and "pmb99002" in buf.getvalue())
xr = lese(root2, "1905-03-01")
pruefe("implied-rs mit echter pmb-ID, Familienhaupt bleibt", 'ref="#pmb99002" subtype="implied">Frau</rs>' in xr and 'ref="#pmb2292" subtype="implied">Frau</rs>' in xr)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = pa.cmd_verify(argparse.Namespace(bereich=None))
pruefe("verify: keine Verstöße, Hinweis auf Personen außerhalb des Registers", rc == 0 and "nicht in indices/listperson.xml" in buf.getvalue())
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pa.cmd_register_luecken(argparse.Namespace())
pruefe("register-luecken nennt die Ehefrau mit Beziehung", "pmb99002|Ottilie Salten|Ehepartner von Felix Salten" in buf.getvalue())

print("PMB-Relationen: Aufgabe 2 (Verwandtschaftswörter)")
git(root2, "add", "-A")
git(root2, "commit", "-q", "-m", "implied angewendet")
with contextlib.redirect_stdout(io.StringIO()):
    pa.cmd_scan(argparse.Namespace(bereich="1905-03-02", aufgaben="2", neu=False, gruppen=False))
auto2 = json.loads(pa.lies(pa.R.temp / "1905-03-02" / "auto.json"))["ops"]
pruefe("allusively »Schwager« bekommt Markus Hajek über die Relation (Stufe A)", len(auto2) == 1 and auto2[0]["ref"] == "pmb2284" and "PMB-Relation" in auto2[0]["grund"])
pruefe("Gruppenwort »Buben« bleibt Stufe B", pa.wort_rolle("Buben") == ("Kind", "male") and "buben" in pa.GRUPPEN_WORTE)

print("Gesamtlauf: sichern und fortschritt")
(pa.R.temp / "1905-03").mkdir(parents=True, exist_ok=True)
(pa.R.temp / "1905-03" / "entscheidungen-A.json").write_text("[]", encoding="utf-8")
(pa.R.temp / "1905-03" / "bericht.md").write_text("# Bericht", encoding="utf-8")
(pa.R.temp / "1905-03" / "arbeitspaket.md").write_text("gross", encoding="utf-8")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = pa.cmd_sichern(argparse.Namespace(bereich="1905-03", keine_arbeit=False, notiz="Test"))
pruefe("sichern kopiert Entscheidungen und Bericht, nicht das Arbeitspaket", rc == 0 and (pa.R.lauf / "1905-03" / "entscheidungen-A.json").exists()
       and (pa.R.lauf / "1905-03" / "bericht.md").exists() and not (pa.R.lauf / "1905-03" / "arbeitspaket.md").exists())
with contextlib.redirect_stdout(io.StringIO()):
    pa.cmd_sichern(argparse.Namespace(bereich="1899-03", keine_arbeit=True, notiz=None))
pruefe("Monat ohne Arbeit steht im Fortschritt", "1899-03" in pa._fortschritt_lesen() and "keine Arbeit" in pa._fortschritt_lesen()["1899-03"][1])
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pa.cmd_fortschritt(argparse.Namespace(ab=None, anzahl=5))
monate_gesamt = len({t_[:7] for t_ in pa.alle_tage()})
pruefe("fortschritt zählt erledigte Monate und nennt die nächsten", f"2 von {monate_gesamt} Monaten erledigt" in buf.getvalue() and "nächste:" in buf.getvalue() or monate_gesamt == 2)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pa.cmd_fortschritt(argparse.Namespace(ab=None, anzahl=40, tage=1))
n_eins = [z for z in buf.getvalue().splitlines() if z.startswith("nächste:")][0].count(",") + 1
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pa.cmd_fortschritt(argparse.Namespace(ab=None, anzahl=40, tage=10**6))
n_alle = [z for z in buf.getvalue().splitlines() if z.startswith("nächste:")][0].count(",") + 1
pruefe("fortschritt --tage wählt mindestens einen Monat, bei hoher Grenze alle offenen", n_eins == 1 and n_alle == monate_gesamt - 2
       and "Einträge" in buf.getvalue())
(pa.R.temp / "1899-03").mkdir(parents=True, exist_ok=True)
fB = pa.R.temp / "1899-03" / "entscheidungen-B.json"
fB.write_text(json.dumps([{"op": "implied", "tag": "1899-03-01", "anker": {"text": "Frau", "vorher": "und "}, "neu": "Frau von Hugo von Hofmannsthal", "grund": "Test"}]), encoding="utf-8")
with contextlib.redirect_stdout(io.StringIO()):
    rc = pa.cmd_apply(argparse.Namespace(dateien=[str(fB)], dry_run=False, unsauber=False, weiter=False, ruhig=True))
pruefe("Protokoll landet im Ordner des Bereichs, auch wenn apply nur einen Tag berührt",
       rc == 0 and (pa.R.temp / "1899-03" / "protokoll.jsonl").exists() and not (pa.R.temp / "1899-03-01" / "protokoll.jsonl").exists())
with contextlib.redirect_stdout(io.StringIO()):
    pa.cmd_bericht(argparse.Namespace(bereich="1899-03"))
pruefe("Bericht zählt die angewendeten Operationen aus dem Bereichsordner", "implied: 1" in pa.lies(pa.R.temp / "1899-03" / "bericht.md"))
fp0 = pa._fingerprint()
e1 = pa.R.entry("1900-01-01")
e1.write_text(e1.read_text(encoding="utf-8") + "\n", encoding="utf-8")
pruefe("Korpus-Cache bleibt gültig, wenn sich Einträge ändern (Lernstand des Ausgangszustands)", pa._fingerprint() == fp0)
os.utime(pa.R.listperson, (1, 1))
pruefe("Korpus-Cache wird ungültig, wenn sich das Personenregister ändert", pa._fingerprint() != fp0)

print()
if fehler:
    print(f"{fehler} Fehler")
    sys.exit(1)
print("alles in Ordnung")
