from freeports.standard_funcs.pdf_extract import (
    PdfExtractManagmentCompanyStandard
)
from freeports.utils.pdf_extract import (
    pdflines_from_pagedict,
    PdfLineSelection
)
from freeports.core import PdfBlock
from freeports.standard_funcs.text_filter import TextFilterManagmentCompanyStandard
from freeports.standard_funcs.deserialize import (
    DeserializerFundStandard,
    DeserializerManagmentCompanyStandard,
    DeserializerInvestmentsManagerStandard
)


import logging
from enum import Enum, auto

logger = logging.getLogger(__name__)

class TipiBlocco(Enum):
    INV = auto()
    MAN = auto()
    SUB = auto()
    ALT_INV = auto()
    NOTE = auto()



def _blocks(lines, managers, funds, notes=None):
    """I blocchi nell'ordine in cui la pagina li scrive: nome, righe secondarie, specificazione.

    Le selezioni si fondono e si riordinano per ordinata perche' e' l'adiacenza a legare un
    gestore ai suoi comparti: tenendo prima tutti i nomi e poi tutte le specificazioni, come
    faceva la lettura scritta a mano, il legame lo ricostruirebbe la **posizione** nelle due liste,
    che e' giusta finche' le due liste hanno la stessa lunghezza e sbagliata appena una voce non
    porta la sua parentesi.

    `notes` e' il tondo chiaro, cioe' l'indirizzo e la qualificazione temporale. Sono righe che
    il lettore non deve scambiare per nomi, e portarle serve perche' una di esse dice che il
    gestore **non e' piu' in carica** (p10: `(until 10th of May 2023)`).
    """
    selected = [(line, TipiBlocco.INV.name) for line in managers.select(lines)]
    selected += [(line, TipiBlocco.SUB.name) for line in funds.select(lines)]
    if notes is not None:
        selected += [(line, TipiBlocco.NOTE.name) for line in notes.select(lines)]
    selected.sort(key=lambda pair: pair[0].bbox[1])
    return [PdfBlock(type_block, {}, line.text) for line, type_block in selected]


def pdf_extract_inv_managers_begin(page):

    lines = pdflines_from_pagedict(page)
    condition_text = PdfLineSelection(
        text="INVESTMENT MANAGERS", font="frutiger-lightitalic"
    )
    end=PdfLineSelection(
        text="INDEPENDENT AUDITOR OF THE INVESTMENT FUND AND OF THE MANAGEMENT COMPANY",
        font="frutiger-lightitalic",
    ).select(lines)
    btm=1e6
    if end:
        btm=end[0].bbox[1]
    bold_text = PdfLineSelection(
        font="frutiger-black", font_size=(8.98, 8.99)
    ) & PdfLineSelection.area_from_bounds(x0=0, y0=condition_text, x1=1e6, y1=btm)
    fund_text = PdfLineSelection(
        font="frutiger-lightitalic", font_size=(8.98, 8.99)
    ) & PdfLineSelection.area_from_bounds(x0=0, y0=condition_text, x1=1e6, y1=btm)
    note_text = PdfLineSelection(
        font="frutiger-light", font_size=(8.98, 8.99)
    ) & PdfLineSelection.area_from_bounds(x0=0, y0=condition_text, x1=1e6, y1=btm)

    return _blocks(lines, bold_text, fund_text, note_text)

# def pdf_extract_inv_managers_begin_alt(lines):
#     condition_text = PdfLineSelection(
#         text="INVESTMENT MANAGERS", font="frutiger-lightitalic"
#     )

#     bold_text = PdfLineSelection(
#         font="frutiger-black", font_size=(8.98, 8.99)
#     ) & PdfLineSelection.area_from_bounds(x0=0, y0=condition_text, x1=1e6, y1=1e6)

#     funds = ((
#         PdfLineSelection.area_from_bounds(
#             x0=0.0,y0=PdfLineSelection.text("This function has been delegated by"),x1=1e6,y1=1e6
#         ) / PdfLineSelection.area_from_movewindow(
#             bold_text & PdfLineSelection.area_from_bounds(
#                 x0=0.0,
#                 y0=PdfLineSelection.text("This function has been delegated by"),
#                 x1=1e6,
#                 y1=1e6
#             ),(-0.1,0.0),1.0,4.0
#         )
#     ) & PdfLineSelection.font_size(8.9,9.0)).select(lines)

