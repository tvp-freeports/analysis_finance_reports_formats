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

# Il `text_filter` sta nel livello `semistructured`: la specificazione sta **sopra** e copre
# **tutte** le societa' che la seguono fino alla prossima, i marcatori si provano nell'ordine, e
# l'ombrello va messo davanti al comparto perche' la parentesi lo da' per sottinteso (`R24`).
deserialize = DeserializerInvestmentsManagerStandard()

deserialize_manco = DeserializerManagmentCompanyStandard()

deserialize_fund = DeserializerFundStandard()
