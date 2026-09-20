"""MEDIOLANUM_IT24_B format submodule"""

import carryover

from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractFundStandard,
    PdfExtractCurrencyConstant,
    PdfExtractLabelledValueStandard,
)
from freeports.utils.pdf_extract import (
    LabelledValueWhere,
    PdfLineSelection,
    pdflines_from_pagedict,
)
from freeports.standard_funcs.text_filter import TextFilterAssetsStandard
from freeports.standard_funcs.deserialize import DeserializerAssetsStandard
from freeports.utils.deserialize import to_int
from freeports.core import Pipeline
from freeports.consts import Currency


def pdf_extract(dict_root):
    """This pdf filter calculate dynamically the sixe of the table using some bound text"""
    lines = pdflines_from_pagedict(dict_root)
    prev_headers = PdfLineSelection(
        font="Helvetica-Bold", text="Elenco degli strumenti finanziari in portafoglio"
    ).select(lines)
    next_table = PdfLineSelection(
        font="Helvetica-Bold", text="Strumenti finanziari quotati"
    ).select(lines)

    if len(next_table) == 0:
        next_table = PdfLineSelection(
            font="Helvetica-Bold", text="STRUMENTI FINANZIARI QUOTATI"
        ).select(lines)
    if len(prev_headers) == 0:
        prev_headers = PdfLineSelection(
            font="Helvetica-Bold",
            text="ELENCO DEGLI STRUMENTI FINANZIARI IN PORTAFOGLIO",
        ).select(lines)

    body_low_limit = 700 if len(next_table) == 0 else next_table[0].bbox[3]
    body_top_limit = 100 if len(prev_headers) == 0 else prev_headers[0].bbox[1]
    std = PdfExtractInvestmentsStandard(
        body_set=PdfLineSelection(
            font="Helvetica",
            area=(0.0, body_top_limit, 1e6, body_low_limit),
        ),
        deselection_list=[PdfLineSelection.text("^ ")],
    )

    return std(dict_root)



# ----------------------------------------------------------------------------------------------
# La situazione patrimoniale, che sta su due pagine (`FA-2` e `FA-3`)
# ----------------------------------------------------------------------------------------------
# Nove comparti in un documento solo, e nove coppie di pagine: dalla p12->13 alla p285->286. Qui
# l'appaiamento per nome non e' una cautela, e' il meccanismo — la promessa che la p12 deposita
# dev'essere ritrovata dalla p13 e da nessun'altra delle otto. Il nome sta nella testatina di
# tutt'e due le pagine, che e' la stessa riga che gli investimenti gia' leggono.

TOT_ASSETS = "TOT_ASSETS"
LIABILITIES = "LIABILITIES"
NET_ASSETS = "NET_ASSETS"
ASSETS_DATE = "ASSETS_DATE"

fund_heading_set = PdfLineSelection(font="Helvetica", area=(150, 67, 1e6, 76))
totals_set = PdfLineSelection(font="Helvetica-Bold", font_size=(5.9, 6.1))
body_set_6pt = PdfLineSelection(font="Helvetica", font_size=(5.9, 6.1))

# `R5`: l'esercizio precedente non si estrae. Misurato sulle nove coppie, il valore corrente
# finisce sempre entro 306,7 sull'attivo — dove la percentuale comincia a 364,9 — ed entro 408
# sul passivo, dove l'esercizio precedente comincia a 484.
current_year_on_assets = PdfLineSelection.area(0.0, 0.0, 330.0, 1e6)
current_year_on_liabilities = PdfLineSelection.area(0.0, 0.0, 440.0, 1e6)

assets_carryover = carryover.Carryover("tot_assets")

pdf_extract_tot_assets = PdfExtractLabelledValueStandard(
    totals_set & PdfLineSelection(text="^TOTALE ATTIVITÀ"),
    TOT_ASSETS,
    "tot_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year_on_assets,
)

# `^TOTALE` e non `PASSIVITÀ`: `N. ALTRE PASSIVITÀ` e' una voce del prospetto, non il totale.
pdf_extract_liabilities = PdfExtractLabelledValueStandard(
    totals_set & PdfLineSelection(text="^TOTALE PASSIVITÀ"),
    LIABILITIES,
    "liabilities",
    where=LabelledValueWhere.RIGHT,
    value=current_year_on_liabilities,
)

# Senza ancore: la riga porta uno spazio in testa su cinque pagine su nove e non su le altre
# quattro. Le classi di quote si chiamano `Valore complessivo netto della classe`, quindi non
# c'e' niente da togliere.
pdf_extract_net_assets = PdfExtractLabelledValueStandard(
    body_set_6pt & PdfLineSelection(text="VALORE COMPLESSIVO NETTO DEL FONDO"),
    NET_ASSETS,
    "net_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year_on_liabilities,
)

# `R17`: la data si prende dalla colonna. `Relazione di gestione al` e' l'intestazione
# dell'esercizio precedente, e non comincia con `Situazione`.
pdf_extract_assets_date = PdfExtractLabelledValueStandard(
    body_set_6pt & PdfLineSelection(text="^Situazione al"),
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
    """La seconda: il filtro **prima** e la promessa **dopo**."""
    return assets_carryover.resume(assets_filter(record_end(pdf_blks), filter_data), filter_data)


pipelines = {
    "investments": Pipeline(
        pdf_extract=(
            pdf_extract,
            PdfExtractFundStandard(fund_heading_set),
            PdfExtractCurrencyConstant(Currency.EUR),
        )
    ),
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
