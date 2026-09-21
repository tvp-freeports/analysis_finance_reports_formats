"""ASTERIA-EN23: il prospetto `Management and Administration`, che dichiara **un** gestore.

`IM-1`, più la pagina aggiuntiva di `MC-1`. Pagina 3 mette le due etichette in due colonne, e
sotto ciascuna il nome:

```
Registered Office of the SICAV:        Investment Manager and Global Distributor:
Centre Etoile,                         Asteria Obviam SA
…                                      15, rue de Lausanne
Management Company:                    …
Waystone Management Company (Lux) S.A.
```

La ricetta è la più semplice delle otto: **un gestore, e nessun elenco di comparti**. `R15` dice
che allora il residuo è tutto suo, e alla società di gestione resta il solo ruolo di `manco` —
ed è per questo che `assign` riceve la `manco` ma non la mette fra i gestori.

Le due letture stanno sulla **stessa pagina**, quindi non c'è nessuna promessa da depositare: un
`text_filter` riceve i blocchi di tutt'e due i `pdf_extract` e li unisce lì.
"""

import inv_managers
import manco
from freeports.core import Pipeline
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.standard_funcs.deserialize import (
    DeserializerInvestmentsManagerStandard,
    DeserializerManagmentCompanyStandard,
)
from freeports.standard_funcs.pdf_extract import PdfExtractLabelledValueStandard
from freeports.utils.pdf_extract import LabelledValueWhere, PdfLineSelection
from freeports.utils.text_filter import investment_fund_filter_data

# Le etichette sono le sole righe in grassetto da 9.98: il titolo della pagina è 13.97 e i nomi
# sono in tondo. `BELOW` con il collocamento per difetto prende la **prima** riga sotto, che è il
# nome; la seconda è l'indirizzo, e non la si vuole.
_LABEL = PdfLineSelection(font="centurygothic-bold", font_size=(9.5, 10.5))

pdf_extract_manco = PdfExtractLabelledValueStandard(
    _LABEL & PdfLineSelection.text("^Management Company:"),
    ResultStandardExtraction.MANAGEMENT_COMPANY.name,
    "managment company",
    where=LabelledValueWhere.BELOW,
)

pdf_extract_inv_managers = PdfExtractLabelledValueStandard(
    _LABEL & PdfLineSelection.text("^Investment Manager and Global Distributor:"),
    ResultStandardExtraction.INVESTMENTS_MANAGER.name,
    "investments managers",
    where=LabelledValueWhere.BELOW,
)


@investment_fund_filter_data
def text_filter(pdf_blks, funds):
    """Il gestore unico, i comparti che gli toccano, e la società di gestione con tutti."""
    manco_block = manco.first(
        [b for b in pdf_blks if b.type_block == ResultStandardExtraction.MANAGEMENT_COMPANY.name]
    )
    assignment = inv_managers.assign(
        inv_managers.Named()(
            b for b in pdf_blks
            if b.type_block == ResultStandardExtraction.INVESTMENTS_MANAGER.name
        ),
        funds,
        manco=manco_block,
    )
    blocks = list(inv_managers.text_blocks(assignment))
    if manco_block is not None:
        blocks.append(inv_managers.management_company_block(assignment, manco_block))
    return blocks


pipelines = {
    "inv_managers": Pipeline(
        (pdf_extract_manco, pdf_extract_inv_managers),
        text_filter,
        (
            DeserializerInvestmentsManagerStandard(),
            DeserializerManagmentCompanyStandard(),
        ),
    ),
}
