"""EURIZON-EN21: la società di gestione, e le due che il bilancio nomina.

`MC-4`. Il 2021 è l'anno in cui Pramerica è diventata Eurizon, e il prospetto `Management and
Administration` di pagina 7 nomina **tutt'e due** le società, ciascuna col suo periodo fra
parentesi:

```
Management Company:
Pramerica Management Company S.A. (until June 30, 2021)
37/A, Avenue J.F. Kennedy
L-1855 Luxembourg
Eurizon Capital S.A. (since July 1, 2021)
```

Si estrae **quella in carica alla chiusura**, ed è la regola `U6` del template `manco`. Le due righe
d'indirizzo non concorrono: a dividerle dai nomi non è la geometria — un indirizzo sta sotto il suo
nome esattamente come ci sta il nome successivo — ma la parentesi, che solo i nomi portano.
"""

from enum import Enum, auto

from freeports.core import PdfBlock, Pipeline
from freeports.utils.pdf_extract import (
    PdfLineSelection,
    get_groups,
    pdflines_from_pagedict,
)

# La `manco` e' configurazione: l'etichetta, il `reach` che e' solo il permesso di arrivare in
# fondo alla sezione, e lo `stop` in grassetto che la chiude stanno in `args/pdf_extract.yaml`.


# ----------------------------------------------------------------------------------------------
# `C18`: i gestori degli investimenti, su due pagine e tre sezioni
# ----------------------------------------------------------------------------------------------
_SECTION_HEADING = PdfLineSelection.font("arialmt-bold")

_RIGHT_COLUMN = 300.0
"""L'ascissa che divide le due colonne del prospetto: a sinistra 27.9, a destra 302.1.

Serve due volte. Una sezione si chiude sulla **prossima intestazione della sua colonna**, e
`Investment Managers:` sta in fondo alla colonna di destra di p7 mentre `Management Company:` sta
sotto, a sinistra: senza il confine la sezione finirebbe li', e PGIM e Jennison resterebbero fuori.
E il corpo e' la sua colonna e non l'altra, o il gestore si prenderebbe l'indirizzo dei revisori.
"""

_ENTRY_GAP = 15.0
"""Lo stacco oltre il quale due righe sono due paragrafi diversi.

Misurato sulle due pagine: 11 punti fra due righe dello stesso paragrafo — nome, indirizzo, citta' —
e 21 fra l'ultima riga di un paragrafo e la prima del prossimo. Quindici sta in mezzo con margine da
tutt'e due le parti.

Il paragrafo e' l'unita' che serve perche' **non c'e' nessuna tipografia** che distingua un nome dal
suo indirizzo: tutto il prospetto e' arialmt 8.98. Il nome e' la prima riga del paragrafo, e le
altre sono l'indirizzo, che nessuno chiede.
"""

_PAGE_FOOT = 800.0
"""L'ordinata sotto la quale non c'e' piu' prospetto, ma il numero di pagina.

Serve perche' le sezioni dei gestori di p7 arrivano al piede della colonna — l'ultima riga chiude a
783.6 — e il numero di pagina sta a 823.4, **rientrato** a 559.9: senza il pavimento sarebbe una
voce dell'elenco dei comparti, e l'ultimo gestore risulterebbe gestore di un fondo chiamato `7`.
"""

_LIST_INTRO = ("For the following sub-fund", "For all sub-funds")
"""Le frasi che aprono una specificazione, e che non sono nomi di nessuno.

`For the following sub-fund:` / `For the following sub-funds:` apre l'elenco dei comparti; `For all
sub-funds except the sub-fund mentioned below.` dice l'opposto — *tutti tranne quelli che gli altri
si prendono* — che e' esattamente il residuo di `R15`, cioe' una dichiarazione **senza** comparti.
Nei due casi la frase non deve diventare un nome, e per questo porta il tipo di blocco delle righe
secondarie.
"""


class TipoBlocco(Enum):
    """I tre ruoli che una riga di questo prospetto puo' avere."""

    MANAGER = auto()
    NOTE = auto()
    FUND = auto()


def _kind(line, indent):
    """Il ruolo della riga: un comparto dell'elenco, una frase d'apertura, o il resto."""
    if line.bbox[0] >= indent:
        return TipoBlocco.FUND.name
    if line.text.strip().startswith(_LIST_INTRO):
        return TipoBlocco.NOTE.name
    return TipoBlocco.MANAGER.name


