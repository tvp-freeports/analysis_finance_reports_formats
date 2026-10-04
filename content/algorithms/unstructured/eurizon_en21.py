"""EURIZON-EN21: la società di gestione, e le due che il bilancio nomina.

`MC-4`. Il 2021 è l'anno in cui Pramerica è diventata Eurizon, e il prospetto `Management and
Administration` di pagina 7 nomina **tutt'e due** le società, ciascuna col suo periodo fra
parentesi:

```
Management Company:
Pramerica Management Company S.A. (until June 30, 2021)
37/A, Avenue J.F. Kennedy
L-1855 Luxembourg
Eurizon Capital S.A. (since July 1, 2021)
```

Si estrae **quella in carica alla chiusura**, ed è la regola `U6` del template `manco`. Le due righe
d'indirizzo non concorrono: a dividerle dai nomi non è la geometria — un indirizzo sta sotto il suo
nome esattamente come ci sta il nome successivo — ma la parentesi, che solo i nomi portano.
"""

from freeports.core import Pipeline
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.standard_funcs.pdf_extract import PdfExtractLabelledValueStandard
from freeports.utils.pdf_extract import (
    LabelledValueTake,
    LabelledValueWhere,
    PdfLineSelection,
)

# L'etichetta e' in grassetto e i valori no: e' il grassetto che chiude la sezione, perche' sotto
# l'ultimo indirizzo viene `Cabinet de Revision Agree:` e poi i revisori, che portano anche loro una
# qualificazione temporale e sceglierebbero al posto nostro.
label = PdfLineSelection(font="arialmt-bold", text="^Management Company:")
next_label = PdfLineSelection.font("arialmt-bold") | PdfLineSelection.font("arialmt-bolditalic")

# `reach` non e' un limite qui, e' solo il permesso di arrivare fino alla fine della sezione: le sei
# righe sotto l'etichetta si stendono per ottantasei punti, e a fermarle e' `stop`.
pdf_extract_manco = PdfExtractLabelledValueStandard(
    label,
    ResultStandardExtraction.MANAGEMENT_COMPANY.name,
    "managment company",
    where=LabelledValueWhere.BELOW,
    take=LabelledValueTake.ALL,
    reach=12.0,
    stop=next_label,
)

pipelines = {
    "manco": Pipeline(pdf_extract_manco),
}