#     return [

#     ]



def pdf_extract_inv_managers(page):

    lines = pdflines_from_pagedict(page)

    bold_text = PdfLineSelection(font="frutiger-black", font_size=(8.98, 8.99))
    fund_text = PdfLineSelection(font="frutiger-lightitalic", font_size=(8.98, 8.99))
    note_text = PdfLineSelection(font="frutiger-light", font_size=(8.98, 8.99))

    return _blocks(lines, bold_text, fund_text, note_text)


def pdf_extract_inv_managers_end(page):

    lines = pdflines_from_pagedict(page)
    condition_text = PdfLineSelection(
        text="INDEPENDENT AUDITOR OF THE INVESTMENT FUND AND OF THE MANAGEMENT COMPANY",
        font="frutiger-lightitalic",
    )

    bold_text = PdfLineSelection(
        font="frutiger-black", font_size=(8.98, 8.99)
    ) & PdfLineSelection.area_from_bounds(x0=0, y0=0, x1=1e6, y1=condition_text)
    fund_text = PdfLineSelection(
        font="frutiger-lightitalic", font_size=(8.98, 8.99)
    ) & PdfLineSelection.area_from_bounds(x0=0, y0=0, x1=1e6, y1=condition_text)
    note_text = PdfLineSelection(
        font="frutiger-light", font_size=(8.98, 8.99)
    ) & PdfLineSelection.area_from_bounds(x0=0, y0=0, x1=1e6, y1=condition_text)

    return _blocks(lines, bold_text, fund_text, note_text)

pdf_extract_manco = PdfExtractManagmentCompanyStandard(
    PdfLineSelection(
        font="frutiger-black", font_size=(8.98, 8.99)
    ) & PdfLineSelection.area_from_bounds(
        x0=0,
        y0=PdfLineSelection(
            text="MANAGEMENT COMPANY AND PROMOTER", font="frutiger-lightitalic"
        ),
        x1=1e6,
        y1=PdfLineSelection(
            text="BOARD OF DIRECTORS OF THE MANAGEMENT COMPANY",
            font="frutiger-lightitalic",
        ),
    )
)

# I tre `text_filter` dei gestori stanno nel livello `semistructured`. La specificazione sta
# **sotto** il nome e la riconosce il tipo di blocco, non la parentesi; i marcatori si provano
# nell'ordine, quindi il plurale per primo. La prima parentesi di p9 non ne porta nessuno — dice
# *quando* Eurizon Capital S.A. e' subentrata, non *che cosa* gestisce — e per questo quel gestore
# resta **senza comparti dichiarati**, cioe' quello a cui tocca il residuo.
#
# `retired` toglie il gestore uscente: p10 scrive `Eurizon Capital Asia Limited` e sotto `(until
# 10th of May 2023)`, e la sua parentesi rivendica `Eurizon Fund - Equity China A` e `Eurizon Fund -
# Asian Equity Opportunities`; p9 dice degli stessi due comparti che *are managed by Eurizon Capital
# S.A. as from 10 May 2023*. Si estrae chi e' in carica alla chiusura, come per la societa' di
# gestione: la dichiarazione uscente non esce, e i suoi due comparti tornano nel residuo.
#
# p9 e' la sola che chiude il conto, e lo schedule la processa **per ultima**: le righe si accumulano
# in uno step e il flag lo chiude *dopo* averle incluse, quindi `inv_managers_end` e `inv_managers`
# stanno nello step prima e `inv_managers_begin` da sola in quello dopo. Non e' un capriccio: il
# gestore che prende il residuo e' dichiarato li', e il residuo si sa solo quando tutte le altre
# pagine hanno rivendicato il loro.
text_filter_manco = TextFilterManagmentCompanyStandard()

deserialize_inv_managers = DeserializerInvestmentsManagerStandard()

deserialize_manco = DeserializerManagmentCompanyStandard()

deserialize_fund = DeserializerFundStandard()
