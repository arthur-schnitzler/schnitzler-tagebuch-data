# Gesamtlauf in der Claude-Cloud (Routine)

Der Skill kann unbeaufsichtigt in einer Cloud-Sitzung laufen. Die Sitzung arbeitet in einem frischen Git-Checkout von GitHub: Sie
sieht nur, was dort liegt, nichts von der lokalen Arbeitskopie (auch nicht `temp-indices/`). Skill und `data/` müssen deshalb auf
einem Branch auf GitHub stehen, bevor die Routine startet.

## Voraussetzung: Claude-GitHub-App

Die Cloud-Sitzung klont das öffentliche Repository ohne Anmeldung, **pusht aber nur, wenn die Claude-GitHub-App für das Repository
freigegeben ist** (sonst `403 … Claude doesn't have GitHub access`; so im ersten Pilot am 2026-10-04). Eine Organisation
braucht dafür einen Administrator: <https://github.com/apps/claude/installations/select_target> (Organisation wählen, nur dieses
Repository freigeben) oder GitHub unter <https://claude.ai/customize/connectors> neu verbinden. Besser vorher auf `master` eine
Regel setzen, die direkte Pushes für die App ausschließt (Ruleset mit Bypass nur für GitHub Actions und Administratoren; ein
einfacher Schutz »Pull Request erforderlich« würde den wöchentlichen Bot-Lauf blockieren).

## Aufbau

| Baustein | Festlegung |
|---|---|
| Skill-Branch | `claude/personen-skill`: aktueller `origin/master` plus der Ordner `.claude/skills/personen-auszeichnen/` (mit `data/`) und der Eintrag `/temp-indices` in `.gitignore` |
| Arbeitsbranch | `claude/personen-lauf`: entsteht aus dem Skill-Branch, die Sitzungen setzen ihn fort; nie nach `master` mergen, nur per Pull Request nach Durchsicht |
| Reihenfolge | strikt chronologisch und nacheinander, **nicht parallel**: neue `xml:id`s (globales Maximum + 1), die Nummern der `implied-person_N` und `index_person_day.xml` sind gemeinsamer Zustand |
| Einheit | ein Monat je Durchgang A und B, ein Commit je Monat (`Personen ausgezeichnet: YYYY-MM`), danach Push |
| Fortschritt | `lauf/fortschritt.txt` (Befehl `pa.py fortschritt`); eine neue Sitzung macht beim ersten offenen Monat weiter |
| Nachweis | `pa.py sichern <Monat>` legt Entscheidungen, Bericht und Protokoll nach `lauf/<Monat>/` und damit in den Commit |

Neue `pNt_`-IDs laufen über 99999 hinaus (der fünfstellige Vorrat reicht für einen Gesamtlauf nicht): `pNt_100000` und so weiter;
`pa.py verify` akzeptiert das. Weicht die eigene Werkzeugkette der Redaktion bei sechsstelligen Nummern ab, vorher prüfen.

## Prompt der Routine (Wortlaut, Fortsetzungs-Variante)

