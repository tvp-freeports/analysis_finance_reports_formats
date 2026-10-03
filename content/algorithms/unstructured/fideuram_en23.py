"""FIDEURAM-EN23: la società di gestione nella prosa di una nota, e i gestori delegati in elenco.

`MC-5`. Il prospetto non ha nessuna sezione `Management Company` e nessuna etichetta: il nome sta
dentro una frase della nota 1, `GENERAL INFORMATION` di pagina 67, fra due espressioni fisse.

```
The Fund has been created for an indefinite period and it is managed by Fideuram Asset Management
(Ireland) dac (the "Management Company").
```

Le due espressioni sono `it is managed by` e la parentesi che apre `(the "Management Company")`, e
la seconda serve **davvero**: il nome stesso ne contiene una, `(Ireland)`, quindi a fermarsi alla
prima parentesi si estrarrebbe `Fideuram Asset Management`.

# Perché l'ancora del `pdf_extract` è la frase e non l'intestazione della nota

`A2` porterebbe giù tutta la sezione, una ventina di righe di prosa, e a quel punto *quale* sia la
riga giusta tornerebbe a essere una domanda. La frase invece la pagina la scrive una volta sola —
misurato su tutte le 81 pagine del prospetto — e allora l'ancora è lei: la geometria consegna
**quella riga**, e il `text_filter` ne taglia il nome (`R23`). Le parole si ripetono nei due
segmenti perché i due lavori sono diversi, non perché uno dei due sia di troppo.
"""

import inv_managers
import manco
from freeports.core import PdfBlock, Pipeline
from freeports.interfaces.pdf_blks import OnePdfBlockType, ResultStandardExtraction
from freeports.standard_funcs.deserialize import (
    DeserializerFundStandard,
    DeserializerInvestmentsManagerStandard,
    DeserializerManagmentCompanyStandard,
)
from freeports.output import Fund
from freeports.standard_funcs.pdf_extract import (
    PdfExtractLabelledValueStandard,
    PdfExtractSectionStandard,
)
from freeports.standard_funcs.deserialize import DeserializerAssetsStandard
from freeports.standard_funcs.text_filter import TextFilterAssetsStandard
from freeports.utils.deserialize import to_int
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict
import datetime
import re

pdf_extract_manco = PdfExtractLabelledValueStandard(
    PdfLineSelection(font="arial", font_size=(7.5, 8.5), text="it is managed by"),
    ResultStandardExtraction.MANAGEMENT_COMPANY.name,
    "managment company",
)

text_filter_manco = manco.text_filter(
    manco.Between(after="it is managed by", before=r"\(the")
)

# `IM-5`, p71: tredici righe `<gestore> for <comparti>`, una sotto l'altra, sotto l'intestazione
# `Investment Manager`. Tutta la pagina e' in arial 7.98 -- intestazioni comprese -- quindi la
# sezione non si chiude sulla famiglia tipografica -- la riga **subito dopo** l'intestazione ha
# lo stesso carattere e lo stesso corpo, e la sezione si chiuderebbe vuota: `family` diventa
# allora la frase che la chiude davvero.
# Il corpo si restringe per **ascissa**, perche' le voci rientrano a `x=56,6` mentre i trattini
# dell'elenco e la prosa attorno stanno a `x=41,5`.
pdf_extract_inv_managers = PdfExtractSectionStandard(
    PdfLineSelection(text="^Investment Manager$", font="arial", font_size=(7.5, 8.5)),
    OnePdfBlockType.RELEVANT_BLOCK.name,
    "investment managers",
    family=PdfLineSelection.text("^The Management Company keeps the control"),
    body=PdfLineSelection(area=(50.0, 0.0, 600.0, 850.0)),
)

read_inv_managers = inv_managers.ConnectorLine()


