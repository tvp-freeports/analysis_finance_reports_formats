"""Custom pdf filter for FINECO-EN23[IR] format"""

from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard, PdfExtractFundStandard, PdfExtractManagmentCompanyStandard
)
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict, get_table_coordinates
from freeports.interfaces.text_blks import ResultStandardFiltering, StandardManagmentCompanyTextBlock
from freeports.standard_funcs.deserialize import DeserializerManagmentCompanyStandard
from freeports.core import PdfBlock,TextBlock,Pipeline
from freeports._internals.output.classes_schema import Interest,InvestmentsManager
from freeports.utils.text_filter import MatchFund
from enum import Enum,auto



class BlockType(Enum):
    INV_MAN = auto()


def pdf_filter(page):
    lines = pdflines_from_pagedict(page)
    b=PdfLineSelection(font="timesnewromanbold",text="Investment Manager").select(lines)[0].bbox[1]
    t=PdfLineSelection(font="timesnewromanbold",text="^Manager").select(lines)[0].bbox[1]-10.0
    std_pdf_filter = PdfExtractManagmentCompanyStandard(PdfLineSelection(font="timesnewroman",area=(0.0,t,1e6,b)))
    return std_pdf_filter(page)



def text_extract(blks,filter_data):
    inv_funds = set(MatchFund(name=n.fund) for n in filter(lambda x: isinstance(x,Investment),filter_data))
    a_funds = set(MatchFund(name=n) for inv in filter(lambda x: isinstance(x,InvestmentsManager),filter_data) for n in inv.managed_funds)
    return [
        StandardManagmentCompanyTextBlock(blks[0],inv_funds.union(a_funds)),
        TextBlock.from_content(BlockType.INV_MAN,{"funds": set(f.name for f in (inv_funds-a_funds))},blks[0].content)
    ]


deserialize = DeserializerManagmentCompanyStandard()

