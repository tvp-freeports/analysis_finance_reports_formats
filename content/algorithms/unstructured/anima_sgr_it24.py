"""Custom pipeline for ANIMA_SGR-IT24"""

from freeports.core import PdfBlock, TextBlock
import carryover
import sfdr

from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractCurrencyConstant,
    PdfExtractFundStandard,
    PdfExtractCurrencyStandard,
    PdfExtractLabelledValueStandard,
    PdfExtractPageClassifyStandard,
)
from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.standard_funcs.text_filter import (
    TextFilterAssetsStandard,
    TextFilterPageClassifyStandard,
)
from freeports.interfaces.text_blks import OneTextBlockType
from freeports.utils.text_filter import MatchFund
from freeports.standard_funcs.deserialize import (
    DeserializerAssetsStandard,
    DeserializerPageClassifyStandard,
)
from freeports.consts import Currency
from freeports.utils.deserialize import to_date_with_it_month, to_int
from freeports.utils.pdf_extract import (
    LabelledValueWhere,
    LabelledValueTake,
    PdfLineSelection,
    pdflines_from_pagedict,
    get_table_coordinates,
)
from freeports.core import Pipeline
from freeports.output import Fund, FundMerge
import re


h_font_selection = (
    PdfLineSelection.font("Lato,Bold")
    | PdfLineSelection.font("TrebuchetMS-Bold")
    | PdfLineSelection.font("Open Sans,Bold")
)
header_sets = [
    PdfLineSelection.text("Titoli") & h_font_selection,
    PdfLineSelection.text("Divisa") & h_font_selection,
]

s_font_selection = (
    PdfLineSelection.font("Lato")
    | PdfLineSelection.font("Open Sans")
    | PdfLineSelection.font("Lato-Regular")
)

manco_set = PdfLineSelection.text("di Gestione del Risparmio") & s_font_selection

subfund_set = (
    PdfLineSelection.area_from_bounds(x0=manco_set, y1=header_sets[0], x1=1e6, y0=0.0)
    & s_font_selection
)


currency_font = (
    PdfLineSelection.font("Lato,Bold")
    | PdfLineSelection.font("TrebuchetMS-Bold")
    | PdfLineSelection.font("Open Sans,Bold")
)

currency_set = (
    PdfLineSelection(text="Controvalore in ")
    & currency_font - PdfLineSelection(text="in $")
) | (
    PdfLineSelection.area_from_movewindow(
        PdfLineSelection(text="Controvalore in ") & currency_font,
        vec=(0.0, 1.0),
        width_mult=1.2,
        height_mult=1.2,
    )
    & currency_font
)

b_font_selection = (
    PdfLineSelection.font("Lato")
    | PdfLineSelection.font("TrebuchetMS")
    | PdfLineSelection.font("Open Sans")
)

# The listing is closed below as well as above. The section that follows it — the fund's
# "Ripartizione degli strumenti finanziari" summary — is set in the same font at the same size, so
# only its position tells the two apart; left unbounded, its much finer column grid is tabularised
# together with the holdings and pushes every field of every holding out of the column the format
# reads.
body_set = (
    PdfLineSelection.area_from_bounds(
        x0=0.0,
        x1=1e6,
        y0=PdfLineSelection(text="Elenco analitico", font_size=(11, 13))
        & b_font_selection,
        y1=PdfLineSelection(
            text="Ripartizione degli strumenti finanziari", font_size=(11, 13)
        )
        & b_font_selection,
    )
    & PdfLineSelection.font_size(6.8, 7.2)
    & b_font_selection
)


def pdf_extract_merges(page):
    lines=pdflines_from_pagedict(page)
    top=PdfLineSelection.area_from_bounds(x0=0.0,y0=PdfLineSelection.text("ONDO OGGETTO DI"),x1=1e6,y1=1e6)
    table=(PdfLineSelection.area_from_bounds(
        x0=0.0,y0=PdfLineSelection.text("ONDO OGGETTO DI"),x1=1e6,y1=top & PdfLineSelection.text("Il Consiglio di Amministrazione")
    ) & PdfLineSelection.font("latobolditalic")).select(lines)
    _,cols=zip(*get_table_coordinates(table))
    lines_old_name=[]
    lines_current_name=[]
    for c,f in zip(cols,table):
        text=f.text.strip()
        if c==0 and text not in lines_old_name:
            lines_old_name.append(text)
        elif c==1 and text not in lines_current_name:
            lines_current_name.append(text)
    old_name=" ".join(lines_old_name)
    current_name=" ".join(lines_current_name)
    body=(
        PdfLineSelection.area_from_movewindow(PdfLineSelection.text("di fusione"),(-0.5,-1.5),100.0,4.0) &
        b_font_selection
    ).select(lines)
    return [
        PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name,{
            "old_name": old_name,
            "current_name": current_name
        },"".join((b.text for b in body)))
    ]

