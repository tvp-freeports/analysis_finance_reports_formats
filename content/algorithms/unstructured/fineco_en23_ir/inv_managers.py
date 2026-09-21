"""FINECO-EN23@IR p155: una riga per comparto, e il gestore in una colonna.

`IM-7`. La tabella `Date of Commencement` elenca trentacinque comparti con la data di avvio e il
gestore, e lo stesso gestore torna su molte righe: le colonne le scopre il `pdf_extract`
(`get_table_coordinates`), e la lettura dice soltanto **quali** delle tre servono.

Il residuo non si decide qui (`settle=False`): la tabella nomina solo i comparti che un delegato
ha, e ciò che resta è della società di gestione, che sta su un'altra pagina — `managment_company`
chiude il conto leggendo da `assigned_funds` ciò che questa pagina ha già preso.
"""

from freeports.standard_funcs.pdf_extract import PdfExtractInvestmentsStandard, PdfExtractFundStandard
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict, get_table_coordinates
from freeports.utils.text_filter import investment_fund_filter_data
from freeports.standard_funcs.deserialize import (
    DeserializerFundStandard,
    DeserializerInvestmentsManagerStandard,
)
from freeports.core import PdfBlock
from enum import Enum,auto

import inv_managers



class BlockType(Enum):
    MANCO = auto()
    INV_MAN = auto()


def pdf_filter(page):
    lines=pdflines_from_pagedict(page)
    s=(PdfLineSelection(font="timesnewroman",font_size=(10.0,10.1)) & PdfLineSelection.area_from_bounds(
        x0=0.0,
        y0=PdfLineSelection(font="timesnewromanbold",font_size=(10.0,10.1),text="Date of Commencement"),
        x1=1e6,
        y1=520.0
    )).select(lines)
    coord=get_table_coordinates(s)
    blks=[PdfBlock(BlockType.INV_MAN.name,{"table-row":cs[0],"table-col":cs[1]},l.text) for cs,l in zip(coord,s)]
    return blks



read = inv_managers.Table(fund_col=0, manager_col=2)


@investment_fund_filter_data
def text_extract(blks, funds):
    """I gestori della tabella, e i comparti che il job non aveva ancora visto."""
    assignment = inv_managers.assign(read(blks), funds, settle=False)
    return inv_managers.text_blocks(assignment)


deserialize = DeserializerInvestmentsManagerStandard()

deserialize_fund = DeserializerFundStandard()
