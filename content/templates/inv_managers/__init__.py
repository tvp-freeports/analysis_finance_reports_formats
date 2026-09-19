"""`A5` — il solo assegnatore dei gestori degli investimenti.

Un bilancio dichiara le **eccezioni** e tace il resto: il residuo è di chi la pagina non nomina.
Questo pacchetto è il posto — uno solo — dove quel residuo si calcola, con le sette regole di
`R6`+`R15`+`R21`+`R22` scritte in `assignment.py` e i blocchi che ne escono in `blocks.py`.

`reading.py` sta dall'altra parte: **costruisce** quelle coppie leggendo i blocchi della pagina,
in una delle forme in cui i bilanci le scrivono. Un `text_filter` completo somiglia a questo:

```python
import inv_managers
from freeports.utils.text_filter import investment_fund_filter_data

read = inv_managers.Adjacent(inv_managers.Parenthetical(markers=("for the Sub-Funds",)))

@investment_fund_filter_data
def text_filter(blocks, funds):
    assignment = inv_managers.assign(read(blocks), funds, manco="Acme SGR S.p.A.")
    return inv_managers.text_blocks(assignment)
```

Il decoratore è del motore e sostituisce il `filter_data` con l'insieme dei fondi che gli
investimenti hanno visto — scritti come li scrivono loro, che è quanto `R24` chiede.
"""

from .assignment import (
    Assigned,
    Assignment,
    Declared,
    assign,
    assigned_funds,
    fund_set,
)
from .blocks import management_company_block, text_blocks
from .reading import (
    Adjacent,
    ConnectorLine,
    Listing,
    Parenthetical,
    Table,
    Take,
    Where,
)

__all__ = [
    "Adjacent",
    "Assigned",
    "Assignment",
    "Declared",
    "ConnectorLine",
    "Listing",
    "Parenthetical",
    "Table",
    "Take",
    "Where",
    "assign",
    "assigned_funds",
    "fund_set",
    "management_company_block",
    "text_blocks",
]
