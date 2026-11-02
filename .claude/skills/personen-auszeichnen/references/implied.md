# Implizit erwähnte Personen (Durchgang B)

Gemeint sind Personen, die der Text nicht nennt, aber mitmeint: die Ehefrau in »Hofmannsthal und Frau«, der Haushalt in »bei
Beer-Hofmanns«, die Frau in »mit ihm und seiner Frau«. Sie bekommen ein `rs subtype="implied"` und, wenn sie im PMB nicht
vorkommen, eine Kennung `implied-person_N`.

## Auslöser, die der Scan liefert

| Art | Muster | Anker |
|---|---|---|
| `folgewort` | ausgezeichnete Person, dann »und/mit/sowie … Frau, Gattin, Gemahlin, Mann, Tochter, Sohn, Bruder, Schwester, Mutter, Vater« | das Wort selbst (reiner Text) |
| `familienform` | ausgezeichneter Nachname im Genitiv/Plural (»Salten’s«, »Speidels«) | der bestehende `rs` wird umschlossen (`um_rs`) |
| `besitz` | »seiner/ihrer/dessen/deren Frau, Mann, Tochter …« hinter einer ausgezeichneten Person (Kopf geraten: **prüfen**) | das Wort |
| Index-implied ohne rs | `<ref ana="implied">` im Index, im Text nichts ausgezeichnet | Auslöser des Tages, sonst ohne Textanker |
| Gruppenwörter | »wir vier«, »und Familie«, »und Kinder« | nur gemeldet, in Version 1 nicht ausgezeichnet |

Gruppenwörter, die schon als `rs type="allusively"` ausgezeichnet sind (Kinder, Eltern, Geschwister), gehören zu Durchgang A
und bekommen dort ein (Mehrfach-)`ref`.

## Urteil: ist es wirklich eine mitgemeinte Person?

1. **Possessiv oder Haushalt?** »bei/zu/mit/von Salten’s« meint die Familie. »Freuds Person«, »Bassermanns Erfolg«,
   »Mann’s Prof. Unrath« sind Genitive des Besitzes: **verwerfen**. Der Scan vermerkt, ob eine Präposition davor steht
   (`nach Präposition` bzw. `KEINE Präposition davor`); ohne Präposition ist Possessiv der Normalfall, es sei denn, der Kontext
   zeigt Besuch, Gesellschaft oder Begleitung.
2. **Anrede statt Beziehung?** »und Frau Reich« hat einen Namen und ist keine implizite Person (der Scan schließt das aus);
   auch »Frau Dr.«, »Herr und Frau Askonas« (steht dann in einem rs) sind keine.
3. **Zeit**: Die Beziehung muss am Datum bestehen. Hofmannsthal heiratete 1901; »Hofmannsthal und Frau« 1899 ist nicht
   Gerty (pmb2292). Wer mehrfach verheiratet war (Bahr), braucht je Ehe eine Person. Die Lebensdaten der Kandidaten stehen im
   Arbeitspaket; Der Helfer schlägt niemanden vor, der am Datum jünger als 16 oder schon verstorben ist.
4. **Wer ist gemeint?** Bei `besitz` ist der Kopf eine Vermutung (letzte ausgezeichnete Person davor mit passendem Geschlecht).
   Stimmt er nicht, verwirf oder setze die Operation frei (`um_rs`/`anker` mit eigenem `ref`).

## Wer ist die mitgemeinte Person?

Der Scan schlägt die Person aus den **PMB-Relationen** vor (`data/verwandtschaft-relationen.csv`, auf Verwandtschaft gekürzt aus
dem ungekürzten PMB-Export; Herkunft und Stand in `data/verwandtschaft-quelle.json`). Das Wort im Text bestimmt die Rolle:

| Wort | gesucht in den Relationen |
|---|---|
| Frau, Gattin, Gemahlin / Mann, Gatte, Familienform | Ehepartner, deren Ehe am Datum besteht (Zeitraum der Relation, Lebensdaten, Mindestalter 16) |
| Tochter, Sohn | Kind des Kopfes (weiblich/männlich), am Datum lebend |
| Bruder, Schwester | Geschwister (auch Halb- und Stiefgeschwister) |
| Mutter, Vater | Eltern |
| Schwager, Schwägerin | direkte »verschwägert«-Relation, Ehepartner der Geschwister, Geschwister des Ehepartners |

Gruppenwörter (Kinder, Eltern, Geschwister, Familie) werden nur gemeldet.

