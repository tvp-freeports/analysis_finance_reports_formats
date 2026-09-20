import carryover

from freeports.standard_funcs.pdf_extract import (
    PdfExtractCurrencyConstant,
    PdfExtractFundStandard,
    PdfExtractLabelledValueStandard,
    PdfExtractManagmentCompanyStandard,
)
from freeports.standard_funcs.text_filter import (
    TextFilterAssetsStandard,
    TextFilterManagmentCompanyStandard,
)
from freeports.standard_funcs.deserialize import DeserializerAssetsStandard, DeserializerManagmentCompanyStandard, DeserializerInvestmentsManagerFromManco
from freeports.utils.deserialize import to_int
from freeports.utils.pdf_extract import LabelledValueWhere, PdfLineSelection
from freeports.consts import Currency
from freeports.core import Pipeline


# ----------------------------------------------------------------------------------------------
# La situazione patrimoniale, che sta su due pagine (`FA-2` e `FA-3`)
# ----------------------------------------------------------------------------------------------
# Due comparti, due coppie: p18->19 e p26->27.
#
# Il nome del fondo si prende dalla **testatina**, che e' la stessa riga da cui lo prendono gli
# investimenti: `R24` chiede che i due lo scrivano allo stesso modo, e il modo piu' sicuro di
# ottenerlo e' leggere la stessa riga. Che quella riga sia un nome brutto —
# `FIDEURAM ITALIAFIDEURAM ISPB ASSET MANAGEMENT SGR SPA...` in `funds.csv` — e' un difetto della
# ricetta degli investimenti, e si corregge la' per tutt'e due insieme.

TOT_ASSETS = "TOT_ASSETS"
LIABILITIES = "LIABILITIES"
NET_ASSETS = "NET_ASSETS"
ASSETS_DATE = "ASSETS_DATE"

fund_heading_set = PdfLineSelection(
    font="ArialBold", font_size=(10.9, 11.1), area=(0.0, 30.0, 1e6, 60.0)
)
statement_title_set = PdfLineSelection(
    font="ArialBold", font_size=(10.9, 11.1), area=(0.0, 100.0, 1e6, 130.0)
)
totals_set = PdfLineSelection(font="TahomaBold", font_size=(6.9, 7.0))

# `R5`: l'esercizio precedente non si estrae. Sull'attivo il valore finisce a 334,2 e la
# percentuale comincia a 364,5; sul passivo il valore finisce a 418,6 e l'esercizio precedente
# comincia a 464,8. Misurato su tutt'e due le coppie.
current_year_on_assets = PdfLineSelection.area(0.0, 0.0, 350.0, 1e6)
current_year_on_liabilities = PdfLineSelection.area(0.0, 0.0, 440.0, 1e6)

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

# `Valore complessivo netto della classe` e' la classe di quote: la maiuscola la distingue.
pdf_extract_net_assets = PdfExtractLabelledValueStandard(
    totals_set & PdfLineSelection(text="^VALORE COMPLESSIVO NETTO DEL FONDO"),
    NET_ASSETS,
    "net_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year_on_liabilities,
)

# `R17` vuole la data dalla colonna, e qui la colonna la scrive in due modi: su p19 `Situazione al`
# e la data sono due righe, su p27 sono una sola. Il titolo del prospetto — `FIDEURAM ITALIA AL
# 28/06/2024` — la porta invece sempre allo stesso modo, ed e' della pagina, non della copertina.
# E' il caso in cui la seconda scelta di `R17` e' la piu' ferma.
pdf_extract_assets_date = PdfExtractLabelledValueStandard(
    statement_title_set, ASSETS_DATE, "assets date"
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

assets_filter = TextFilterAssetsStandard(" AL ([0-9/]+)$")


def text_filter_fund_assets_begin(pdf_blks, filter_data):
    """La prima delle due pagine: un prospetto solo, filtrato sui fondi d'interesse."""
    return assets_filter(record_begin(pdf_blks), filter_data)


def text_filter_fund_assets_end(pdf_blks, filter_data):
    """La seconda: il filtro **prima** e la promessa **dopo**."""
    return assets_carryover.resume(assets_filter(record_end(pdf_blks), filter_data), filter_data)


pipelines = {
    "manco": Pipeline(
        pdf_extract=PdfExtractManagmentCompanyStandard(
            PdfLineSelection.area_from_movewindow(
                PdfLineSelection(font="arial",font_size=(9.9,10.1),text="Società di gestione:"),
                (-0.2,1.5),100.0,1.2
            )
        ),
        text_filter=TextFilterManagmentCompanyStandard(),
        deserialize=(
            DeserializerManagmentCompanyStandard(),
            DeserializerInvestmentsManagerFromManco()
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

