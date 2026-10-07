---
name: personen-auszeichnen
description: >-
  Zeichnet Personen in den Tagebucheinträgen (editions/entry__YYYY-MM-DD.xml) aus: (1) prüft bestehende
  rs[@type='person'] (nur melden) und zieht Wiederholungen am selben Tag nach, (2) gleicht mit
  indices/index_person_day.xml ab (fehlendes @ref an rs ohne Identifier, auch an rs type="allusively" wie »Mama«; neue rs
  für Index-Personen, die im Text unmarkiert stehen), (3) findet implizit erwähnte Personen (»Hofmannsthal und Frau«,
  »bei Beer-Hofmanns«) und zeichnet sie als rs subtype="implied" aus; neue Kennungen implied-person_N stehen in
  indices/implied-persons.txt. Schreibt nur über den Helfer pa.py. Verwenden, sobald jemand Personen im Tagebuch auszeichnen
  oder verknüpfen, den Personenindex abgleichen, rs ohne ref ergänzen oder implizite Personen, Ehefrauen und Familien finden
  will (Tag, Monat, Jahr). Nicht für Orte, Werke, Briefe, Lektorat oder zum Anlegen von PMB-Einträgen.
argument-hint: "[YYYY-MM-DD | YYYY-MM | YYYY | von..bis]"
disable-model-invocation: true
allowed-tools:
  - Bash(python3 .claude/skills/personen-auszeichnen/scripts/pa.py *)
  - Bash(python3 .claude/skills/personen-auszeichnen/scripts/test_skill.py)
  - Bash(git status*)
  - Bash(git diff*)
  - Edit(/temp/personen-auszeichnen/**)
  - Write(/temp/personen-auszeichnen/**)
hooks:
  PreToolUse:
    - matcher: "Edit|Write|MultiEdit|NotebookEdit|Bash"
      hooks:
        - type: command
          command: 'python3 "${CLAUDE_PROJECT_DIR}/.claude/skills/personen-auszeichnen/scripts/schreibschutz.py"'
---

# Personen im Tagebuch auszeichnen

Angabe: $ARGUMENTS

Du zeichnest Personen in `editions/entry__*.xml` aus, gleichst sie mit `indices/index_person_day.xml` ab und findest
implizit erwähnte Personen. **Der Helfer `pa.py` macht die Mechanik** (Kandidaten finden, XML ändern, Sicherungen);
**du urteilst nur über Mehrdeutiges** (Spitznamen, Kürzel, Verwandtschaftswörter, Possessiv oder Haushalt,
Zeitabhängigkeit). Die Redaktion prüft danach den Git-Diff und committet.

## Die eine Regel: geschrieben wird nur über `pa.py apply`

Du änderst **kein** XML direkt (nicht mit Edit, Write, sed, Python …). Der Hook `scripts/schreibschutz.py` verweigert
es. Warum: Nur `apply` stellt sicher, dass der Text unverändert bleibt (nur Tags und Attribute kommen hinzu), dass jede
Operation eindeutig verankert ist und dass jede `xml:id` neu und eindeutig ist. Meldet der Hook eine Verweigerung, ist
das die Regel, kein Fehler. Du schreibst nur Entscheidungsdateien nach `temp/personen-auszeichnen/<Bereich>/`.

Außerdem gilt: Du ordnest **nie** eine Person ohne Beleg zu (Index des Tages, PMB-Name, Kontext). Im Zweifel nicht
anwenden, sondern im Bericht nennen. Bestehende `@ref` änderst du nie; Auffälligkeiten meldest du nur.

## Was schon da ist

`H` steht für `python3 .claude/skills/personen-auszeichnen/scripts/pa.py` (alle Befehle aus dem Repo-Wurzelverzeichnis).

- `H scan <Bereich> [--aufgaben 1,2,3]` liest nur und schreibt `arbeitspaket.md` (zum Lesen), `auto.json` (Stufe A) und das
  Kandidatenregister. `H apply <Dateien…> [--dry-run]` ist der einzige Schreibweg. `H verify`, `H bericht <Bereich>`,
  `H namensformen --person pmbN | --wort Mama`, `H implied-liste`.
- **PMB-Relationen** (Ehepartner, Kinder, Eltern, Geschwister, Schwager …): `H verwandte pmbN [--tag YYYY-MM-DD]` zeigt alle
  Relationen einer Person mit Gültigkeit am Tag, `H verwandte pmbN --wort Frau --tag …` die Kandidaten für ein Wort.
  `H kuerzen` erzeugt die Daten (`data/verwandtschaft-*`) aus den ungekürzten PMB-Dateien in `temp-indices/` (relations.csv,
  listperson.xml); nur nötig, wenn die PMB-Daten neu heruntergeladen wurden. `H register-luecken` listet PMB-Personen, die in
  den Einträgen oder im Index vorkommen, aber nicht in `indices/listperson.xml` stehen.
- `references/konventionen.md`: XML-Muster mit Korpusbelegen (**lies es vor dem ersten Durchgang**).
- `references/implied.md`: Erkennung und Urteil bei impliziten Personen (**vor Durchgang B**).
- `references/haushalte.md`: von der Redaktion bestätigte Paare (gehen den PMB-Relationen vor); wächst mit.
- `data/`: gekürzte PMB-Relationen (`verwandtschaft-relationen.csv`, `verwandtschaft-personen.xml`, `verwandtschaft-quelle.json`
  mit Herkunft und Stand); Teil des Skills, rund 2 MB.
- `references/cloud-lauf.md`: Gesamtlauf unbeaufsichtigt in der Claude-Cloud (Routine): Aufbau, Prompt, Prüfen. Dazu `H fortschritt`
  (welche Monate sind erledigt) und `H sichern <Monat>` (Entscheidungen, Bericht und Fortschritt nach `lauf/`).
- `scripts/offene_fragen.py` (mit Vorlage `offene_fragen.html`): sammelt nach einem Gesamtlauf die offenen Punkte (neue
  implied-Personen mit Bezugsperson und Beziehung, Register-Lücken, Index-Personen ohne Textstelle, auffällige Altbestände,
  nicht entschiedene Auslöser) und baut `temp/personen-auszeichnen/offene-fragen/offene-fragen.html`, ein Arbeitswerkzeug für
  die Redaktion. Dessen Export ist eine Entscheidungsdatei, die `H apply` direkt annimmt. Dazu `neue-personen.csv` und
  `register-luecken.csv`. Liest nur.
- `scripts/test_skill.py`: Regressionstest (nach Änderungen an den Skripten).

Die Edition kennt drei Auszeichnungsarten, die du nicht vermischst: `type="person"` (Name genannt), `type="allusively"`
(Verwandtschafts- und Rollenwörter wie »Mama«, »Vater«, »Kinder«, »Hofrätin«, ohne Namen) und `type="person"
subtype="implied"` (mitgemeinte Personen: »und Frau«, Familienformen). Allusively-`rs` bekommen ihr `@ref` aus dem Index;
`type` und die `rst_`-ID bleiben.

## Ablauf

Ein Durchgang bearbeitet **einen Monat** (rund 30 Tage); für ein Jahr arbeitest du Monat für Monat. Bei leerer Angabe
frag nach Bereich (Empfehlung: ein Monat). Zwei Durchgänge je Bereich: A (Aufgaben 1 und 2), dann B (Aufgabe 3), weil
implizite Personen ausgezeichnete Köpfe voraussetzen.

### 0 Vorbereiten

`git status --short editions indices`: Gibt es uncommittete Änderungen an `editions/` oder `indices/`, sag der Redaktion,
dass erst committet werden muss (`apply` bricht sonst ab). Beim ersten Mal in der Sitzung `references/konventionen.md` lesen.

### 1 Durchgang A: scan, entscheiden, anwenden

1. `H scan 1905-03 --aufgaben 1,2` (baut beim ersten Mal den Korpus-Cache, ca. 30 s). Lies die Kurzübersicht.
2. Lies `temp/personen-auszeichnen/1905-03/arbeitspaket.md` **in Stücken** (Read mit `offset`/`limit`, etwa zehn Tage je
   Stück). Je Tag steht der Text mit eingebetteten Markierungen, der Index mit Haken, dann Arbeit. Legende:

   | Zeichen | Bedeutung |
   |---|---|
   | `⟦Text\|pmb123⟧` | ausgezeichnet (Text, ref); `a:` = allusively, `i:` = implied |
   | `⟦Text\|?pNt_10251⟧` | rs **ohne** ref (die `xml:id` steht nach dem `?`) |
   | Index `✓` / `✗` | Person steht im Text mit ref / fehlt |
   | `Stufe A (automatisch …)` | eindeutig, steht in `auto.json`, nur Stichprobe nötig |
   | `- fehlt: pmbN …` + `[Tag#n] art »Text« Stufe k` | Kandidaten für eine Index-Person |
   | `- ohne Kandidat im Text` | Stufe C: nichts anwenden, im Bericht nennen |
   | `- Prüfung: …` | Aufgabe 1a (ausreisser, vor_geburt, nicht_im_index, ref_unbekannt): nur melden |
   | `- Wiederkehr? [Tag#n]` | Aufgabe 1b: derselbe Name kommt unmarkiert nochmals vor |

   Kandidatenarten: `rs_ohne_ref` und `allusively` (vorhandenes rs bekommt ref), `unmarkiert` (neues rs um den Text),
   `verwandtschaft` (neues allusively-rs um ein Verwandtschaftswort, das der Korpus oder die PMB-Relation dieser Person
   zuordnet). Ein Zusatz `[Schwager = Schwager von Arthur Schnitzler (PMB-Relation)]` bedeutet: Die Person steht laut PMB am
   Datum in dieser Rolle zu Schnitzler; ist sie die einzige Index-Person ohne ref mit dieser Rolle, steht die Zuordnung in
   `auto.json` (Stufe A). Plurale und Gruppenwörter (Kinder, Buben, Eltern, Geschwister) bleiben Stufe B (Mehrfach-ref).
   `Stufe k`: 3 = PMB-Namensform, 2 = gelernte Form oder Abkürzung, 1 = Initiale oder ähnlich. `GATTUNGSWORT?` heißt: Das
   Wort ist meist ein gewöhnliches Wort (Zimmer, Mann). `MEHRDEUTIG`: passt auf mehrere Personen des Tages.
3. Entscheide (Regeln unten) und schreibe `temp/personen-auszeichnen/1905-03/entscheidungen-A.json` (Format unten).
   **Alle Entscheidungen eines Tages gehören in dieselbe Datei und denselben `apply`-Aufruf**: Nach dem Schreiben sind die
   Kandidaten dieses Tages veraltet.
4. `H apply temp/personen-auszeichnen/1905-03/auto.json temp/personen-auszeichnen/1905-03/entscheidungen-A.json --dry-run`.
   Lies die Ausgabe (jede Operation mit Grund) und achte auf Fehler. Dann ohne `--dry-run` (mit `--ruhig`, wenn du die
   Operationen schon gelesen hast: dann erscheinen nur Zusammenfassung, Hinweise und Fehler).

### 2 Durchgang B: implizite Personen

Lies `references/implied.md`. Dann `H scan 1905-03 --aufgaben 3`, `arbeitspaket.md` lesen, `entscheidungen-B.json`
schreiben, `apply … --dry-run`, `apply`. Pro Auslöser (`[Tag#n] folgewort|familienform|besitz`) steht ein Vorschlag:
`ref` (echte pmb-ID), `neue Person` (→ `implied-person_N`) oder `Kein Vorschlag`. Die Kandidaten kommen **zuerst aus den
PMB-Relationen** (verheiratet mit Zeitraum, Kinder, Geschwister …), erst ohne Relationsdaten aus Namen und gemeinsamer
Erwähnung. Steht bei einem Kandidaten `NICHT im Tagebuch-Register`, existiert die Person im PMB, ist aber noch nicht in
`indices/listperson.xml`: Du darfst ihre echte pmb-ID verwenden (`apply` akzeptiert sie und meldet sie), die Redaktion nimmt
sie danach in der PMB in die Sammlung des Tagebuchs auf (`H register-luecken`). Zweifelhaft ist besonders `Datum unsicher`
(Heiratsdatum im PMB unbekannt): dann Kontext und gemeinsame Erwähnung prüfen.

### 3 Abschluss

`H verify` (muss »keine Verstöße« melden), `H bericht 1905-03`, dann antworte knapp auf Deutsch (siehe unten).

## Entscheidungsdatei

Eine JSON-Liste. Der Normalfall verweist auf eine Kandidaten-Kennung:

```json
[
  {"k": "1903-09-02#1", "grund": "Hajeks = Markus und Gisela Hajek"},
  {"k": "1922-07-22#1", "ref": ["pmb25918", "pmb25921"], "grund": "Hr. Frau Tels: beide in einem rs"},
  {"k": "1922-07-22#2", "verwerfen": true, "grund": "mit #1 erledigt"},
  {"k": "1921-01-06#1", "neu": "Frau von Richard Specht", "grund": "Ehefrau nicht im PMB"},
  {"k": "1921-03-05#3", "verwerfen": true, "grund": "Gattungswort"}
]
```

- `k`: Kennung aus dem Arbeitspaket. Ohne weitere Felder wird der Vorschlag übernommen (`ref` des Kandidaten bzw. der
  Vorschlag bei Auslösern). Überschreiben: `ref` (String oder Liste für Mehrfach-ref), `neu` (Beschreibung einer neuen
  implied-Person), `typ` (`person`|`allusively`), `teile` (z. B. `["forename:Anna","surname:Reich"]`), `ohne_teile: true`,
  `index: false` (implied nicht in den Index), `grund`.
- `verwerfen: true`: Der Vorschlag wird nicht mehr angeboten (steht in `temp/personen-auszeichnen/verworfen.json`).
- **Freie Operation**, nur wenn der Scan keinen Kandidaten liefert, du aber eine sichere Stelle siehst:
  `{"op":"wrap","tag":"1903-05-01","anker":{"text":"Papas","vorher":"Grab "},"ref":"pmb12695","typ":"allusively","grund":"…"}`.
  Weitere Operationen: `set_ref` (`id`, `ref`; nur an rs ohne ref), `add_ref` (`id`, `ref`: hängt weitere Personen an den vorhandenen ref eines rs an, z. B. »Hajeks« = zwei Personen), `implied` (`anker` oder `um_rs`, `ref` oder `neu`), `index_add`.
  Der Anker steht im **Klartext ohne die Markierungen ⟦…⟧**, besser mit kurzem `vorher`/`nachher` (höchstens 12 Zeichen,
  ohne Zeilenumbruch) oder mit `nr` (n-ter freier Treffer).
- Ein `ref` muss zu den Index-Refs des Tages (oder zu den Refs im Text desselben Tages) gehören; sonst weist `apply` ihn
  ab (`frei: true` hebt das auf, nur mit Begründung). Mehrere Personen für dasselbe rs: **eine** Operation mit `ref`-Liste.

## Urteilsregeln Durchgang A

- Nimm einen Kandidaten nur, wenn Name, Kontext und Lebensdaten zusammenpassen und die Person laut Index an diesem Tag
  vorkommt. Spitznamen und Kürzel (»Dilly«, »F.s«, »Mz. Rh.«) prüfst du mit `H namensformen --person pmbN` (gelernte Formen).
- **Alle** Erwähnungen einer Person am Tag werden ausgezeichnet (Wiederkehr), außer das Wort ist ein Gattungswort oder meint
  erkennbar eine andere Person gleichen Namens.
- Verwandtschaftswörter (Papa, Mama, Vater, Schwester, Schwager …) und Rollenwörter (Hofrätin, Kaiser) sind
  `allusively`; bezieht sich ein Wort auf **fremde** Verwandte (»Annerls Mutter«), bleibt es ohne ref.
- Gleichnamige Personen (Richard Horn 1879, später Richard Beer-Hofmann; Gustav und Sigmund Schneider am selben Tag):
  Kontext und Zeit entscheiden; unklar → verwerfen und im Bericht nennen.
- Aufgabe 1a (Prüfbefunde) und Index-Personen ohne Kandidat nimmst du nur in den Abschlussbericht auf.
- Die PMB-Relationen sind ein starker Beleg, aber kein Beweis: Sie sagen, wer **verheiratet, verwandt oder verschwägert ist**,
  nicht, wer im Text **gemeint** ist (»Schwager« kann auch Annerls Schwager sein; »Frau« ein anderer Haushalt). Nimm sie als
  Beleg, wenn Index und Kontext nicht widersprechen. Mehrere Personen in derselben Rolle: Index des Tages und Kontext entscheiden.

## Abschluss-Antwort

Antworte knapp auf Deutsch, ohne den Bericht zu wiederholen: Bereich; Zahl der Operationen je Art (set_ref, wrap, implied);
Zahl der Dateien; neue `implied-person_N` (die Zeilen aus der Liste); PMB-Personen außerhalb des Registers, die du neu
verwendet hast (`apply` meldet sie; die Redaktion nimmt sie in der PMB auf); die drei bis fünf wichtigsten Prüffälle mit Tag;
Ergebnis von `verify` (genau wie gemeldet); offene Punkte (Stufe C, Index-implied ohne Textanker); ein Vorschlag für die
Commit-Meldung (z. B. `Personen ausgezeichnet: 1905-03`); der Link zum Bericht als Markdown-Link. Du committest nicht.

## Wenn etwas schiefgeht

| Meldung von `apply` | Was tun |
|---|---|
| `Anker … mehrdeutig` | `vorher`/`nachher` ergänzen oder `nr` setzen |
| `Anker … nicht gefunden (… in bereits ausgezeichnetem Text)` | Stelle ist schon ein rs; ggf. `set_ref` statt `wrap` |
| `seit dem scan geändert` | `scan` für den Tag wiederholen, Entscheidung neu schreiben |
| `uncommittete Änderungen` | Redaktion bitten zu committen (oder `--unsauber`, nur auf ausdrückliche Anweisung) |
| `gehört nicht zu den Index-Refs` | `ref` prüfen; nur mit Begründung `frei: true` |
| `bekommt in diesem Lauf schon einen ref` | `ref`-Liste in einer Operation |
| `weder in listperson.xml … noch in den PMB-Verwandtschaftsdaten` | ID prüfen (`H verwandte pmbN`); fehlt die Person auch dort, `neu` mit Beschreibung |

Nach unerwarteten Ergebnissen: `H verify`; `git diff` zeigt jede Änderung. Zurück geht es mit `git checkout -- <Datei>` durch
die Redaktion (der Hook sperrt dir das).
