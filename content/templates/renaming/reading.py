"""`A7` — come una pagina dichiara che un comparto ha cambiato nome, o ne ha assorbito un altro.

# Che cosa cambia da un formato all'altro, e che cosa no

Il dato è sempre lo stesso — **nome vecchio, nome nuovo, data** — e a cambiare è dove la data sta
scritta e come la coppia di nomi si tiene insieme:

| come la pagina lo scrive | lettore | misurato su |
|---|---|---|
| un'**intestazione datata**, e sotto un elenco `<vecchio> into <nuovo>` | `Listed` | AMUNDI-EN24 p510 |
| una **frase per evento**, con verbo e data dentro la frase | `Sentence` | DANSKEINVEST-EN24 p351 · KAIROS-EN23 D2 p104 |
| la **sezione c'è ed è vuota**: dichiara l'assenza | nessuno — v. sotto | ARCA-IT24 D1 p6 |

La terza riga non ha un lettore, ed è il punto: una sezione che dice *«Non si segnalano eventi
rilevanti»* si legge con gli stessi due lettori, che non trovano niente e non producono niente. È
una prova positiva — la pagina è stata trovata, la sezione aperta, e il risultato vuoto è il dato —
e per questo il test si scrive lo stesso.

# Le sezioni sorelle, che sono il vero tranello

AMUNDI-EN24 p510 mette una sotto l'altra tre sezioni con la stessa tipografia: i comparti
**lanciati**, quelli **ridenominati**, quelli **liquidati**. Solo la seconda porta un dato. `Listed`
le distingue senza guardare i nomi delle sezioni una per una: un'intestazione che apre uno degli
schemi dichiarati **apre** uno scopo con la sua data, qualunque altra riga che non porti il
connettore lo **chiude**. Così una sezione nuova che nessuno ha previsto non entra per sbaglio, che
è il comportamento che si vuole quando il documento cambia da un anno all'altro.
"""

import re
from dataclasses import dataclass

from freeports import log

NOTE_MARKS = "*†‡¹²³⁴⁵"
"""I richiami di nota che si tolgono dal nome di un comparto (`R16`, `U3`)."""

DATE = r"\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/.]\d{1,2}[/.]\d{4}"
"""Le tre forme in cui i documenti della raccolta scrivono una data dentro una frase.

Non è un convertitore: qui si **trova** la data, e a leggerla è il `deserialize`, che è il solo
segmento a cui `R23` lascia i casting.
"""


@dataclass(frozen=True)
class Change:
    """Un cambio, come la pagina lo dichiara: due nomi, una data, e di che cambio si tratta."""

    old_name: str
    current_name: str
    when: str
    merge: bool = False
    block: object = None


@dataclass(frozen=True)
class Listed:
    """Un'intestazione datata apre un elenco, e ogni riga dell'elenco è un cambio.

    - `renamed` e `merged` — gli schemi che riconoscono le due intestazioni. Sono due elenchi
      perché il dato d'uscita è diverso: una ridenominazione e una fusione sono due righe di
      `funds_change_name.csv` con due verbi diversi;
    - `connector` — ciò che divide il nome vecchio dal nuovo sulla riga. Una riga che non lo porta
      **chiude** lo scopo aperto, ed è così che le sezioni sorelle restano fuori;
    - `strip` — ciò che va tolto dai due nomi perché coincidano con quelli degli investimenti
      (`R24`): un prefisso d'ombrello, di solito;
    - `date` — dove la data sta dentro l'intestazione. L'intestazione la porta sempre: se non la
      porta, l'elenco non si legge e lo si dice, perché una ridenominazione senza data non è una
      riga che si possa scrivere.
    """

    renamed: tuple = ()
    merged: tuple = ()
    connector: str = " into "
    date: str = DATE
    date_intro: str = r"\s+(?:on|il|dal|in data|a far data dal)$"
    strip: tuple = ()
    note_marks: str = NOTE_MARKS

    def __call__(self, blocks):
        """I cambi letti dai blocchi, nell'ordine in cui la pagina li scrive."""
        changes = []
        scope = None
        for block in blocks:
            text = _text(block)
            if not text:
                continue
            if self.connector in text and scope is not None:
                change = self._change(text, scope, block)
                if change is not None:
                    changes.append(change)
                continue
            scope = self._opens(text)
        return changes

    def _change(self, text, scope, block):
        """Il cambio dichiarato da una riga dell'elenco, con la data sua o quella dell'elenco."""
        when, merge = scope
        own = re.search(self.date, text)
        if own is not None:
            # La data sulla riga vince su quella dell'intestazione, e va tolta dal nome: su
            # AMUNDI-EN24 p510 l'elenco delle fusioni la porta riga per riga, e lasciandocela il
            # comparto si chiamerebbe `… ESG Improvers on 23 February 2024`.
            when = own.group(0)
            text = re.sub(self.date_intro, "", text[: own.start()].rstrip())
        if when is None:
            log.warn(
                "'{}' declares a fund name change with no date, neither on the line nor on the "
                "heading above it: the line is not read".format(text)
            )
            return None
        old, current = text.split(self.connector, 1)
        return Change(
            _clean(old, self.note_marks, self.strip),
            _clean(current, self.note_marks, self.strip),
            when,
            merge=merge,
            block=block,
        )

    def _opens(self, text):
        """La data e il tipo di cambio se questa riga apre un elenco, altrimenti `None`.

        Un'intestazione **senza** data apre lo stesso: vuol dire che la data sta su ogni riga, ed
        è la forma in cui AMUNDI-EN24 scrive le fusioni sotto l'elenco delle ridenominazioni, che
        invece la data ce l'ha una sola volta.
        """
        for patterns, merge in ((self.renamed, False), (self.merged, True)):
            for pattern in patterns:
                if not re.search(pattern, text):
                    continue
                when = re.search(self.date, text)
                return (when.group(0) if when else None), merge
        return None


