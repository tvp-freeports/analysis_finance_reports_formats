"""MEDIOLANUM-ES24.A: gli investimenti, i gestori delegati, e il prospetto patrimoniale.

`FA-6` sta a p18, p26 e p33 — una per comparto — e **non** a p16, che è il prospetto
`COMBINADO` dell'intero fondo. `R7` vuole i prospetti per comparto, e il combinato è la loro
somma: estrarlo vorrebbe dire scrivere una riga che non corrisponde a nessun comparto e che, se
letta insieme alle altre, conta i patrimoni due volte. Le due pagine si distinguono per la riga
sotto il titolo: sul combinato c'è `COMBINADO`, sulle altre il nome del comparto.

I tre totali stanno **sulla riga dell'etichetta** (`TOTAL ACTIVO`, `TOTAL PASIVOS`, `TOTAL
PATRIMONIO NETO`) e l'equazione torna. La data invece è scritta in spagnolo — `31 de diciembre de
2024` — e il motore i mesi spagnoli non li conosce: il convertitore è tre righe e sta qui, che è
il posto di una cosa che vale per questo formato e per nessun altro.
"""

from lxml import etree
from freeports.core import TextBlock, PdfBlock
from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractPageClassifyStandard,
    PdfExtractCurrencyStandard,
    PdfExtractFundStandard,
    PdfExtractManagmentCompanyStandard,
)
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.utils.pdf_extract import pdflines_from_pagedict, PdfLineSelection
from freeports.standard_funcs.text_filter import (
    TextFilterPageClassifyStandard,
    TextFilterManagmentCompanyStandard,
)
from freeports.interfaces.text_blks import StandardInvestmentsMangerTextBlock
from freeports.utils.text_filter import MatchFund
from freeports.standard_funcs.deserialize import (
    DeserializerAssetsStandard,
    DeserializerPageClassifyStandard,
    DeserializerManagmentCompanyStandard,
    DeserializerInvestmentsManagerStandard,
)
from freeports.standard_funcs.pdf_extract import PdfExtractLabelledValueStandard
from freeports.standard_funcs.text_filter import TextFilterAssetsStandard
from freeports.utils.deserialize import to_int
from freeports.utils.pdf_extract import LabelledValueWhere
import carryover
import datetime
from freeports.output import Fund
from freeports.core import Pipeline
import re

h_font = PdfLineSelection.font_of(PdfLineSelection.text("n de la cartera"))
curr_set = PdfLineSelection(font_size=(8.9, 9.1), text="(expresado en") & h_font



def pdf_extract_inv_managers(page):
    lines=pdflines_from_pagedict(page)
    top=PdfLineSelection.text("Gestores Delegados de Inversiones").select(lines)[0].bbox[3]
    left_column=(
        PdfLineSelection.area_from_bounds(x0=0.0,y0=top-10,x1=290,y1=1e6) & PdfLineSelection.font_size(9.8,10.0)
    ) 
    right_column=PdfLineSelection.area_from_bounds(x0=290,y0=0.0,x1=1e6,y1=PdfLineSelection.text("Administrador Fiduciario"))
    body = (
        (left_column | right_column) / PdfLineSelection.text("^ $") / PdfLineSelection.text("^  $")
    ).select(lines)
    return [
        PdfBlock(ResultStandardExtraction.INVESTMENTS_MANAGER.name,{},b.text) for b in body
    ]

date_regex=re.compile("\\((desde el|hasta el) [^)]+\\)")
fund_regex=re.compile("\\((.*)\\)")
def text_filter_inv_managers(pdf_blks,filter_data):
    funds=set(map(lambda x: MatchFund(x.name),filter(lambda x: isinstance(x,Fund),filter_data)))
    curr_inv_man=None
    manco=None
    res=[]
    investments_managers_funds=set()
    for blk in pdf_blks:
        if blk.type_block == ResultStandardExtraction.MANAGEMENT_COMPANY.name:
            manco=blk.content
            continue
        txt=blk.content
        txt=txt.replace("*","")
        txt=date_regex.sub("",txt)
        txt=txt.strip()
        if txt=="":
            continue
        if curr_inv_man is None:
            curr_inv_man = txt
            continue
        m=fund_regex.match(txt)
        if m:
            f=MatchFund(m.group(1).strip())
            if f in funds:
                investments_managers_funds.add(f)
                res.append(
                    StandardInvestmentsMangerTextBlock.from_name(curr_inv_man,[f])
                )
            curr_inv_man=None
    res.append(
        StandardInvestmentsMangerTextBlock.from_name(manco,funds - investments_managers_funds)
    )
    return res


deserialize_inv_managers = DeserializerInvestmentsManagerStandard()




# ----------------------------------------------------------------------------------------------
# Il prospetto patrimoniale, uno per comparto (`FA-6`)
# ----------------------------------------------------------------------------------------------

TOT_ASSETS = "TOT_ASSETS"
LIABILITIES = "LIABILITIES"
NET_ASSETS = "NET_ASSETS"
ASSETS_DATE = "ASSETS_DATE"

# Il titolo del comparto, sotto quello del prospetto. Sul combinato al suo posto c'è `COMBINADO`,
# e il trattino è ciò che li distingue senza doverlo dire per nome.
subfund_set = PdfLineSelection(font_size=(11.9, 12.1)) & PdfLineSelection.text("^GAMAX FUNDS - ")

assets_statement_set = PdfLineSelection.text("Estado del patrimonio neto")