date_regex=re.compile(".+ con efficacia a far data dal ([0-9]+ [a-z]+ [0-9]+)")
def text_filter_merges(pdf_blks,filter_data):
    funds=set(map(lambda x: MatchFund(x.name), filter(lambda x: isinstance(x,Fund),filter_data)))
    text=pdf_blks[0].content
    md={**pdf_blks[0].metadata}
    if MatchFund(md["current_name"]) not in funds:
        return []
    m=date_regex.match(text)
    md["date"]=m.group(1)
    return [
        TextBlock(OneTextBlockType.RELEVANT_BLOCK.name,md,pdf_blks[0])
    ]

def deserialize_merges(txt_blk):
    md=txt_blk.metadata
    return FundMerge(
        old_name=md["old_name"],
        current_name=md["current_name"],
        date=to_date_with_it_month(md["date"])
    )

header_sets_merges=[
    PdfLineSelection.text("ONDO OGGETTO DI") & h_font_selection,
    PdfLineSelection.text("ONDO RICEVENTE") & h_font_selection
]


# ----------------------------------------------------------------------------------------------
# La situazione patrimoniale, che sta su due pagine (`FA-2` e `FA-3`)
# ----------------------------------------------------------------------------------------------
# Centotre coppie su cinque documenti, e questo formato porta il caso che `R8` prevede: **lo stesso
# prospetto in quattro famiglie tipografiche**. Lato e Lato Bold nei due documenti grandi,
# Trebuchet nel secondo e nel quarto, Open Sans nel terzo, e il secondo e il quarto mescolano —
# testatine in Open Sans o in Lato, tabella in Trebuchet. Il carattere entra quindi come
# **unione di varianti**, che e' esattamente cio' che `R8` autorizza, e il resto della ricetta non
# cambia di una riga.
#
# Il nome del comparto sta nella testatina in alto a destra, tranne nel quarto documento, dove la
# riga e' una sola e comincia con la societa' di gestione. Quel documento pero' porta **un fondo
# solo**, quindi `carryover.sole_fund` risponde, e lo dichiara come valore imposto (`R3`).

TOT_ASSETS = "TOT_ASSETS"
LIABILITIES = "LIABILITIES"
NET_ASSETS = "NET_ASSETS"
ASSETS_DATE = "ASSETS_DATE"
FUND_NAME = "FUND_NAME"

assets_bold_set = (
    PdfLineSelection.font("LatoBold")
    | PdfLineSelection.font("TrebuchetMS-Bold")
    | PdfLineSelection.font("Open-SansBold")
) & PdfLineSelection(font_size=(6.9, 7.1))

assets_body_set = (
    PdfLineSelection.font("Lato")
    | PdfLineSelection.font("TrebuchetMS")
    | PdfLineSelection.font("Open-Sans")
) & PdfLineSelection(font_size=(6.9, 7.1))

# La testatina in alto a destra. Il prefisso d'ombrello e' l'ancora: nella stessa area il quarto
# documento ha solo uno spazio, che senza il prefisso diventerebbe il nome del comparto.
assets_fund_set = PdfLineSelection(text="^ANIMA") & PdfLineSelection(
    area=(300.0, 20.0, 1e6, 50.0)
)

# `R5`: l'esercizio corrente e' cio' che sta a sinistra dell'intestazione dell'esercizio
# precedente, meno le percentuali, che sono le sole a portare il segno.
current_year = PdfLineSelection.area_from_bounds(
    0.0, 0.0, PdfLineSelection(text="^Situazione a fine"), 1e6
) - PdfLineSelection(text="%")

assets_carryover = carryover.Carryover("tot_assets")

pdf_extract_assets_fund = PdfExtractLabelledValueStandard(
    assets_fund_set, FUND_NAME, "fund", take=LabelledValueTake.ALL
)

pdf_extract_tot_assets = PdfExtractLabelledValueStandard(
    assets_bold_set & PdfLineSelection(text="^TOTALE ATTIVITA'"),
    TOT_ASSETS,
    "tot_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year,
)

pdf_extract_liabilities = PdfExtractLabelledValueStandard(
    assets_bold_set & PdfLineSelection(text="^TOTALE PASSIVITA'"),
    LIABILITIES,
    "liabilities",
    where=LabelledValueWhere.RIGHT,
    value=current_year,
)