@dataclass(frozen=True)
class Sentence:
    """Una frase per evento, con i due nomi e la data dentro di sé.

    `renamed` e `merged` sono schemi con tre gruppi nominati — `old`, `current`, `when` — e si
    provano su **tutto** il testo, non solo all'inizio: una stessa frase può dichiarare più di un
    cambio (EURIZON-IT24 D4 p14 ne dichiara due), e cercarne uno solo ne perderebbe metà.

    Il testo su cui si cerca è quello dei blocchi **riuniti**, perché una frase va a capo: `groups`
    dice quale chiave dei metadati separa un paragrafo dal successivo, e senza quella chiave i
    blocchi si riuniscono tutti in uno.
    """

    renamed: tuple = ()
    merged: tuple = ()
    group_key: str = "group"
    strip: tuple = ()
    note_marks: str = NOTE_MARKS

    def __call__(self, blocks):
        """I cambi letti dalle frasi, nell'ordine in cui la pagina le scrive."""
        changes = []
        for entry in _entries(blocks, self.group_key):
            text = " ".join(line for line in (_text(block) for block in entry) if line)
            for patterns, merge in ((self.renamed, False), (self.merged, True)):
                for pattern in patterns:
                    for found in re.finditer(pattern, text):
                        changes.append(
                            Change(
                                _clean(found.group("old"), self.note_marks, self.strip),
                                _clean(found.group("current"), self.note_marks, self.strip),
                                found.group("when").strip(),
                                merge=merge,
                                block=entry[0],
                            )
                        )
        return changes


def _entries(blocks, group_key):
    """I blocchi divisi in paragrafi: per gruppo se i metadati lo dicono, altrimenti tutti in uno."""
    entries = []
    previous = object()
    for block in blocks:
        group = _group_of(block, group_key)
        if not entries or (group is not None and group != previous):
            entries.append([])
        entries[-1].append(block)
        previous = group
    return entries


def _group_of(block, group_key):
    """Il gruppo del blocco, o `None` se il `pdf_extract` non ne ha messo uno."""
    try:
        return block.metadata[group_key]
    except (KeyError, TypeError, IndexError):
        return None


def _clean(text, note_marks, strip=()):
    """Il nome come gli investimenti lo scrivono: senza punto, senza richiamo, senza ombrello.

    `strip` toglie ciò che la sezione scrive e gli investimenti no — su AMUNDI-EN24 il prefisso
    `Amundi Funds `, che il modulo SFDR dello stesso formato già si toglie per la stessa ragione.
    È `R24`: due modi di scrivere lo stesso comparto sono lo stesso comparto solo se le due
    scritture arrivano alla stessa forma.
    """
    name = text.strip().rstrip(".").strip()
    for pattern in strip:
        name = re.sub(pattern, "", name).strip()
    return name.rstrip(note_marks).strip() if note_marks else name


def _text(block):
    """Il testo del blocco, senza gli spazi che la riga del PDF si porta dietro."""
    return str(block.content).strip()
