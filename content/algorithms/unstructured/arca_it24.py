"""ARCA-IT24: gli attivi a cavallo di due pagine, e la sezione degli eventi che li nega.

`FC-5`. `Eventi rilevanti` di p6 è una sezione che c'è, si apre, e **dichiara l'assenza**:
*«Non si segnalano eventi rilevanti.»* Non è un buco da riempire — è il dato, e leggerlo è la
prova che la sezione è stata trovata. La pipeline è quella di tutti gli altri, e il risultato
vuoto viene da sé: nessuna frase della sezione porta un evento, quindi nessuna riga esce.

L'intestazione **è un parametro** e non una costante (`R13`): ARCA scrive `Eventi rilevanti`,
AMUNDI-IT24 scrive `Eventi che hanno interessato il fondo`.
"""

import carryover
import renaming
import sfdr

from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractFundStandard,
    PdfExtractCurrencyConstant,
    PdfExtractLabelledValueStandard,
)
from freeports.consts import Currency
from freeports.utils.pdf_extract import (
    LabelledValueWhere,
    PdfLineSelection,
)
from freeports.standard_funcs.text_filter import TextFilterAssetsStandard
from freeports.standard_funcs.deserialize import DeserializerAssetsStandard
from freeports.utils.deserialize import to_int
from freeports.core import Pipeline
from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.standard_funcs.pdf_extract import PdfExtractSectionStandard
from freeports.utils.deserialize import to_date_with_it_month


subfund_set = PdfLineSelection.area(0.0, 0.0, 1e6, 60.0) & (
    PdfLineSelection.font("Calibri") | PdfLineSelection.font("Lato-Regular")
)


body_set = PdfLineSelection(
    font="TrebuchetMS", font_size=(6.95, 6.97)
) & PdfLineSelection.area_from_bounds(
    x0=0.0,
    y0=PdfLineSelection(
        font="Lato-Regular",
        text="Elenco analitico dei principali strumenti finanziari detenuti dal Fondo",
        font_size=(11.9, 12.1),
    ),
    x1=1e6,
    y1=1e6,
)


# ----------------------------------------------------------------------------------------------
# La situazione patrimoniale, che sta su due pagine (`FA-2` e `FA-3`)
# ----------------------------------------------------------------------------------------------
# `SITUAZIONE PATRIMONIALE` apre l'attivo su una pagina e continua col passivo e il netto su
# quella dopo. `FundAssets` vuole i tre importi insieme e li controlla insieme (`R32`), quindi
# nessuna delle due pagine da sola costruisce la riga: il totale delle attivita' attraversa il
# confine come promessa, e il template `carryover` e' il posto dove l'identificativo e' scritto.
#
# Le due pagine sono due classi e due pipeline perche' portano dati diversi (`R27`), e nello
# `algorithms_schedule.csv` quella dell'attivo viene prima, con `Filter next iteration = TRUE`.

TOT_ASSETS = "TOT_ASSETS"
LIABILITIES = "LIABILITIES"
NET_ASSETS = "NET_ASSETS"
ASSETS_DATE = "ASSETS_DATE"

totals_set = PdfLineSelection(font="TrebuchetMS-Bold", font_size=(6.9, 7.0))
column_heading_set = PdfLineSelection(font="TrebuchetMS", font_size=(6.9, 7.0))

# `R5`: l'esercizio precedente non si estrae. Le due pagine mettono la colonna corrente in due
# posti diversi, e fra le due colonne di valori la pagina dell'attivo ne infila una di percentuali:
# nessuna delle tre si separa con un'ancora testuale, perche' portano tutte soltanto delle cifre.
# Le ascisse sono misurate su tutt'e due i documenti di prova, che concordano: sull'attivo il
# valore sta fra 310 e 353 e la percentuale comincia a 384; sul passivo il valore sta fra 407 e
# 451 e l'esercizio precedente comincia a 458.
current_year_on_assets = PdfLineSelection.area(0.0, 0.0, 370.0, 1e6)
current_year_on_liabilities = PdfLineSelection.area(0.0, 0.0, 455.0, 1e6)

assets_carryover = carryover.Carryover("tot_assets")

pdf_extract_tot_assets = PdfExtractLabelledValueStandard(
    totals_set & PdfLineSelection(text="^TOTALE ATTIVITA'"),
    TOT_ASSETS,
    "tot_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year_on_assets,
)

pdf_extract_liabilities = PdfExtractLabelledValueStandard(
    totals_set & PdfLineSelection(text="^TOTALE PASSIVITA'"),
    LIABILITIES,
    "liabilities",
    where=LabelledValueWhere.RIGHT,
    value=current_year_on_liabilities,
)

# `CLASSE P` e `CLASSE R` cominciano con le stesse parole: e' il netto della classe di quote, non
# quello del fondo. Le si tolgono dalla selezione, e non ci si affida al fatto che il netto del
# fondo venga per primo: le righe di una pagina non arrivano in ordine di lettura, e `take=FIRST`
# sceglie la prima dell'elenco, non la piu' in alto.
pdf_extract_net_assets = PdfExtractLabelledValueStandard(
    (totals_set & PdfLineSelection(text="^VALORE COMPLESSIVO NETTO DEL FONDO"))
    - PdfLineSelection(text="CLASSE"),
    NET_ASSETS,
    "net_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year_on_liabilities,
)

