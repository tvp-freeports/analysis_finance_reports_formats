"""CANE-EN23 custom functions"""

import re

import sfdr
from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractCurrencyStandard,
    PdfExtractFundStandard,
    PdfExtractManagmentCompanyStandard,
    AssetsColumn,
    PdfExtractAssetsStandard,
)
from freeports.utils.pdf_extract import (
    pdfline_selection_from_str,
    PdfLineSelection,
)
from freeports.standard_funcs.text_filter import (
    TextFilterManagmentCompanyStandard,
    TextFilterAssetsStandard,
)
from freeports.standard_funcs.deserialize import (
    DeserializerManagmentCompanyStandard,
    DeserializerAssetsStandard,
)
from freeports.utils.deserialize import to_float
from freeports.core import Pipeline

subfund_set = PdfLineSelection(
    font="ArialMT", font_size=(6.95, 6.97)
) & PdfLineSelection.area_from_movewindow(
    target=pdfline_selection_from_str('ArialMT[6.96] "^Annual report including"'),
    vec=(0.1, 0.8),
    width_mult=2.0,
    height_mult=1.4,
)

currency_set = pdfline_selection_from_str('Arial-BoldMT "Valuation in"')
body_set = pdfline_selection_from_str("ArialMT[6.96](160:786)")


currency_set_assets = PdfLineSelection.area_from_movewindow(
    target=PdfLineSelection(font="arial-boldmt", font_size=(7.9, 8.2), text="^Assets"),
    vec=(1.2, -1.0),
    width_mult=100,
    height_mult=1.5,
)

# `R17`: la data degli attivi si prende **dalla pagina**, e non si lascia vuota. Sta sulla riga di
# `Assets`, all'estrema destra e sopra la colonna dei numeri -- misurata identica su tutte e dieci
# le pagine del prospetto (`31.12.2023` a `x=497,8`, Arial-BoldMT 8.04). La finestra e' quella della
# valuta con l'ordinata ferma: `EUR` sta una riga sopra `Assets`, la data sulla riga stessa.
date_set_assets = PdfLineSelection.area_from_movewindow(
    target=PdfLineSelection(font="arial-boldmt", font_size=(7.9, 8.2), text="^Assets"),
    vec=(1.2, 0.0),
    width_mult=100,
    height_mult=1.0,
)

pdf_extract_assets = PdfExtractAssetsStandard(
    fund_set=subfund_set,
    currency_set=currency_set_assets,
    date=date_set_assets,
    tot_assets=AssetsColumn(
        PdfLineSelection(font="arial-boldmt", font_size=(7.9, 8.2), text="^Total Assets"),
        mult=(100.0, 1.02),
    ),
    liabilities=AssetsColumn(
        PdfLineSelection(font="arial-boldmt", font_size=(7.9, 8.2), text="^Total Liabilities"),
        mult=(100.0, 1.02),
    ),
    net_assets=AssetsColumn(
        PdfLineSelection(
            font="arial-boldmt",
            font_size=(7.9, 8.2),
            text="^Net assets at the end of the financial year",
        ),
        mult=(100.0, 1.02),
    ),
)

# `R16`: il prospetto degli attivi intitola le sue pagine con lo stesso nome che gli investimenti
# leggono, richiamo di nota compreso -- `Sidera Funds SICAV - Christian Equity*` su p36. Il marchio
# va tolto **da tutt'e due i lati**: la colonna `Note marks` lo toglie dagli investimenti, e se qui
# restasse, il comparto che gli attivi cercano non sarebbe piu' quello che `funds.csv` scrive.
text_filter_assets = TextFilterAssetsStandard("^([0-9.]+)$", note_marks="*")

# Sidera Funds lays the Statement of Net Assets out so that assets plus liabilities equal net
# assets, which means "Total Liabilities" is printed negative. The output schema wants the
# magnitude — it checks `liabilities + net_assets == tot_assets` — so the sign is dropped here,
# where the convention is visible, rather than by the cast, which honours every sign it reads.
deserialize_assets = DeserializerAssetsStandard(num_converter=lambda text: abs(to_float(text)))

pipelines = {
    "investments": Pipeline(
        pdf_extract=(
            PdfExtractInvestmentsStandard(currency_set=currency_set, body_set=body_set),
            PdfExtractFundStandard(subfund_set),
            PdfExtractCurrencyStandard(currency_set),
        )
    ),
    "fund_assets": Pipeline(pdf_extract_assets, text_filter_assets, deserialize_assets),
    "manco": Pipeline(
        pdf_extract=PdfExtractManagmentCompanyStandard(
            PdfLineSelection.area_from_movewindow(
                PdfLineSelection(
                    font="arial-boldmt", font_size=(7.9, 8.1), text="Management Company"
                ),
                (-0.1, 0.8),
                100,
                2.5,
            )
            & PdfLineSelection.area_from_bounds(
                x1=PdfLineSelection(
                    font="arial-boldmt", font_size=(7.9, 8.1), text="Legal adviser"
                ),
                x0=0,
                y0=0.0,
                y1=1e6,
            )
        ),
        text_filter=TextFilterManagmentCompanyStandard(),
        deserialize=DeserializerManagmentCompanyStandard(),
    ),
    # Il segno e' una `X` di testo in Arial-BoldMT su tutti e quattro i moduli. Il nome del
    # prodotto sta sotto l'etichetta, non accanto, e va a capo sulla qualificazione.
    #
    # L'ombrello, pero', lo stesso documento lo scrive in due modi: `Sidera Funds SICAV - Christian
    # Equity` su una pagina e `Sidera Funds - Digital Worlds` sulle altre tre, mentre il portafoglio
    # lo scrive sempre `SIDERA FUNDS SICAV`. Per `R24` non basta toglierlo: va tolto **e riscritto**,
    # ed e' per questo che qui convivono una rimozione e un `product_prepend`.
    #
    # Una delle quattro righe si perde lo stesso, e non per colpa del modulo: il portafoglio intitola
    # due comparti `... CHRISTIAN EQUITY*` e `... FINANCIAL BOND*`, col richiamo di nota attaccato
    # che `R16` vorrebbe via. Finche' e' li', il nome del modulo non puo' corrispondere.
    "sfdr_classification": sfdr.ENGLISH.pipeline(
        product_joined=True,
        product_prepend="SIDERA FUNDS SICAV",
        product_prefix=(
            re.compile(r"Product name\s*:\s*"),
            re.compile(r"Sidera Funds(?: SICAV)?\s*[\u2013-]\s*"),
            re.compile(r"\s*\((?:the|il|la)\s[^)]*\)\s*$"),
        ),
    ),
}