_TOTALS = PdfLineSelection(font="timesnewromanps-boldmt", font_size=(7.4, 7.7))

# La testata della colonna: la valuta a sinistra e la data a destra, sulla stessa riga, in
# grassetto corpo 8. Nessuna delle due porta un'etichetta, quindi si prendono per posizione.
_HEADING = PdfLineSelection(font="timesnewromanps-boldmt", font_size=(7.9, 8.2))
assets_currency_set = _HEADING & PdfLineSelection.area(0.0, 118.0, 120.0, 140.0)
assets_date_set = _HEADING & PdfLineSelection.area(440.0, 118.0, 1e6, 140.0)

pdf_extract_tot_assets = PdfExtractLabelledValueStandard(
    _TOTALS & PdfLineSelection(text="^TOTAL ACTIVO"),
    TOT_ASSETS,
    "tot_assets",
    where=LabelledValueWhere.RIGHT,
)

pdf_extract_liabilities = PdfExtractLabelledValueStandard(
    _TOTALS & PdfLineSelection(text="^TOTAL PASIVOS"),
    LIABILITIES,
    "liabilities",
    where=LabelledValueWhere.RIGHT,
)

pdf_extract_net_assets = PdfExtractLabelledValueStandard(
    _TOTALS & PdfLineSelection(text="^TOTAL PATRIMONIO NETO"),
    NET_ASSETS,
    "net_assets",
    where=LabelledValueWhere.RIGHT,
)

record_assets = carryover.Record(
    fund="FUND_NAME",
    currency="CURRENCY_STATEMENT",
    date=ASSETS_DATE,
    tot_assets=TOT_ASSETS,
    liabilities=LIABILITIES,
    net_assets=NET_ASSETS,
)

assets_filter = TextFilterAssetsStandard()


def text_filter_fund_assets(pdf_blks, filter_data):
    """Un prospetto per pagina, filtrato sui comparti d'interesse."""
    return assets_filter(record_assets(pdf_blks), filter_data)


_ES_MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def to_date_with_es_month(text):
    """`31 de diciembre de 2024`, che è l'unico modo in cui questo formato scrive una data."""
    found = re.match(
        r"\s*(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})\s*$", str(text).strip(), re.I
    )
    if not found:
        raise ValueError('"{}" is not in "DD de MONTH de YYYY" format'.format(text))
    day, month, year = found.groups()
    if month.lower() not in _ES_MONTHS:
        raise ValueError('"{}" is not a Spanish month'.format(month))
    return datetime.date(int(year), _ES_MONTHS.index(month.lower()) + 1, int(day))


pipelines = {
    "": Pipeline(
        pdf_extract=(
            PdfExtractPageClassifyStandard(
                header_sets=[PdfLineSelection.text("Descripci") & h_font, curr_set],
                page_type="investments",
            ),
            PdfExtractPageClassifyStandard(
                header_sets=[
                    PdfLineSelection.text("Gestor de Inversiones y Gestora de Tesorería"),
                    PdfLineSelection.text("Presidente del Consejo de Administración de la Sociedad"),
                    PdfLineSelection.text("Gestores Delegados de Inversiones")
                ],
                page_type="manco",
            ),
            # Il formato classifica da sé, quindi la classe nuova si aggiunge **qui** e non in
            # `page_classify/args.csv`: scrivendocela si accenderebbe anche il classificatore
            # predefinito, e ogni pagina uscirebbe classificata due volte.
            #
            # Le due condizioni insieme escludono il combinato: il titolo del prospetto c'è su
            # tutt'e due, il nome del comparto solo sulle pagine che ne hanno uno.
            PdfExtractPageClassifyStandard(
                header_sets=[assets_statement_set, subfund_set],
                page_type="fund_assets",
            ),
        ),
        text_filter=TextFilterPageClassifyStandard(),
        deserialize=DeserializerPageClassifyStandard(),
    ),
    "investments": Pipeline(
        pdf_extract=(
            PdfExtractInvestmentsStandard(
                body_set=PdfLineSelection.area(0.0, 0.0, 1e6, 767.0) & h_font / PdfLineSelection.text("^ ")
            ),
            PdfExtractFundStandard(PdfLineSelection.area(0.0, 58.0, 1e6, 82.0) & h_font),
            PdfExtractCurrencyStandard(curr_set)
        )
    ),
    "fund_assets": Pipeline(
        pdf_extract=(
            PdfExtractFundStandard(subfund_set),
            PdfExtractCurrencyStandard(assets_currency_set),
            PdfExtractLabelledValueStandard(
                assets_date_set, ASSETS_DATE, "assets date"
            ),
            pdf_extract_tot_assets,
            pdf_extract_liabilities,
            pdf_extract_net_assets,
        ),
        text_filter=text_filter_fund_assets,
        deserialize=DeserializerAssetsStandard(to_int, to_date_with_es_month),
    ),
    "manco": Pipeline(
        pdf_extract=(
            PdfExtractManagmentCompanyStandard(
                PdfLineSelection.area_from_movewindow(
                    PdfLineSelection.text("Gestor de Inversiones y Gestora de Tesorería"),
                    (-0.1,0.8),2.0,1.4
                )
            ),
            pdf_extract_inv_managers
        ),
        text_filter=(TextFilterManagmentCompanyStandard(),text_filter_inv_managers),
        deserialize=(DeserializerManagmentCompanyStandard(),deserialize_inv_managers)
    )
}
