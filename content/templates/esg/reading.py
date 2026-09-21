"""`A6` — gli indicatori ESG: la coppia *nome → valore*, in qualunque forma la pagina la scriva.

# Che cosa è un indicatore, e che cosa non lo è

Il modulo periodico europeo chiede *«Come hanno funzionato gli indicatori di sostenibilità?»* e i
bilanci rispondono in tre modi diversi: una **tabella** di coppie, una **frase che comincia col
numero**, o **soltanto prosa**. Il terzo caso non è un buco: `R11` dice che dove non c'è un numero
non c'è un indicatore, e non estrarre niente è la lettura giusta — ANIMA_SGR-IT24 p1726 risponde
con quattro righe di discorso e zero misure.

Da qui viene la regola che tiene insieme i tre casi: **un indicatore senza numero non esiste**. I
lettori qui sotto lasciano cadere in silenzio tutto ciò che un numero non ce l'ha, ed è per questo
che la pagina di sola prosa non ha bisogno di nessun ramo suo.

| come la pagina scrive l'indicatore | lettore | misurato su |
|---|---|---|
| una frase numerata che **comincia col valore** | `LeadingNumber` | FINECO-EN23@IR D1 p894 |
| **solo prosa**, nessun numero | `LeadingNumber`, che non trova niente | ANIMA_SGR-IT24 D1 p1726 |

# Il tranello comune a tutti i moduli

La colonna di glossario del modello europeo sta a `x≈4.8` e in ordine di lettura per sola ordinata
**si intreccia** col corpo del testo. La sezione va quindi ritagliata per ascissa nel `pdf_extract`,
che è dove `R23` mette la geometria; qui si riceve già il solo corpo.
"""

import re
from dataclasses import dataclass

NUMBER = r"[-+]?\d{1,3}(?:[.,]\d+)?\s*%|[-+]?\d+(?:[.,]\d+)?"
"""Il valore di un indicatore: una percentuale, o un numero puro.

La percentuale va provata per prima, o `93.07% of the Fund…` darebbe `93.07` e lascerebbe il segno
di percento nel nome — che è la stessa cosa scritta in due unità diverse.
"""

MARKER = r"^\d+[.)]$"
"""Il richiamo che apre una voce dell'elenco: `1.`, `2.`, in un blocco tutto suo."""


@dataclass(frozen=True)
class Indicator:
    """Un indicatore come la pagina lo scrive: un nome, un valore, e da dove viene."""

    name: str
    value: str
    block: object = None


@dataclass(frozen=True)
class LeadingNumber:
    """La frase **comincia col numero**, e il nome è il resto della frase.

    FINECO-EN23@IR p894 elenca sei voci numerate, e ciascuna dice prima quanto e poi di che cosa:
    *«93.07% of the Fund was invested in securities of issuers with favourable ESG characteristics
    …»*. Il valore è il numero in testa, il nome è la frase che lo segue.

    - `marker` — il richiamo che apre una voce quando la pagina lo scrive in un blocco a sé (`1.`).
      Dove non c'è, le voci si separano per gruppo, e dove non c'è nemmeno il gruppo la sezione è
      una voce sola;
    - `number` — che forma ha un valore. Una voce che non comincia con un numero **non è un
      indicatore** e si lascia cadere: è `R11`, ed è ciò che rende la pagina di sola prosa un caso
      già coperto invece che un'eccezione;
    - `max_name` — quanti caratteri del nome si tengono. Alcune frasi continuano per due righe di
      precisazioni che non fanno parte del nome; a `0` si tiene tutto.
    """

    marker: str = MARKER
    number: str = NUMBER
    group_key: str = "group"
    max_name: int = 0

    def __call__(self, blocks):
        """Gli indicatori letti dai blocchi, nell'ordine in cui la pagina li scrive."""
        indicators = []
        for entry in _entries(blocks, self.marker, self.group_key):
            text = " ".join(line for line in (_text(block) for block in entry) if line)
            found = re.match(r"\s*(?P<value>{})\s*(?P<name>.+)".format(self.number), text)
            if not found:
                continue
            name = found.group("name").strip()
            if self.max_name and len(name) > self.max_name:
                name = name[: self.max_name].rstrip()
            indicators.append(
                Indicator(name.rstrip(".").strip(), found.group("value").strip(), entry[0])
            )
        return indicators


def _entries(blocks, marker, group_key):
    """I blocchi divisi in voci: sul richiamo se c'è, sul gruppo se no, tutti insieme altrimenti."""
    entries = []
    previous = object()
    for block in blocks:
        text = _text(block)
        if marker and re.match(marker, text):
            entries.append([])
            continue
        group = _group_of(block, group_key)
        if not entries or (group is not None and group != previous):
            entries.append([])
        entries[-1].append(block)
        previous = group
    return [entry for entry in entries if entry]


def _group_of(block, group_key):
    """Il gruppo del blocco, o `None` se il `pdf_extract` non ne ha messo uno."""
    try:
        return block.metadata[group_key]
    except (KeyError, TypeError, IndexError):
        return None


def _text(block):
    """Il testo del blocco, senza gli spazi che la riga del PDF si porta dietro."""
    return str(block.content).strip()
