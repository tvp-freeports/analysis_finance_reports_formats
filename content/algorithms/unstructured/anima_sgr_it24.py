"""ANIMA_SGR-IT24: gli attivi a cavallo di due pagine, la societa' di gestione, e `EI-4`.

`EI-4` e' la ricetta in cui il modulo periodico risponde alla domanda sugli indicatori **con
sola prosa**: p1726 scrive quattro righe di discorso e nessuna misura, e la lettura giusta e' non
estrarre niente (`R11`). Non e' un ramo del template ESG ma la sua regola generale applicata —
un indicatore senza numero non esiste — e per questo la pipeline e' la stessa che leggerebbe un
elenco di percentuali.
"""

from freeports.core import PdfBlock, TextBlock

from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractFundStandard,
    PdfExtractCurrencyStandard,
)
from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.interfaces.text_blks import OneTextBlockType
from freeports.utils.text_filter import MatchFund
from freeports.utils.deserialize import to_date_with_it_month
from freeports.utils.pdf_extract import (
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
# solo**, quindi la cella `fund: sole_if_absent` risponde, e lo dichiara come valore imposto
# (`R3`).

# I due prospetti patrimoniali (`FA-2` e `FA-3`) e la `manco` sono **tutti configurazione**: la
# testatina del comparto, le ascisse delle colonne e la sottrazione delle classi di quote stanno nei
# commenti di `args/pdf_extract.yaml`, e il ritaglio del nome della societa' di gestione e'
# l'`after` dell'algoritmo `manco`.


# La sezione degli indicatori ESG e' configurazione: `section` nel `pdf_extract`. Il glossario del
# modello europeo sta nella colonna di sinistra e in ordine di lettura si intreccia col corpo: a
# lasciarlo fuori sono il carattere del corpo e l'**ascissa**, che e' geometria e sta nella cella.

pipelines = {
    "investments": Pipeline(
        pdf_extract=(
            PdfExtractInvestmentsStandard(body_set=body_set,manco_set=manco_set),
            PdfExtractFundStandard(subfund_set),
            PdfExtractCurrencyStandard(currency_set)
        )
    ),
    # Il segno e' una `X` di testo, e su quasi tutti i moduli e' **fusa nella riga
    # dell'etichetta** (`Si'` / `X No`): per questo le etichette si ancorano anche in coda.
    "merges": Pipeline(pdf_extract_merges,text_filter_merges,deserialize_merges),
}
