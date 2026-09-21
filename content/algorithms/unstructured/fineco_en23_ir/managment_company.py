"""Custom pdf filter for FINECO-EN23[IR] format"""

from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard, PdfExtractFundStandard, PdfExtractManagmentCompanyStandard
)
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict, get_table_coordinates
from freeports.interfaces.text_blks import ResultStandardFiltering, StandardManagmentCompanyTextBlock
from freeports.standard_funcs.deserialize import (
    DeserializerInvestmentsManagerStandard,
    DeserializerManagmentCompanyStandard,
)

import inv_managers
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



def text_extract(blks, filter_data):
    """La societa' di gestione con tutti i comparti, e il residuo di quelli che nessuno ha preso.

    Il conto lo chiude questa pagina perche' e' l'ultima: la tabella di p155 ha gia' scritto le
    sue righe, e `assigned_funds` dice quali comparti si e' presa. `R26` vuole la societa' di
    gestione uno a molti su **tutto** il documento e i gestori molti a molti sul resto, ed e'
    per questo che lo stesso nome compare in tutt'e due i ruoli senza essere un doppione.
    """
    if not blks:
        return []
    assigned = inv_managers.assigned_funds(filter_data)
    funds = inv_managers.fund_set(
        n.fund for n in filter(lambda x: isinstance(x, Investment), filter_data)
    )
    # I comparti della tabella di p155 entrano fra quelli del documento anche quando nessun
    # investimento li nomina: la `manco` risponde di **tutti** (`R26`), e senza questa unione le
    # loro righe di `funds.csv` resterebbero senza societa' di gestione.
    assignment = inv_managers.assign(
        [], funds | assigned, manco=blks[0], already_assigned=assigned
    )
    return [
        inv_managers.management_company_block(assignment, blks[0]),
        *inv_managers.text_blocks(assignment),
    ]


deserialize = DeserializerManagmentCompanyStandard()

deserialize_inv_manager = DeserializerInvestmentsManagerStandard()

