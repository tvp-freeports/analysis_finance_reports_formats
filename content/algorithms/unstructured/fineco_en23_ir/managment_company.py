"""Custom pdf filter for FINECO-EN23[IR] format"""

from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard, PdfExtractFundStandard, PdfExtractManagmentCompanyStandard
)
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict, get_table_coordinates
from freeports.interfaces.text_blks import ResultStandardFiltering, StandardManagmentCompanyTextBlock
from freeports.standard_funcs.deserialize import DeserializerManagmentCompanyStandard
from freeports.core import PdfBlock,TextBlock,Pipeline
from freeports.output import Investment, InvestmentsManager
from freeports.utils.text_filter import MatchFund
from enum import Enum,auto



class BlockType(Enum):
    INV_MAN = auto()


# "Directors and Other Information" is a column of bold section headings down the left margin, with
# each section's text beside it.  The management company is the one headed "Manager", and it runs
# down to whatever heading comes next: "Investment Manager & Investment Advisor" in the FAM Series
# reports, but "Distributor" in the FAM Evolution ones, which name no investment manager at all.
# So the end of the section is read from the layout rather than from a heading known in advance.
section_headings = PdfLineSelection(font="timesnewromanbold", area=(0.0, 0.0, 200.0, 1e6))
manager_heading = PdfLineSelection(font="timesnewromanbold", text="^Manager")


def pdf_filter(page):
    lines = pdflines_from_pagedict(page)
    manager = manager_heading.select(lines)
    if not manager:
        return []
    t = min(line.bbox[1] for line in manager)
    below = [line.bbox[1] for line in section_headings.select(lines) if line.bbox[1] > t]
    if not below:
        return []
    std_pdf_filter = PdfExtractManagmentCompanyStandard(PdfLineSelection(font="timesnewroman",area=(0.0,t-10.0,1e6,min(below))))
    return std_pdf_filter(page)



def text_extract(blks,filter_data):
    inv_funds = set(MatchFund(name=n.fund) for n in filter(lambda x: isinstance(x,Investment),filter_data))
    a_funds = set(MatchFund(name=n) for inv in filter(lambda x: isinstance(x,InvestmentsManager),filter_data) for n in inv.managed_funds)
    return [
        StandardManagmentCompanyTextBlock(blks[0],inv_funds.union(a_funds)),
        TextBlock.from_content(BlockType.INV_MAN.name,{"funds": set(f.name for f in (inv_funds-a_funds))},blks[0].content)
    ]


deserialize = DeserializerManagmentCompanyStandard()