- **Gültigkeit am Datum**: `vor_beginn` (Ehe beginnt später), `nach_ende` (geschieden, verwitwet), `nicht_am_leben`, `zu_jung`.
  Heiratsdaten mit nur einer Jahreszahl gelten für das ganze Jahr; bei fehlendem Beginn steht `Datum unsicher` (dann prüfst
  du Ko-Erwähnung und Kontext). `H verwandte pmbN --tag YYYY-MM-DD` zeigt alle Relationen mit Status.
- Das PMB kennt nicht alles: Bei 104 von 449 Ehe-Auslösern in drei Probejahren hatte der Kopf keine Ehe-Relation. Dann (und nur
  dann) fällt der Scan auf Namen und gemeinsame Erwähnung zurück und kennzeichnet das (`keine PMB-Relation bekannt`).
- Kandidaten tragen weitere Belege: `im Index des Tages` (stärkster), `zusammen erwähnt n Tage ±3 J.` (Ko-Erwähnung),
  `Haushalt bestätigt` (`haushalte.md`, geht vor).

Vorschlagsreihenfolge: bestätigter Haushalt, Index-implied des Tages, genau eine gültige PMB-Relation, mehrere Relationen und
nur eine davon im Index des Tages, Namen/Ko-Erwähnung (nur ohne Relationsdaten), sonst `neu` bzw. `Kein Vorschlag`. Gibt es
mehrere gültige Personen ohne Unterscheidung (zwei Ehen mit unbekannten Daten), steht `Kein Vorschlag`: Du entscheidest mit dem
Kontext oder verwirfst.

- **Gibt es die Person im PMB, nimm ihre echte ID** (Entscheidung der Redaktion), auch wenn sie noch nicht in
  `indices/listperson.xml` steht (`NICHT im Tagebuch-Register`): `apply` akzeptiert die ID, meldet sie und `H register-luecken`
  führt sie für die Redaktion. `implied-person_N` nur ohne PMB-Treffer.
- Beschreibung neuer Personen: `<Beziehung> von <Vorname Nachname laut PMB des Kopfes>`: »Frau von Rudolf Lothar«, »Tochter
  von Paul Goldmann«. Wechselt die Person (zweite Ehe), ergänze die Beschreibung: »erste Frau von Hermann Bahr«.
- Gleiche Beschreibung = gleiche Person = gleiche Nummer (der Helfer vergibt sie).

## Verwandtschaftswörter aus Schnitzlers Sicht (Aufgabe 2)

Auch für `allusively`-Wörter (Schwager, Tante, Bruder, Schwiegermutter …) nutzt der Scan die Relationen: Steht eine Index-Person
ohne ref am Datum in dieser Rolle zu Arthur Schnitzler, ist sie Kandidat für das Wort; ist sie die **einzige** solche Person
und das Wort ein Einzelwort, steht die Zuordnung in `auto.json` (Stufe A). Beispiel: »Schwager« 1896-01-02 → Markus Hajek
(Ehemann der Schwester Gisela).

## Beispiele aus dem Korpus

- `entry__1894-05-16.xml`: »wir vier« = Schnitzler, Richard Beer-Hofmann, Salten, Hofmannsthal; drei verschachtelte
  implied-`rs` auf demselben Wort, Schnitzler selbst bleibt unmarkiert. Der Helfer liest so etwas als vorhanden und ändert nichts.
- `entry__1920-07-16.xml`: »ich gehe dann mit ihm und seiner Frau …« (Dir. Stern); der Index nennt `pmb340592` als implied,
  ein Auslöser `besitz` bekommt ihn als Vorschlag.
- `entry__1922-07-22.xml`: `<rs>Hr. Frau Tels</rs>` ohne `ref`; der Index nennt beide Personen als normale Refs:
  Mehrfach-`ref`, kein implied.
- `entry__1903-09-13.xml`: »Georg Hirschfeld und Frau«: Elly Petersen (pmb9233, 12 gemeinsame Tage ±3 Jahre) schlägt
  Emilie Hirschfeld (0 Tage) deutlich.
- `entry__1903-09-02.xml`: »Hajeks« (Markus Hajek, Schnitzlers Schwager): Gisela Hajek (pmb2461) ist die Ehefrau.

## Was du nicht tust

- Keine Kinder, Geschwister oder Gruppen automatisch erfinden (Version 1: nur Ehepartner und die einzelnen Folgewörter).
- Nichts raten, wenn der Kandidat nur denselben Nachnamen hat und Lebensdaten oder Ko-Erwähnung dagegen sprechen.
- Implizite Personen nicht in Durchgang A ausführen: Erst müssen die Köpfe ausgezeichnet sein.