def text_filter_inv_managers(pdf_blks, filter_data):
    """`R15`: il residuo e' della societa' di gestione, che pero' sta su un'altra pagina.

    Per questo la classe `manco_note` viene **prima** nello `algorithms_schedule.csv` e il suo passo
    si chiude: qui la si ritrova fra i risultati, e `assign` sa a chi dare i comparti che le
    tredici righe non nominano.
    """
    declared_manco = manco.declared(filter_data)
    assignment = inv_managers.assign(
        read_inv_managers(pdf_blks),
        inv_managers.fund_set(
            result.name for result in filter_data if isinstance(result, Fund)
        ),
        manco=declared_manco,
    )
    blocks = list(inv_managers.text_blocks(assignment))
    if declared_manco is not None and assignment.new_funds:
        # `C10`. Un comparto che **nasce qui** — perche' un gestore lo nomina e gli investimenti
        # non l'avevano visto — non ce l'ha, la societa' di gestione: quando la classe `manco`
        # e' passata quel comparto non esisteva ancora. La si ridichiara con tutti i comparti,
        # `R26`, cosi' la colonna non resta vuota: `WILLERFUNDS - PRIVATE SUITE FIDELITY USD
        # BOND` era l'unica riga di `funds.csv` di tutta la raccolta senza societa' di gestione.
        blocks.append(inv_managers.management_company_block(assignment, declared_manco))
    return blocks




# ----------------------------------------------------------------------------------------------
# Il prospetto patrimoniale, quattro comparti per pagina (`FA-8`)
# ----------------------------------------------------------------------------------------------
# Il prospetto mette **quattro comparti in colonna** e scrive ogni nome su tre o quattro righe
# sovrapposte — `WILLERFUNDS –` / `PRIVATE SUITE –` / `FIDELITY FLEXIBLE` / `SHORT DURATION` —
# quindi il nome non è una riga ma una colonna di righe, e a ricomporlo è l'appaiamento per
# ascissa di `A4`.
#
# Il passivo è scritto **fra parentesi**: è presentazione e non dato (`R31`), e il convertitore le
# toglie. Il trattino è lo zero, come su ANIMA-EN23.

_HEAD = PdfLineSelection(font="arial-bold", font_size=(6.3, 6.6))
_TOTALS = PdfLineSelection(font="arial-bold", font_size=(6.8, 7.1))

# Le due bande della testata: i nomi sopra, la valuta sulla riga sotto, stesso carattere e stesso
# corpo. Le separa l'ordinata, e il taglio va **fra** le due righe e non sulla prima: le scatole
# sono alte 6,5 punti, i nomi occupano 142,7–183,1 e la valuta 185,1–191,6, quindi a 183 l'ultima
# riga del nome resta fuori — `SWITZERLAND` e `SHORT DURATION` si perdevano così.
assets_fund_set = _HEAD & PdfLineSelection.area(180.0, 130.0, 1e6, 184.5)
assets_currency_set = _HEAD & PdfLineSelection.area(180.0, 184.5, 1e6, 197.0)

_DATE = PdfLineSelection(font="arial-bold", font_size=(7.8, 8.1)) & PdfLineSelection(
    text="^STATEMENTS OF NET ASSETS AS OF"
)

_TOTAL_ASSETS = _TOTALS & PdfLineSelection(text="^Total Assets")
_TOTAL_LIABILITIES = _TOTALS & PdfLineSelection(text="^Total Liabilities")
_TOTAL_NET_ASSETS = _TOTALS & PdfLineSelection(text="^Total Net Assets")

# La colonna delle etichette finisce a 180: oltre ci sono solo valori e testate.
_VALUES = PdfLineSelection.area(180.0, 0.0, 1e6, 1e6)


def _centre(line):
    """L'ascissa media della riga, che è ciò con cui una riga si assegna a una colonna."""
    return (line.bbox[0] + line.bbox[2]) / 2.0


def _value_row(lines, anchor):
    """I valori della riga che `anchor` apre: stessa banda di ordinate, oltre le etichette."""
    found = anchor.select(lines)
    if not found:
        return []
    top, bottom = found[0].bbox[1], found[0].bbox[3]
    return [
        line
        for line in _VALUES.select(lines)
        if line.bbox[1] < bottom and line.bbox[3] > top and line.text.strip()
    ]


def _nearest(centres, line):
    """L'indice della colonna più vicina all'ascissa della riga."""
    return min(range(len(centres)), key=lambda i: abs(centres[i] - _centre(line)))