```
Du arbeitest im Repository arthur-schnitzler/schnitzler-tagebuch-data (TEI-Daten der Tagebücher Arthur Schnitzlers,
editions/entry__YYYY-MM-DD.xml). Aufgabe: Mit dem Projekt-Skill personen-auszeichnen Personen in den Einträgen auszeichnen, mit
indices/index_person_day.xml abgleichen und implizit erwähnte Personen finden. Du arbeitest unbeaufsichtigt; niemand beantwortet
Rückfragen. Entscheide nach den Regeln des Skills und halte dich im Zweifel zurück (nichts anwenden, im Bericht nennen).

1. Einrichten
   - git fetch origin. Arbeitsbranch claude/personen-lauf: Gibt es origin/claude/personen-lauf, dann
     git checkout -B claude/personen-lauf origin/claude/personen-lauf, sonst
     git checkout -B claude/personen-lauf origin/claude/personen-skill.
   - Push-Test sofort: git push -u origin claude/personen-lauf (noch ohne neue Commits). Scheitert er (z. B. 403), brich ab und melde
     das, bevor du Arbeit investierst.
   - python3 -c "import lxml" (falls es fehlt: pip install lxml).
   - Lies .claude/skills/personen-auszeichnen/SKILL.md vollständig und references/konventionen.md; vor Durchgang B references/implied.md.
     Der Skill ist deine Arbeitsanweisung; die Punkte hier ergänzen sie. Der Schreibschutz-Hook ist in dieser Sitzung nicht aktiv:
     Ändere XML-Dateien trotzdem nie direkt, nur mit pa.py apply.
   - python3 .claude/skills/personen-auszeichnen/scripts/test_skill.py muss »alles in Ordnung« melden, sonst brich ab und melde es.
2. Bereich: python3 .claude/skills/personen-auszeichnen/scripts/pa.py fortschritt --anzahl 12 nennt die nächsten offenen Monate.
   Bearbeite sie der Reihe nach (höchstens 12 in dieser Sitzung).
3. Je Monat nach SKILL.md (Durchgang A mit --aufgaben 1,2, dann B mit --aufgaben 3), mit diesen Änderungen für den Lauf:
   - Du fragst nicht nach; Entscheidungen schreibst du selbst in temp/personen-auszeichnen/<Monat>/entscheidungen-A.json und -B.json.
   - Je Durchgang: apply --dry-run (Ausgabe lesen), danach apply --ruhig. Committe nach Durchgang A (git add editions indices;
     git commit -m 'Personen ausgezeichnet: YYYY-MM (Durchgang A)'), bevor du Durchgang B beginnst: Das Arbeitsverzeichnis muss
     für apply sauber sein. Lass keine unversionierten Dateien zurück (der Stop-Hook der Sitzung prüft das).
   - Nach Durchgang B: pa.py verify muss »keine Verstöße« melden. Sonst: Ursache klären; was verify nicht besteht, wird nicht
     committet (nur die betroffenen Dateien mit git checkout -- <Datei> zurücksetzen) und der Monat mit
     pa.py sichern <Monat> --keine-arbeit --notiz "verify fehlgeschlagen: …" vermerkt.
   - pa.py bericht <Monat>, dann pa.py sichern <Monat>; Monate ohne Arbeit: pa.py sichern <Monat> --keine-arbeit.
   - git add editions indices .claude/skills/personen-auszeichnen/lauf; git commit -m "Personen ausgezeichnet: YYYY-MM";
     git push origin claude/personen-lauf. Bei »non-fast-forward« git pull --rebase und erneut pushen; bei anderen Push-Fehlern
     die Sitzung mit klarer Meldung beenden.
4. Grenzen: Du änderst nur editions/, indices/index_person_day.xml, indices/implied-persons.txt und
   .claude/skills/personen-auszeichnen/lauf/. Kein Merge nach master, kein Pull Request, kein Force-Push, keine Änderung an
   listperson.xml, listplace.xml, listwork.xml.
5. Ende: Alles gepusht? Gib aus: erledigte Monate, Zahl der Operationen je Art, neue implied-person-Kennungen, PMB-Personen
   außerhalb des Registers, offene Punkte (Stufe C, Prüfbefunde), Probleme.
```

**Pilot-Variante**: Statt Schritt 2: »Bearbeite genau diese Monate: 1880-05, 1902-07, 1905-03, 1921-11.« Der Pilot geht in denselben Branch;
die Redaktion prüft den Diff (`git diff origin/master...claude/personen-lauf`) und die Berichte unter `lauf/`, bevor der Lauf fortgesetzt wird.

## Routine anlegen

Umgebung »Default«, Modell Sonnet 5.5 (für den Pilot; danach nach Qualität entscheiden), Quelle
`https://github.com/arthur-schnitzler/schnitzler-tagebuch-data`, Werkzeuge Bash, Read, Write, Edit, Glob, Grep. Die Routine hat keinen
Zeitplan (einmalig, deaktiviert) und wird je Sitzung mit »Run now« gestartet. Läufe lassen sich in `claude.ai/code/routines` ansehen.

## Prüfen

- `python3 .claude/skills/personen-auszeichnen/scripts/pa.py verify` über den ganzen Branch (muss »keine Verstöße« melden).
- Stichprobe von rund 100 Änderungen je Jahrgang (Schwelle des Plans: ≥ 98 % richtig); `pa.py register-luecken` und
  `pa.py implied-liste` für die Redaktion (PMB-Aufnahme, neue Personen).
- Der Branch ändert `index_person_day.xml` flächig; manuelle Arbeit der Redaktion an dieser Datei und an denselben Einträgen
  während des Laufs vermeiden, sonst gibt es Merge-Konflikte.

## Offene Unsicherheiten (erst im Pilot klar)

Ob die Cloud-Sitzung auf `claude/…`-Branches pushen darf, ob `lxml` vorhanden oder installierbar ist, wie lange eine Sitzung läuft
und was das Kontingent hergibt. Darum zuerst der Pilot.
