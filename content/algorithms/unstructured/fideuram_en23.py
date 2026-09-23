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
from freeports.core import Pipeline
from freeports.interfaces.pdf_blks import OnePdfBlockType, ResultStandardExtraction
from freeports.standard_funcs.deserialize import (
    DeserializerFundStandard,
    DeserializerInvestmentsManagerStandard,
    DeserializerManagmentCompanyStandard,
)
from freeports.output import Fund
from freeports.standard_funcs.pdf_extract import (
    AssetsColumn,
    PdfExtractAssetsStandard,
    PdfExtractLabelledValueStandard,
    PdfExtractSectionStandard,
)
from freeports.standard_funcs.deserialize import DeserializerAssetsStandard
from freeports.standard_funcs.text_filter import TextFilterAssetsStandard
from freeports.utils.deserialize import to_int
from freeports.utils.pdf_extract import PdfLineSelection
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
    assignment = inv_managers.assign(
        read_inv_managers(pdf_blks),
        inv_managers.fund_set(
            result.name for result in filter_data if isinstance(result, Fund)
        ),
        manco=manco.declared(filter_data),
    )
    return inv_managers.text_blocks(assignment)




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
# corpo. Le separa l'ordinata, ed è misurata su tutte le pagine del prospetto.
assets_fund_set = _HEAD & PdfLineSelection.area(180.0, 130.0, 1e6, 183.0)
assets_currency_set = _HEAD & PdfLineSelection.area(180.0, 183.0, 1e6, 197.0)

pdf_extract_assets = PdfExtractAssetsStandard(
    fund_set=assets_fund_set,
    currency_set=assets_currency_set,
    tot_assets=AssetsColumn(
        _TOTALS & PdfLineSelection(text="^Total Assets"),
        vec=(1.2, -0.1),
        mult=(100.0, 1.2),
    ),
    liabilities=AssetsColumn(
        _TOTALS & PdfLineSelection(text="^Total Liabilities"),
        vec=(1.2, -0.1),
        mult=(100.0, 1.2),
    ),
    net_assets=AssetsColumn(
        _TOTALS & PdfLineSelection(text="^Total Net Assets"),
        vec=(1.2, -0.1),
        mult=(100.0, 1.2),
    ),
    date=PdfLineSelection(font="arial-bold", font_size=(7.8, 8.1))
    & PdfLineSelection(text="^STATEMENTS OF NET ASSETS AS OF"),
    table_condition=True,
)

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
    "inv_managers": Pipeline(
        pdf_extract_inv_managers,
        text_filter_inv_managers,
        (DeserializerInvestmentsManagerStandard(), DeserializerFundStandard()),
    ),
}