def pdf_extract_assets(page):
    """Un blocco per comparto, composto **per colonne**.

    `A4` saprebbe appaiare i tre importi per ascissa, ma la valuta la tratta come un dato della
    pagina e non della colonna: su questa pagina la prima colonna è in CHF e le altre tre in EUR,
    e tutte e quattro uscivano in CHF. Finché `A4` non impara ad appaiare anche quella, la pagina
    si legge qui — che è geometria, e quindi il posto giusto (`R23`).
    """
    lines = pdflines_from_pagedict(page)
    currencies = sorted(assets_currency_set.select(lines), key=_centre)
    if not currencies:
        return []
    centres = [_centre(line) for line in currencies]

    names = [[] for _ in centres]
    for line in sorted(assets_fund_set.select(lines), key=lambda line: line.bbox[1]):
        names[_nearest(centres, line)].append(line.text.strip())

    amounts = {}
    for key, anchor in (
        ("tot_assets", _TOTAL_ASSETS),
        ("liabilities", _TOTAL_LIABILITIES),
        ("net_assets", _TOTAL_NET_ASSETS),
    ):
        column = [None] * len(centres)
        for line in _value_row(lines, anchor):
            column[_nearest(centres, line)] = line.text.strip()
        amounts[key] = column

    date = _DATE.select(lines)
    date = date[0].text.strip() if date else None

    blocks = []
    for index, currency in enumerate(currencies):
        name = " ".join(part for part in names[index] if part)
        values = {key: amounts[key][index] for key in amounts}
        if not name or any(value is None for value in values.values()):
            continue
        metadata = {"fund": name, "currency": currency.text.strip(), "date": date}
        metadata.update(values)
        blocks.append(PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, metadata, ""))
    return blocks


text_filter_assets = TextFilterAssetsStandard(
    "STATEMENTS OF NET ASSETS AS OF (.+)$", "STATEMENTS OF NET ASSETS AS OF"
)

_EN_MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)


def to_date_month_first(text):
    """`FEBRUARY 28, 2023`: il mese per primo, che nessuno dei convertitori del motore legge."""
    found = re.match(r"\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\s*$", str(text).strip())
    if not found:
        raise ValueError('"{}" is not in "MONTH DD, YYYY" format'.format(text))
    month, day, year = found.groups()
    if month.lower() not in _EN_MONTHS:
        raise ValueError('"{}" is not an English month'.format(month))
    return datetime.date(int(year), _EN_MONTHS.index(month.lower()) + 1, int(day))


def to_amount(text):
    """Il trattino è zero, le parentesi sono il segno, e il segno qui è tipografia (`R31`)."""
    cleaned = str(text).strip()
    if cleaned in ("-", "–", ""):
        return 0
    return to_int(cleaned.strip("()"))


deserialize_assets = DeserializerAssetsStandard(
    num_converter=to_amount, date_converter=to_date_month_first
)


pipelines = {
    # Nessun `DeserializerInvestmentsManagerFromManco` qui: i comparti che restano alla societa'
    # di gestione li calcola `assign` sulla pagina dei gestori, e darglieli tutti da questa parte
    # vorrebbe dire scrivere due volte le stesse righe.
    "manco_note": Pipeline(
        pdf_extract_manco,
        text_filter_manco,
        DeserializerManagmentCompanyStandard(),
    ),
    # Il secondo deserializzatore serve al comparto che **solo** questa sezione nomina:
    # `Willerfunds - Private Suite - Fidelity USD Bond` non compare fra gli investimenti, e senza
    # di lui `funds.csv` guadagnerebbe una riga senza rapporto ne' pagina.
    "fund_assets": Pipeline(
        pdf_extract_assets, text_filter_assets, deserialize_assets
    ),
    # Il terzo deserializzatore e' `C10`: questa classe ridichiara la societa' di gestione coi
    # comparti che la pagina dei gestori fa **nascere**, e senza di lui il blocco si ferma qui.
    "inv_managers": Pipeline(
        pdf_extract_inv_managers,
        text_filter_inv_managers,
        (
            DeserializerInvestmentsManagerStandard(),
            DeserializerFundStandard(),
            DeserializerManagmentCompanyStandard(),
        ),
    ),
}
