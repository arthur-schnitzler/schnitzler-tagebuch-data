# Konventionen der Auszeichnung (mit Belegen aus dem Korpus)

Alle Beispiele stammen aus `editions/`. Der Helfer erzeugt diese Muster selbst; die Tabelle hilft dir, Entscheidungen
so zu formulieren, dass das Ergebnis der Edition entspricht.

## Auszeichnungsarten

| Art | Wofür | Beispiel |
|---|---|---|
| `type="person"` | Person mit Name oder Namensteil | `<rs type="person" xml:id="pNt_10250" ref="#pmb2378"><forename>Mz.</forename> <surname>Rh.</surname></rs>` |
| `type="allusively"` | Verwandtschafts-/Rollenwort ohne Namen | `<rs type="allusively" xml:id="rst_00388" ref="#pmb12701">Mama</rs>` (vor dem Abgleich ohne `ref`) |
| `type="person" subtype="implied"` | mitgemeinte Person | `<rs type="person" xml:id="pNt_94475" ref="#pmb9233" subtype="implied">Frau</rs>` |

`persName` im body (476 ältere Stellen, v. a. 1880) zählt als ausgezeichnet und bleibt unberührt.

## Fälle und was der Helfer daraus macht

| Fall | Operation | Ergebnis |
|---|---|---|
| `rs type="person"` ohne `ref`, Index nennt die Person | `set_ref` | ` ref="#pmbN"` wird hinter `xml:id` angehängt (Attributfolge `type, xml:id, ref`, die Mehrheit im Korpus mit 82.314×) |
| `rs type="allusively"` ohne `ref` (Mama, Vater, Kinder, Hofrätin, Kaiser) | `set_ref` | gleiches; `type` und `rst_`-ID bleiben; für »Kinder«, »Eltern« Mehrfach-`ref` |
| Name im Text noch unmarkiert | `wrap` (`typ: person`) | neues `<rs type="person" xml:id="pNt_…" ref="#pmbN">` um genau das Token, mit Kindelementen |
| Verwandtschaftswort unmarkiert, Index belegt es | `wrap` (`typ: allusively`) | neues `<rs type="allusively" xml:id="rst_…" ref="#pmbN">Wort</rs>`, reiner Text |
| mehrere Personen in einem rs, namentlich genannt (»Hr. Frau Tels«) | `set_ref` mit Liste | `ref="#pmb25918 #pmb25921"` wie 1903-10-19 (»Gottliebs«) und 1881-03-22 (»Z.s«) |
| Mitgemeinte Person hinter einem Wort (»Hofmannsthal und Frau«) | `implied` mit `anker` | `<rs … ref="#pmb2292" subtype="implied">Frau</rs>` |
| Familienform eines ausgezeichneten Namens (»Beer-Hofmanns«) | `implied` mit `um_rs` | der implied-`rs` **umschließt** den bestehenden `rs` des Haushaltsvorstands (wie `entry__1894-05-16.xml`) |
| Mitgemeinte Person ohne PMB-Eintrag | `implied` mit `neu` | `ref="#implied-person_N"`, Zeile in `indices/implied-persons.txt`, Index `<ref ana="implied">` |

## Kindelemente nach Korpuskonvention

- Vorname → `<forename>`, Nachname → `<surname>`, Anrede/Titel → `<roleName>` (Frau, Herr, Frl., Hr., Dr., Prof., Hofr., Dir.).
- Partikel (v., von) gehören zum Vornamen: `<forename>Theodor v.</forename> <surname>Sosnosky</surname>`.
- Ein Spitzname allein ist `<forename>` (»Dilly«, »Minnie«), ein einzelner Name, der PMB-Nachname ist, `<surname>`.
- Abkürzungen behalten ihren Punkt (`Mz.`, `Rh.`, `Sigm.`), der Satzpunkt gehört nicht zum Anker.
- Verwandtschafts- und Gruppenwörter bleiben **reiner Text** (»Mama«, »Frau« im implied-rs, »vier«).
- Zerlegung selbst festlegen: `teile: ["roleName:Frau", "surname:Reich"]` in der Entscheidung (Reihenfolge wie im Text).

## Kennungen

- Personen-`rs` (auch implied): `xml:id="pNt_NNNNN"`; allusively: `rst_NNNNN`. Jeweils globales Maximum + 1, beim Start von
  `apply` aus dem Korpus bestimmt (derzeit pNt bis 94472, rst bis 2202). Es gibt 18 alte doppelte `xml:id`s im Korpus; sie
  sind Baseline, nicht dein Problem.
- Attributfolge neuer Elemente: `type`, `xml:id`, `ref`, `subtype` (z. B. `type="person" xml:id="…" ref="#pmb2292" subtype="implied"`).

## Wo nichts ausgezeichnet wird

- Nicht in anderen `rs` (work, place, org, institution) und nicht in `date`, `fw`, `bibl`, `persName`.
- Nicht über Elementgrenzen (`<pb/>` oder `<fw>` mitten im Namen): der Helfer lehnt ab, du meldest die Stelle im Bericht.
- Nicht Arthur Schnitzler selbst (pmb2121 kommt im Index nie vor) und nicht Gattungswörter.
- Pronomen (»er«, »sie«) werden nie ausgezeichnet.

## Index (`indices/index_person_day.xml`)

```xml
<item target="1920-07-16">
   <ref>pmb25462</ref>
   <ref ana="implied">pmb340592</ref>
</item>
```

- Der Index ist chronologisch; neue Tage werden an der richtigen Stelle eingefügt, neue Refs ans Ende des Items.
- `ana="implied"` kennzeichnet mitgemeinte Personen (Konvention der Redaktion, Commits »Implied«). Der Helfer ergänzt den Index
  nur bei Aufgabe 3 (implied); Aufgabe 2 ändert ihn nicht, weil die Personen dort schon stehen.
- Refs in der Form `person_N` sind Altlasten (6 im Index); sie werden nur gemeldet.

## `indices/implied-persons.txt`

Eine Zeile je Person: `implied-person_N|?? [Beziehung von Vorname Nachname]`. Die Beschreibung ist der Schlüssel (gleiche
Beschreibung = gleiche Nummer) und folgt der Form der PMB-Platzhalter (`?? [Russischer Verlobter von Marie Elsinger]`). Die
Redaktion legt die Person im PMB an und ersetzt später `implied-person_N` durch `pmbN` (Ersetzungslauf nach dem Muster von
`replace_person_with_pmb.py`).

## Personen außerhalb des Tagebuch-Registers

`indices/listperson.xml` enthält nur PMB-Personen, die die PMB dem Tagebuch zuordnet (wöchentlicher Lauf). Ehepartner und
Verwandte, die das PMB kennt, die aber nicht dazugehören, dürfen als echte pmb-ID in einem implied-`rs` stehen; `apply`
meldet sie, `pa.py verify` vermerkt sie, `pa.py register-luecken` listet sie (mit Beziehung zu einer Registerperson). Die
Redaktion nimmt sie in der PMB in die Sammlung des Tagebuchs auf; bis dahin gibt es für sie keine Personenseite.

## Folgen für die Website (zur Kenntnis)

`xslt/partials/shared.xsl` im Statik-Repo macht aus jedem `rs` mit `@ref` einen Link `<ref>.html`: allusively-`rs` verweisen
künftig auf die Personenseite, ein `#implied-person_N` ergäbe einen toten Link, und verschachtelte `rs` erzeugen
verschachtelte `<a>`. Das ist eine Folgearbeit im Statik-Repo, kein Grund, anders auszuzeichnen.
