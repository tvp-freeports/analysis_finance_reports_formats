"""MEDIOLANUM-EN23: la societa' di gestione e il gestore, che sono la stessa societa'.

`C07` e `C19`. Prima di questo file il formato viveva interamente nei CSV — gli investimenti al
livello strutturato, e nient'altro — e questa e' la prima cosa che ha bisogno di Python: non per
l'estrazione, che e' la forma piu' semplice delle otto, ma per i **due avvisi** che la
nomenclatura di questo bilancio impone.

Pagina 3, prospetto `Management and Administration`, mette le etichette in corsivo grassetto da
9.98 e i valori in tondo, una riga sotto:

```
Alternative Investment Fund Manager and Global Distributor
Mediolanum International Funds Limited
4th Floor, The Exchange, George's Dock, IFSC
...
Cash Manager and Portfolio Manager
Mediolanum International Funds Limited
```

**Nessuna delle due etichette e' quella consueta.** Questo bilancio e' di un fondo alternativo
(SICAV-SIF), e il ruolo che gli altri bilanci chiamano `Management Company` qui si chiama
*Alternative Investment Fund Manager*; quello che gli altri chiamano `Investment Manager` si chiama
*Cash Manager and Portfolio Manager*. Le due cose sono assimilabili — l'ha detto l'utente, e con
un dubbio esplicito — quindi si estraggono, **e il motore dice che lo sta facendo**: un dato letto
sotto un'etichetta diversa da quella che lo definisce e' una deduzione, e una deduzione si
dichiara.

Le due etichette portano **lo stesso nome**, che e' il caso normale di `R15` visto da vicino: la
societa' di gestione gestisce anche gli investimenti, e lo dice il bilancio invece di lasciarlo
dedurre. Che la stessa societa' compaia nei due ruoli non e' un doppione (`R26`).

La ricetta e' quella del template — due etichette su una pagina, nessun comparto nominato — quindi
qui ci sono le ancore, i due avvisi, e nient'altro.
"""

import inv_managers
from freeports import log
from freeports.core import Pipeline
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.standard_funcs.deserialize import (
    DeserializerInvestmentsManagerStandard,
    DeserializerManagmentCompanyStandard,
)
from freeports.standard_funcs.pdf_extract import PdfExtractLabelledValueStandard
from freeports.utils.pdf_extract import LabelledValueWhere, PdfLineSelection

# Le etichette sono le sole righe in corsivo grassetto della pagina; i nomi e gli indirizzi sono in
# tondo, e il titolo del prospetto e' da 15.96. `BELOW` col collocamento per difetto prende la
# prima riga sotto, che e' il nome: le altre sono l'indirizzo.
_LABEL = PdfLineSelection(font="timesnewromanps-boldital", font_size=(9.5, 10.5))

pdf_extract_manco = PdfExtractLabelledValueStandard(
    _LABEL & PdfLineSelection.text("^Alternative Investment Fund Manager"),
    ResultStandardExtraction.MANAGEMENT_COMPANY.name,
    "managment company",
    where=LabelledValueWhere.BELOW,
)

pdf_extract_inv_managers = PdfExtractLabelledValueStandard(
    _LABEL & PdfLineSelection.text("^Cash Manager and Portfolio Manager"),
    ResultStandardExtraction.INVESTMENTS_MANAGER.name,
    "investments managers",
    where=LabelledValueWhere.BELOW,
)

_declared_together = inv_managers.declared_together()


def text_filter(pdf_blks, filter_data):
    """La ricetta del template, piu' i due avvisi sulla nomenclatura."""
    log.warn(
        "this report names no management company: the 'Alternative Investment Fund Manager and "
        "Global Distributor' is taken as one, because an alternative fund calls that role by that "
        "name - the report itself does not say the two are the same thing"
    )
    log.warn(
        "the investments manager is declared as 'Cash Manager and Portfolio Manager': the "
        "nomenclature is this report's own, and the role is read as the usual one"
    )
    return _declared_together(pdf_blks, filter_data)


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
