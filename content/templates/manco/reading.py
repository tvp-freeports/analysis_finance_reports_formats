"""Come una riga dichiara la società di gestione, e quale delle due si tiene.

`R23` mette qui tutto ciò che è interpretazione del testo: il `pdf_extract` consegna **la riga**, e
sta al `text_filter` dire quale pezzo di quella riga è il nome. Il motore fin qui prendeva la riga
intera — `TextFilterManagmentCompanyStandard` — che è la cosa giusta dove l'etichetta sta **sopra**
il valore, e la cosa sbagliata dove i due stanno sulla **stessa riga** o dentro una frase di prosa.

# Il nome sta fra due espressioni fisse

Quattro formati scrivono il nome dentro una riga più larga di lui, e le quattro forme sono la stessa
cosa con due parametri diversi:

| come la riga scrive il nome | lettore | misurato su |
|---|---|---|
| l'etichetta apre la riga e il nome è il resto — nella testata di **ogni** pagina | `Between(after=…)` | ANIMA_SGR-IT24 D1 p3 |
| il nome apre la riga e una parentesi lo chiude | `Between(before=r"\\(")` | EURIZON-EN21 p7 |
| il nome sta **in mezzo** a una frase di prosa | `Between(after=…, before=…)` | FIDEURAM-EN23 p67 |
| il nome viene dopo una parola e finisce alla virgola | `Between(after="gestione", before=",")` | EURIZON-IT24 D1 p7 |

`after` e `before` sono **frammenti di espressione regolare**, non testo da cercare alla lettera: la
riga di FIDEURAM-EN23 si chiude su `(the “Management Company”)`, e quella parentesi va protetta.
Nessuno dei due è obbligatorio — `after` assente vuol dire *dall'inizio della riga*, `before`
assente *fino alla fine*.

# La qualificazione temporale — `U6`

Un bilancio d'esercizio in cui la società è cambiata **nomina tutt'e due** le società, ciascuna col
periodo fra parentesi, e la riga da estrarre è una sola: quella in carica **alla data di chiusura**.

EURIZON-EN21 p7 lo scrive così, sotto l'etichetta `Management Company:`:

```
Pramerica Management Company S.A. (until June 30, 2021)
37/A, Avenue J.F. Kennedy
L-1855 Luxembourg
Eurizon Capital S.A. (since July 1, 2021)
```

[`most_recent`][manco.reading.most_recent] tiene la seconda. Le due righe d'indirizzo non portano
nessuna qualificazione e non sono candidate: è la qualificazione stessa a fare da filtro, e non la
geometria, perché un indirizzo sta sotto il suo nome esattamente come ci sta il nome successivo.
"""

import re
from dataclasses import dataclass

from freeports import log
from freeports.utils.deserialize import to_date_with_en_month


@dataclass(frozen=True)
class Between:
    """Il nome è il pezzo di riga fra due espressioni fisse.

    Restituisce `None` quando la riga non ha la forma attesa: chi chiama decide se è un'altra riga
    della stessa sezione — un indirizzo, per esempio — o la pagina sbagliata.
    """

    after: str = ""
    before: str = ""

    def __call__(self, text):
        found = self._pattern().search(text)
        return found.group(1).strip() if found else None

    def _pattern(self):
        head = f"(?:{self.after})\\s*" if self.after else ""
        tail = f"(?={self.before})" if self.before else r"\s*$"
        return re.compile(f"{head}(.+?){tail}")


def first(texts):
    """Il caso normale: la pagina dichiara **una** società, e quella si prende."""
    return texts[0] if texts else None


_QUALIFICATION = re.compile(
    r"\(\s*(?P<verb>until|till|since|from|fino al|dal)\s+(?P<when>[^)]+?)\s*\)",
    re.IGNORECASE,
)

_EN_DATE = re.compile(r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})\s*,?\s*(?P<year>\d{4})$")

_OPEN_ENDED = {"until", "till", "fino al"}
"""I verbi che chiudono un periodo invece di aprirlo.

`since July 1, 2021` dice *da quel giorno in poi*, e quindi alla chiusura d'esercizio quella società
c'era ancora; `until June 30, 2021` dice il contrario. Quando le righe portano tutte un `until` — il
caso di un documento che nomina solo società uscenti — si tiene comunque **l'ultima a uscire**, che
è la più vicina alla chiusura, e l'alternativa sarebbe non estrarre niente.
"""


def _when(text):
    """La data della qualificazione, e `None` se la riga non ne porta nessuna."""
    found = _QUALIFICATION.search(text)
    if not found:
        return None
    written = found.group("when").strip()
    english = _EN_DATE.match(written)
    if english:
        written = f"{english.group('day')} {english.group('month')} {english.group('year')}"
    try:
        return found.group("verb").lower(), to_date_with_en_month(written)
    except ValueError:
        # La parentesi c'era ma non conteneva una data: non è una qualificazione temporale, ed è
        # un'informazione che non sappiamo leggere, non una riga da scartare in silenzio (`R25`).
        log.warn(f"a parenthesis next to a management company did not carry a date: {written!r}")
        return None


def most_recent(texts):
    """`U6` — di più società dichiarate col loro periodo, quella **in carica alla chiusura**.

    Le righe senza qualificazione non concorrono: se non ce n'è nessuna con la parentesi, vuol dire
    che la società è una sola e si ricade su [`first`][manco.reading.first].
    """
    qualified = [(text, _when(text)) for text in texts]
    qualified = [(text, when) for text, when in qualified if when is not None]
    if not qualified:
        return first(texts)

    def closeness(entry):
        _, (verb, when) = entry
        # Un periodo aperto batte un periodo chiuso a parità di data: chi è entrato il 1º luglio
        # c'era alla chiusura, chi è uscito il 30 giugno no.
        return (when, verb not in _OPEN_ENDED)

    chosen, (verb, when) = max(qualified, key=closeness)
    if len(qualified) > 1:
        log.info(
            f"the report names {len(qualified)} management companies: "
            f"kept the one in charge at closing ({verb} {when})"
        )
    return chosen


__all__ = ["Between", "first", "most_recent"]
