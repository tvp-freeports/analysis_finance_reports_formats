"""Custom pdf filter for FINECO-EN23[IR] format"""

from freeports.standard_funcs.pdf_extract import PdfExtractInvestmentsStandard, PdfExtractFundStandard
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict, get_table_coordinates
from freeports.utils.text_filter import normalize_string, MatchFund
from freeports.interfaces.text_blks import ResultStandardFiltering
from freeports.standard_funcs.deserialize import DeserializerFundStandard
from freeports.core import PdfBlock,TextBlock, Pipeline
from freeports.output import Investment, InvestmentsManager
from enum import Enum,auto



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


def text_extract(blks,filter_data):
    filter_funds = set(MatchFund(name=n.fund) for n in filter(lambda x: isinstance(x,Investment),filter_data))
    funds = [b.content for b in blks if b.metadata["table-col"]==0]
    inv_man = [b.content for b in blks if b.metadata["table-col"]==2]
    inv_managers={}
    for f,i in zip(funds,inv_man):
        if i not in inv_managers:
            inv_managers[i]=[f]
        else:
            inv_managers[i].append(f)
    res = []
    for i,ifunds in inv_managers.items():
        obj_ifunds=set(MatchFund(name=f) for f in ifunds)
        if not obj_ifunds.isdisjoint(filter_funds):
            res.append(
                TextBlock.from_content(BlockType.INV_MAN.name,{"funds": set(ifunds)},i)
            )
            for f in obj_ifunds-filter_funds:
                res.append(TextBlock.from_content(ResultStandardFiltering.FUND.name,{},f.name))
    return res



def deserialize(blk):
    if blk.type_block == BlockType.INV_MAN.name:
        return InvestmentsManager(
            name=blk.content,
            managed_funds=blk.metadata["funds"]
        )


deserialize_fund = DeserializerFundStandard()
