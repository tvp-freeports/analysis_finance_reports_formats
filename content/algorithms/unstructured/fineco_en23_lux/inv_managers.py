"""FINECO-EN23@LUX p6: la specificazione sta **sopra**, e copre le società che seguono.

`IM-4`, pagina aggiuntiva. La colonna `Investment Manager(s)` alterna una frase fra parentesi e
una o più società, e la frase vale per **tutte** quelle che la seguono fino alla prossima:

```
(Only in respect of the Sub-Fund MFS Prudent Capital FAM Fund)
MFS Investment Management Company (Lux) S.à r.l.      ← tutt'e tre
MFS International (U.K.) Limited
MFS Institutional Advisors Inc.
```

Due cose che la pagina impone e che sono parametri, non rami:

- i marcatori si provano **nell'ordine**, quindi `Only in respect of the Sub-Fund` prima di `Only
  in respect of`, o il comparto si chiamerebbe `the Sub-Fund Invesco Pan …`;
- la parentesi nomina il comparto **senza l'ombrello**, che sta nella testatina: `Invesco Pan
  European High Income FAM Fund` contro `CoRe Series Invesco Pan European High Income FAM Fund`
  degli investimenti. `R24` vuole il secondo, e `umbrella` è come si ottiene.

Il residuo è di `Fineco Asset Management DAC`, che questa pagina legge come società di gestione.
"""

import inv_managers
from freeports.utils.pdf_extract import (
    pdflines_from_pagedict,
    PdfLineSelection,
    get_groups,
)
from freeports.standard_funcs.pdf_extract import (
    PdfExtractManagmentCompanyStandard,
)
from freeports.core import PdfBlock
from freeports.standard_funcs.deserialize import (
    DeserializerFundStandard,
    DeserializerManagmentCompanyStandard,
    DeserializerInvestmentsManagerStandard
)
from freeports.utils.text_filter import fund_filter_data
from enum import Enum, auto


class BlockType(Enum):
    INV_MAN = auto()
    MANCO = auto()


def pdf_extract(page):
    lines = pdflines_from_pagedict(page)
    body = PdfLineSelection(
        font="arialnarrow", font_size=(10.9, 11.1), area=(315.0, 0.0, 1e6, 1e6)
    ).select(lines)
    groups=get_groups(body,20)
    return [
        PdfBlock(BlockType.INV_MAN.name, {"group": g}, b.text) for g, b in zip(groups, body)
    ]


pdf_extract_manco = PdfExtractManagmentCompanyStandard(
    PdfLineSelection.area_from_movewindow(
        PdfLineSelection(
            font="arialnarrow-bold",
            font_size=(10.9, 11.1),
            text="Management Company and Global Distributor ",
        ),
        (-0.2, 1.2),
        width_mult=1.8,
        height_mult=1.3,
    )
)


UMBRELLA = "CoRe Series"
"""L'ombrello, che la testatina di ogni pagina scrive e la specificazione dà per sottinteso."""

read = inv_managers.Adjacent(
    inv_managers.Parenthetical(
        markers=("Only in respect of the Sub-Fund ", "Only in respect of "),
        umbrella=UMBRELLA,
    ),
    where=inv_managers.Where.ABOVE,
    take=inv_managers.Take.ALL,
)


@fund_filter_data
def text_filter(pdf_blocks, funds):
    """I gestori delegati, il residuo alla societa' di gestione, e i comparti nuovi."""
    manco = next(
        (b for b in pdf_blocks if b.type_block != BlockType.INV_MAN.name), None
    )
    relevant = [b for b in pdf_blocks if b.type_block == BlockType.INV_MAN.name]
    assignment = inv_managers.assign(read(relevant), funds, manco=manco)
    blocks = list(inv_managers.text_blocks(assignment))
    if manco is not None:
        blocks.append(inv_managers.management_company_block(assignment, manco))
    return blocks


deserialize = DeserializerInvestmentsManagerStandard()

deserialize_manco = DeserializerManagmentCompanyStandard()

deserialize_fund = DeserializerFundStandard()
