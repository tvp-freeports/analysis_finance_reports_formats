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

from freeports.core import PdfBlock
from freeports.standard_funcs.pdf_extract import (
    PdfExtractPageClassifyStandard,
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
    DeserializerPageClassifyStandard,
    DeserializerManagmentCompanyStandard,
    DeserializerInvestmentsManagerStandard,
)
from freeports.output import Fund
from freeports.core import Pipeline
import re

# Le due selezioni che il **classificatore** di questo formato usa ancora. Il carattere non e'
# scritto da nessuna parte: e' quello della testata della colonna, e `font_of` e' quel *quello*.
# Il portafoglio diceva le stesse tre cose e adesso le dice in `args/pdf_extract.yaml`, dove
# `font_of` e' una chiave della mappa.
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

# Il prospetto patrimoniale e' **tutto configurazione**: `fund` + `currency` + quattro
# `labelled_value` nel `pdf_extract`, `labelled_assets` nel `text_filter` e `assets` nel
# `deserialize`. Il titolo del comparto, la testata della colonna e le tre etichette dei totali
# stanno nei commenti di `args/pdf_extract.yaml`.
#
# Qui resta `assets_statement_set`, che serve al **classificatore** di questa stessa pagina.
assets_statement_set = PdfLineSelection.text("Estado del patrimonio neto")

# Il titolo del comparto, sotto quello del prospetto. Sul combinato al suo posto c'è `COMBINADO`,
# e il trattino è ciò che li distingue senza doverlo dire per nome. Lo usa il classificatore.
subfund_set = PdfLineSelection(font_size=(11.9, 12.1)) & PdfLineSelection.text("^GAMAX FUNDS - ")

# Il `text_filter` e il `deserialize` del prospetto sono del motore: `labelled_assets` riunisce i
# blocchi nudi che gli `A1` qui sotto lasciano e filtra sui comparti d'interesse, e `assets`
# costruisce la riga. Il prospetto sta su **una** pagina sola, quindi niente promesse.
#
# La data — `31 de diciembre de 2024`, il solo modo in cui questo formato la scrive — era una
# funzione di quindici righe qui dentro ed e' adesso la cella `date_cast: es_month`: il mese in
# parole e' la logica di un **tipo di dato**, non la forma di questo documento, e il motore ne
# aveva gia' tre lingue.


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