def _managers_section(page, heading, left, indent):
    """I paragrafi di una sezione di gestori, numerati, ciascuna riga col suo ruolo.

    `left` dice in quale colonna sta la sezione e `indent` da quale ascissa una riga e' una voce
    dell'elenco dei comparti: su p7 l'elenco rientra a 320 contro i 302.1 della colonna, su p8 a
    45.8 contro i 27.9.
    """
    lines = pdflines_from_pagedict(page)
    opening = heading.select(lines)
    if not opening:
        return []
    top = opening[0].bbox[1]
    column = PdfLineSelection.area(left, 0.0, left + 1e6, 1e6)
    below = [
        line
        for line in (_SECTION_HEADING & column).select(lines)
        if line.bbox[1] > top
    ]
    bottom = min((line.bbox[1] for line in below), default=1e6)
    body = [
        line
        for line in column.select(lines)
        if top < line.bbox[1] < min(bottom, _PAGE_FOOT) and line.text.strip()
    ]
    if not body:
        return []
    body.sort(key=lambda line: (line.bbox[1], line.bbox[0]))
    groups = get_groups(body, _ENTRY_GAP, True)
    return [
        PdfBlock(_kind(line, indent), {"group": group}, line.text)
        for line, group in zip(body, groups)
    ]


def pdf_extract_inv_managers(page):
    """p7: `Investment Managers:`, in fondo alla colonna di destra."""
    return _managers_section(
        page,
        _SECTION_HEADING & PdfLineSelection.text("^Investment Managers:"),
        _RIGHT_COLUMN,
        320.0,
    )


def pdf_extract_inv_managers_continued(page):
    """p8: le due sezioni dei sub-gestori, appiattite (`R22`).

    Due letture e non una, perche' sono due intestazioni e ciascuna chiude la sezione dell'altra.
    Che siano sub- o sub-sub- non e' un dato d'uscita: il legame gestore-comparto lo e'.
    """
    blocks = _managers_section(
        page,
        _SECTION_HEADING & PdfLineSelection.text("^Sub-Investment Manager:"),
        0.0,
        45.0,
    )
    blocks.extend(
        _managers_section(
            page,
            _SECTION_HEADING & PdfLineSelection.text("^Sub-Investment Managers/"),
            0.0,
            45.0,
        )
    )
    return blocks


# I due `text_filter` stanno nel livello `semistructured`. La specificazione e' l'elenco rientrato,
# che il `pdf_extract` ha gia' separato in un tipo di blocco suo — quindi `item_prefix: ""`, ogni
# riga e' una voce — e la qualificazione temporale sta **in coda al nome**: `strip` la toglie dal
# nome d'uscita (`Pramerica SGR S.p.A. (until June 30, 2021)` diventa `Pramerica SGR S.p.A.`) e
# `retired` la riconosce prima che `strip` la tolga. Si estrae solo chi e' in carica alla chiusura,
# quindi `Pramerica SGR S.p.A.` e `Prudential International Investments Advisers, LLC` non diventano
# righe, e i comparti che rivendicano tornano nel residuo. Il nome di Prudential va a capo dentro la
# parentesi (`… LLC (until June 30,` / `2021)`), e per questo l'espressione non pretende la
# parentesi chiusa. Lo `strip` dell'elenco toglie l'ombrello: il prospetto scrive `Eurizon AM Sicav
# – USA Equity`, gli investimenti scrivono `USA EQUITY`, e `R24` vuole il secondo.
#
# p8 lo schedule la processa **per prima** e non chiude niente: i due sub-gestori che nomina sono
# l'uno uscente e l'altro in carica, e nessuno dei due e' dichiarato *senza* comparti. Il residuo lo
# decide p7, dove sta `Eurizon Capital SGR S.p.A. (since July 1, 2021)` con la sua `For all
# sub-funds except the sub-fund mentioned below.` — una specificazione che non nomina niente — e i
# comparti di p8 le arrivano da `already_assigned`.
pipelines = {
    # I gestori stanno sulla stessa pagina della societa' di gestione, quindi la pipeline e'
    # un'altra e la classe di pagina e' la sua: il legame lo fa `mapping.csv`.
    "inv_managers": Pipeline(pdf_extract=pdf_extract_inv_managers),
    "inv_managers_continued": Pipeline(pdf_extract=pdf_extract_inv_managers_continued),
}
