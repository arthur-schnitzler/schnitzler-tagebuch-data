# Bestätigte Haushalte

Von der Redaktion bestätigte Paare (Kopf → Partner, mit Zeitraum). Der Scan nutzt diese Zeilen, um Ehepartner-Kandidaten als
`Haushalt bestätigt` zu markieren und vorzuschlagen; sie gehen allen anderen Belegen vor, auch den PMB-Relationen (diese sind
in `data/verwandtschaft-relationen.csv` gekürzt abgelegt und decken die meisten Paare schon ab). Hier gehört nur hin, was im
PMB fehlt oder falsch ist, und nur, was die Redaktion bestätigt hat: Der Skill trägt nichts selbst ein.

## Format

Eine Zeile je Beziehung, in beliebiger Reihenfolge, außerhalb von Codeblöcken:

`pmbKOPF -> pmbPARTNER | von .. bis | Beziehung | Anmerkung`

- `von`/`bis`: `YYYY`, `YYYY-MM-DD` oder leer (offen). Die Beziehung gilt auch umgekehrt (Partner → Kopf).
- Beziehung: ein Wort (`Ehefrau`, `Ehemann`).
- Eine Zeile pro Ehe; bei Wiederverheiratung zwei Zeilen mit getrenntem Zeitraum.

Beispiel (mit `#` auskommentiert, wird nicht gelesen):

```
# pmb11740 -> pmb2292 | 1901-06-08 .. | Ehefrau | Hofmannsthal – Gerty (Datum von der Redaktion zu bestätigen)
```

## Bestätigte Einträge

(noch keine)