# `R17`: la data si prende dalla colonna. Sta sotto `Situazione al`, alla stessa ascissa, mentre
# la copertina la scrive dentro il titolo del prospetto, che e' la fonte meno diretta.
pdf_extract_assets_date = PdfExtractLabelledValueStandard(
    column_heading_set & PdfLineSelection(text="^Situazione al"),
    ASSETS_DATE,
    "assets date",
    where=LabelledValueWhere.BELOW,
)

record_begin = carryover.Record(
    fund="FUND_NAME",
    currency="CURRENCY_STATEMENT",
    tot_assets=TOT_ASSETS,
)

record_end = carryover.Record(
    fund="FUND_NAME",
    currency="CURRENCY_STATEMENT",
    date=ASSETS_DATE,
    liabilities=LIABILITIES,
    net_assets=NET_ASSETS,
)

assets_filter = TextFilterAssetsStandard()


def text_filter_fund_assets_begin(pdf_blks, filter_data):
    """La prima delle due pagine: un prospetto solo, filtrato sui fondi d'interesse."""
    return assets_filter(record_begin(pdf_blks), filter_data)


def text_filter_fund_assets_end(pdf_blks, filter_data):
    """La seconda: il filtro **prima** e la promessa **dopo**.

    In quest'ordine ogni blocco che arriva a `resume` parla di un comparto d'interesse, e non
    trovare la promessa e' davvero un difetto — non il caso normale di un fondo che non interessa.
    """
    return assets_carryover.resume(assets_filter(record_end(pdf_blks), filter_data), filter_data)


# La sezione si apre sull'intestazione in grassetto e si chiude sulla prossima dello stesso
# carattere, che è il comportamento per difetto di `family`.
pdf_extract_merges = PdfExtractSectionStandard(
    PdfLineSelection(font="lato-bold", font_size=(11.5, 12.5), text="^Eventi rilevanti"),
    OnePdfBlockType.RELEVANT_BLOCK.name,
    "merges",
    body=PdfLineSelection(font="lato-regular", font_size=(9.5, 10.5)),
)

# Le due forme in cui i bilanci italiani della raccolta scrivono un evento: l'incorporazione,
# misurata su EURIZON-IT24 D3 p14, e la ridenominazione, misurata sullo stesso paragrafo. Qui non
# trovano niente, ed è esattamente ciò che la sezione dichiara.
read_merges = renaming.Sentence(
    merged=(
        r"(?P<when>[0-9]{1,2} [a-zàèéìòù]+ [0-9]{4}) (?:il|la) [Ff]ondo "
        r"[\u201c\"](?P<old>[^\u201d\"]+)[\u201d\"] è stato incorporato "
        r"(?:nel|in) [Ff]ondo [\u201c\"](?P<current>[^\u201d\"]+)[\u201d\"]",
    ),
    renamed=(
        r"[Ii]l [Ff]ondo [\u201c\"](?P<current>[^\u201d\"]+)[\u201d\"] "
        r"\(già denominato (?P<old>[^)]+)\) .{0,40}?"
        r"(?P<when>[0-9]{1,2} [a-zàèéìòù]+ [0-9]{4})",
    ),
)

pipelines = {
    "merges": Pipeline(
        pdf_extract=pdf_extract_merges,
        text_filter=renaming.text_filter(read_merges),
        deserialize=renaming.deserialize(to_date_with_it_month),
    ),
    "investments": Pipeline(
        pdf_extract=(
            PdfExtractInvestmentsStandard(body_set=body_set),
            PdfExtractFundStandard(subfund_set),
            PdfExtractCurrencyConstant(Currency.EUR),
        )
    ),
    "fund_assets_begin": Pipeline(
        pdf_extract=(
            PdfExtractFundStandard(subfund_set),
            PdfExtractCurrencyConstant(Currency.EUR),
            pdf_extract_tot_assets,
        ),
        text_filter=text_filter_fund_assets_begin,
        deserialize=assets_carryover.deposit,
    ),
    "fund_assets_end": Pipeline(
        pdf_extract=(
            PdfExtractFundStandard(subfund_set),
            PdfExtractCurrencyConstant(Currency.EUR),
            pdf_extract_assets_date,
            pdf_extract_liabilities,
            pdf_extract_net_assets,
        ),
        text_filter=text_filter_fund_assets_end,
        deserialize=DeserializerAssetsStandard(to_int),
    ),
    # L'articolo si legge dalla casella spuntata, non dal titolo: il titolo resta come verifica
    # (`R34`). Su questo formato il segno è un'immagine, e una sola nella banda -- la casella vuota
    # e' disegnata, non fotografata.
    "sfdr_classification": sfdr.ITALIAN.pipeline(),
}
