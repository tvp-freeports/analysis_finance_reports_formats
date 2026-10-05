"""Custom pdf filter for FINECO-EN23[IR] format"""

from freeports.standard_funcs.pdf_extract import (
    PdfExtractManagmentCompanyStandard
)
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict
from freeports.standard_funcs.deserialize import (
    DeserializerInvestmentsManagerStandard,
    DeserializerManagmentCompanyStandard,
)

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



# Il `text_filter` sta nel livello `semistructured`: la societa' di gestione con **tutti** i
# comparti (`R26`) e il residuo di quelli che nessuno ha preso. Il conto lo chiude questa pagina
# perche' e' l'ultima: la tabella di p155 ha gia' scritto le sue righe, e `already_assigned` dice
# quali comparti si e' presa. `funds_include_assigned` li fa entrare fra i comparti del documento
# anche quando nessun investimento li nomina, o le loro righe di `funds.csv` resterebbero senza
# societa' di gestione.
deserialize = DeserializerManagmentCompanyStandard()

deserialize_inv_manager = DeserializerInvestmentsManagerStandard()

