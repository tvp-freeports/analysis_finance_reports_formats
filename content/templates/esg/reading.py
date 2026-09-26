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
| una **tabella**: il nome sopra, una riga per serie, una colonna per esercizio | `DatedRows` | AMUNDI-EN24 p778 |
| **`etichetta: valore`**, una voce per riga, e la stessa misura scritta anche per l'indice | `LabelledPairs` | UBS-EN23 p140 |

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


@dataclass(frozen=True)
class DatedRows:
    """L'indicatore è una **tabella**: il nome sopra, una riga per serie, una colonna per esercizio.

    AMUNDI-EN24 p778 scrive, sotto il nome `Weighted Average Carbon Intensity`, due righe — quella
    del prodotto e quella dell'indice di riferimento — e su ciascuna due valori, uno per esercizio:

    ```
                                   28/06/24   30/06/23
    Weighted Average Carbon Intensity
        Great European Models SRI        71         72
        Stoxx 600                        83        101
    ```

    Il valore che serve è **all'incrocio** fra la riga del prodotto e la colonna dell'esercizio in
    corso, e le altre tre celle non si estraggono: quella dell'indice non è un dato del comparto, e
    quella dell'esercizio precedente non si estrae per `R5`.

    Il lettore non guarda la pagina: legge i metadati che il `pdf_extract` ha scritto — quale
    indicatore, quale serie, quale colonna — perché quello è geometria e sta di là (`R23`). Qui
    stanno le due scelte che sono interpretazione: **quale serie** e **quale colonna**.

    - `series` — l'indice della serie da tenere. `0` è quella del prodotto, che è la prima che la
      tabella scrive; le altre sono indici di riferimento;
    - `column` — l'indice della colonna. Il `pdf_extract` le numera **dalla più recente**, che è
      ciò che `R5` chiede di tenere, quindi `0`;
    - `number` — che forma ha un valore. Una cella che non è un numero non è un indicatore (`R11`),
      e su questa tabella capita: l'ultima riga di ogni blocco è una nota di fonte.
    """

    indicator_key: str = "indicator"
    series_key: str = "series"
    column_key: str = "column"
    series: int = 0
    column: int = 0
    number: str = NUMBER

    def __call__(self, blocks):
        """Gli indicatori all'incrocio chiesto, nell'ordine in cui la tabella li scrive."""
        indicators = []
        for block in blocks:
            metadata = block.metadata
            if _index(metadata, self.series_key) != self.series:
                continue
            if _index(metadata, self.column_key) != self.column:
                continue
            value = _text(block)
            if not re.match(r"\s*(?:{})\s*$".format(self.number), value):
                continue
            name = str(metadata.get(self.indicator_key, "")).strip()
            if not name:
                continue
            indicators.append(Indicator(name.rstrip(":").strip(), value, block))
        return indicators


def _index(metadata, key):
    """Il numero scritto sotto `key`, o `None` se non c'è o non è un numero."""
    try:
        return int(metadata[key])
    except (KeyError, TypeError, ValueError):
        return None


@dataclass(frozen=True)
class LabelledPairs:
    """`<etichetta>: <valore>`, una voce per riga, e il valore è il numero che segue i due punti.

    UBS-EN23 p140 risponde alla domanda con un elenco a due livelli, e le voci che portano un dato
    sono quelle del secondo:

    ```
    o  Weighted Average Carbon Intensity (WACI) of the financial product: 26.81 tons CO₂ per …
    o  Weighted Average Carbon Intensity (WACI) of the benchmark: 38.2 tons CO₂ per …
    ```

    Ogni misura è scritta **due volte**, una per il comparto e una per il suo indice di riferimento,
    e quella dell'indice non è un dato del comparto: la distingue una frase, ed è `drop` a dirla.
    La stessa frase, al rovescio, sporca l'etichetta — `… of the financial product` non fa parte del
    nome dell'indicatore — e a togliercela è `strip`.

    - `separator` — ciò che divide l'etichetta dal valore. Si divide sul **primo**, che è quello che
      chiude l'etichetta: `For the characteristic 1:` non arriva qui perché non è una voce;
    - `drop` — le espressioni che qualificano una voce come non del prodotto;
    - `strip` — le code da togliere all'etichetta;
    - `number` — che forma ha un valore. Del testo che segue i due punti si prende **il primo
      numero**, perché l'unità di misura lo segue (`26.81 tons CO₂ per million dollars revenues`);
    - `group_key` — la chiave con cui il `pdf_extract` ha separato una voce dall'altra: una voce va
      a capo, e il valore sta sulla riga dopo l'etichetta.
    """

    separator: str = ":"
    drop: tuple = ()
    strip: tuple = ()
    number: str = NUMBER
    group_key: str = "group"

    def __call__(self, blocks):
        """Gli indicatori del prodotto, nell'ordine in cui l'elenco li scrive."""
        indicators = []
        for entry in _entries(blocks, None, self.group_key):
            text = " ".join(line for line in (_text(block) for block in entry) if line)
            if self.separator not in text:
                continue
            if any(re.search(pattern, text) for pattern in self.drop):
                continue
            name, _, tail = text.partition(self.separator)
            found = re.search(self.number, tail)
            if not found:
                continue
            for pattern in self.strip:
                name = re.sub(pattern, "", name)
            name = name.strip()
            if not name:
                continue
            indicators.append(Indicator(name, found.group(0).strip(), entry[0]))
        return indicators
