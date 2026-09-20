"""Unstructured module for AMUNDI-IT24.

Solo la situazione patrimoniale: gli investimenti stanno al livello strutturato, in
`content/algorithms/structured/investments/args.csv`, e non si toccano.

# Le due pagine, e la colonna che si sposta (`FA-2` e `FA-3`)

Ventisette comparti, ventisette coppie di pagine, dalla p20->21 alla p715->716. La difficolta' di
questo formato non e' l'appaiamento: e' `R5`, cioe' **quale** delle colonne di numeri e' l'esercizio
corrente.

Due comparti su ventisette sono nati durante l'esercizio e **non hanno l'anno prima**. La loro
pagina non lascia la colonna vuota: la toglie, e il valore corrente si stampa dove sulle altre
pagine sta quello precedente. Sulla pagina del passivo i due posti coincidono esattamente —
`504,6-533,9` per il valore corrente di p254, `508,8-533,9` per il precedente di p21 — quindi
**nessuna ascissa fissa** distingue i due casi, e neanche una distanza dall'etichetta: sulle pagine
a due colonne il valore sta a ventun righe dall'etichetta, su quelle a una a trentatre'.

Cio' che le distingue e' l'intestazione. `Situazione a fine esercizio precedente` c'e' **solo** dove
la colonna c'e', e il suo margine sinistro e' il limite destro dell'esercizio corrente; dove non
c'e', la selezione non trova niente e il limite resta aperto — che e' la lettura giusta, perche'
non c'e' nessuna colonna da cui difendersi. A questo si aggiunge una sola sottrazione: le
percentuali portano la virgola decimale e gli importi no.
"""

import carryover

from freeports.standard_funcs.pdf_extract import (
    PdfExtractCurrencyConstant,
    PdfExtractFundStandard,
    PdfExtractLabelledValueStandard,
)
from freeports.standard_funcs.text_filter import TextFilterAssetsStandard
from freeports.standard_funcs.deserialize import DeserializerAssetsStandard
from freeports.utils.deserialize import to_int
from freeports.utils.pdf_extract import LabelledValueWhere, PdfLineSelection
from freeports.consts import Currency
from freeports.core import Pipeline

TOT_ASSETS = "TOT_ASSETS"
LIABILITIES = "LIABILITIES"
NET_ASSETS = "NET_ASSETS"
ASSETS_DATE = "ASSETS_DATE"

fund_heading_set = PdfLineSelection(
    font="Arial-BoldItalicMT", font_size=(9.9, 10.1), area=(0.0, 40.0, 1e6, 60.0)
)
totals_set = PdfLineSelection(font="TrebuchetMS-Bold", font_size=(6.9, 7.0))
body_set_7pt = PdfLineSelection(font="TrebuchetMS", font_size=(6.9, 7.0))

# `R5`: l'esercizio corrente e' cio' che sta a sinistra della **sua intestazione**, meno le
# percentuali, che sono le sole a portare una virgola. Dove l'intestazione manca — il comparto e'
# nato nell'esercizio — la selezione non trova niente e il limite resta aperto: e' la risposta
# giusta, non una scappatoia, perche' l'unica colonna che c'e' e' quella corrente.
current_year = PdfLineSelection.area_from_bounds(
    0.0, 0.0, PdfLineSelection(text="^Situazione a fine"), 1e6
) - PdfLineSelection(text=",")

assets_carryover = carryover.Carryover("tot_assets")

pdf_extract_tot_assets = PdfExtractLabelledValueStandard(
    totals_set & PdfLineSelection(text="^TOTALE ATTIVITÀ"),
    TOT_ASSETS,
    "tot_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year,
)

pdf_extract_liabilities = PdfExtractLabelledValueStandard(
    totals_set & PdfLineSelection(text="^TOTALE PASSIVITÀ"),
    LIABILITIES,
    "liabilities",
    where=LabelledValueWhere.RIGHT,
    value=current_year,
)

pdf_extract_net_assets = PdfExtractLabelledValueStandard(
    body_set_7pt & PdfLineSelection(text="^VALORE COMPLESSIVO NETTO DEL FONDO"),
    NET_ASSETS,
    "net_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year,
)

pdf_extract_assets_date = PdfExtractLabelledValueStandard(
    body_set_7pt & PdfLineSelection(text="^Situazione al"),
    ASSETS_DATE,
    "assets date",
    where=LabelledValueWhere.BELOW,
)

record_begin = carryover.Record(
    fund="FUND_NAME", currency="CURRENCY_STATEMENT", tot_assets=TOT_ASSETS
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
    """La seconda: il filtro **prima** e la promessa **dopo**."""
    return assets_carryover.resume(assets_filter(record_end(pdf_blks), filter_data), filter_data)


pipelines = {
    "fund_assets_begin": Pipeline(
        pdf_extract=(
            PdfExtractFundStandard(fund_heading_set),
            PdfExtractCurrencyConstant(Currency.EUR),
            pdf_extract_tot_assets,
        ),
        text_filter=text_filter_fund_assets_begin,
        deserialize=assets_carryover.deposit,
    ),
    "fund_assets_end": Pipeline(
        pdf_extract=(
            PdfExtractFundStandard(fund_heading_set),
            PdfExtractCurrencyConstant(Currency.EUR),
            pdf_extract_assets_date,
            pdf_extract_liabilities,
            pdf_extract_net_assets,
        ),
        text_filter=text_filter_fund_assets_end,
        deserialize=DeserializerAssetsStandard(to_int),
    ),
}