# `CLASSE AM`, `CLASSE FM`, `CLASSE IM`: il netto delle classi di quote, non quello del fondo.
pdf_extract_net_assets = PdfExtractLabelledValueStandard(
    (assets_bold_set & PdfLineSelection(text="^VALORE COMPLESSIVO NETTO DEL FONDO"))
    - PdfLineSelection(text="CLASSE"),
    NET_ASSETS,
    "net_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year,
)

pdf_extract_assets_date = PdfExtractLabelledValueStandard(
    assets_body_set & PdfLineSelection(text="^Situazione al"),
    ASSETS_DATE,
    "assets date",
    where=LabelledValueWhere.BELOW,
)

record_begin = carryover.Record(
    fund=FUND_NAME, currency="CURRENCY_STATEMENT", tot_assets=TOT_ASSETS
)

record_end = carryover.Record(
    fund=FUND_NAME,
    currency="CURRENCY_STATEMENT",
    date=ASSETS_DATE,
    liabilities=LIABILITIES,
    net_assets=NET_ASSETS,
)

assets_filter = TextFilterAssetsStandard()


def _fund_the_page_does_not_name(pdf_blks, filter_data):
    """Il ripiego per il documento a un fondo solo, chiesto **solo** quando serve davvero."""
    if any(blk.type_block == FUND_NAME for blk in pdf_blks):
        return None
    name = carryover.sole_fund(filter_data)
    return {"fund": name} if name else None


def text_filter_fund_assets_begin(pdf_blks, filter_data):
    """La prima delle due pagine: un prospetto solo, filtrato sui fondi d'interesse."""
    also = _fund_the_page_does_not_name(pdf_blks, filter_data)
    return assets_filter(record_begin(pdf_blks, also=also), filter_data)


def text_filter_fund_assets_end(pdf_blks, filter_data):
    """La seconda: il filtro **prima** e la promessa **dopo**."""
    also = _fund_the_page_does_not_name(pdf_blks, filter_data)
    blocks = assets_filter(record_end(pdf_blks, also=also), filter_data)
    return assets_carryover.resume(blocks, filter_data)


pipelines = {
    "": Pipeline(
        pdf_extract=(
            PdfExtractPageClassifyStandard(
                header_sets=header_sets, page_type="investments"
            ),
            PdfExtractPageClassifyStandard(
                header_sets=header_sets_merges, page_type="merges"
            ),
            PdfExtractPageClassifyStandard(
                header_sets=PdfLineSelection.text("aveva un obiettivo di investimento sostenibile"),page_type="sfdr_classification"
            ),
            # Senza carattere: le quattro famiglie tipografiche del formato non si scrivono in un
            # insieme solo, e la congiunzione delle due etichette basta da se'.
            PdfExtractPageClassifyStandard(
                header_sets=[
                    PdfLineSelection.text("^SITUAZIONE PATRIMONIALE"),
                    PdfLineSelection.text("^TOTALE ATTIVITA'"),
                ],
                page_type="fund_assets_begin",
            ),
            PdfExtractPageClassifyStandard(
                header_sets=[
                    PdfLineSelection.text("^PASSIVITA' E NETTO"),
                    PdfLineSelection.text("^TOTALE PASSIVITA'"),
                ],
                page_type="fund_assets_end",
            ),
        ),
        text_filter=TextFilterPageClassifyStandard(),
        deserialize=DeserializerPageClassifyStandard(),
    ),
    "fund_assets_begin": Pipeline(
        pdf_extract=(
            pdf_extract_assets_fund,
            PdfExtractCurrencyConstant(Currency.EUR),
            pdf_extract_tot_assets,
        ),
        text_filter=text_filter_fund_assets_begin,
        deserialize=assets_carryover.deposit,
    ),
    "fund_assets_end": Pipeline(
        pdf_extract=(
            pdf_extract_assets_fund,
            PdfExtractCurrencyConstant(Currency.EUR),
            pdf_extract_assets_date,
            pdf_extract_liabilities,
            pdf_extract_net_assets,
        ),
        text_filter=text_filter_fund_assets_end,
        deserialize=DeserializerAssetsStandard(to_int),
    ),
    "investments": Pipeline(
        pdf_extract=(
            PdfExtractInvestmentsStandard(body_set=body_set,manco_set=manco_set),
            PdfExtractFundStandard(subfund_set),
            PdfExtractCurrencyStandard(currency_set)
        )
    ),
    # Il segno e' una `X` di testo, e su quasi tutti i moduli e' **fusa nella riga
    # dell'etichetta** (`Si'` / `X No`): per questo le etichette si ancorano anche in coda.
    "sfdr_classification": sfdr.ITALIAN.pipeline(),
    "merges": Pipeline(pdf_extract_merges,text_filter_merges,deserialize_merges)
}
