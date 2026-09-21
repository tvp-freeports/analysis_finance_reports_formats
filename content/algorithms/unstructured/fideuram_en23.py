"""FIDEURAM-EN23: la società di gestione nella prosa di una nota, e i gestori delegati in elenco.

`MC-5`. Il prospetto non ha nessuna sezione `Management Company` e nessuna etichetta: il nome sta
dentro una frase della nota 1, `GENERAL INFORMATION` di pagina 67, fra due espressioni fisse.

```
The Fund has been created for an indefinite period and it is managed by Fideuram Asset Management
(Ireland) dac (the "Management Company").
```

Le due espressioni sono `it is managed by` e la parentesi che apre `(the "Management Company")`, e
la seconda serve **davvero**: il nome stesso ne contiene una, `(Ireland)`, quindi a fermarsi alla
prima parentesi si estrarrebbe `Fideuram Asset Management`.

# Perché l'ancora del `pdf_extract` è la frase e non l'intestazione della nota

`A2` porterebbe giù tutta la sezione, una ventina di righe di prosa, e a quel punto *quale* sia la
riga giusta tornerebbe a essere una domanda. La frase invece la pagina la scrive una volta sola —
misurato su tutte le 81 pagine del prospetto — e allora l'ancora è lei: la geometria consegna
**quella riga**, e il `text_filter` ne taglia il nome (`R23`). Le parole si ripetono nei due
segmenti perché i due lavori sono diversi, non perché uno dei due sia di troppo.
"""

import inv_managers
import manco
from freeports.core import Pipeline
from freeports.interfaces.pdf_blks import OnePdfBlockType, ResultStandardExtraction
from freeports.standard_funcs.deserialize import (
    DeserializerFundStandard,
    DeserializerInvestmentsManagerStandard,
    DeserializerManagmentCompanyStandard,
)
from freeports.output import Fund
from freeports.standard_funcs.pdf_extract import (
    PdfExtractLabelledValueStandard,
    PdfExtractSectionStandard,
)
from freeports.utils.pdf_extract import PdfLineSelection

pdf_extract_manco = PdfExtractLabelledValueStandard(
    PdfLineSelection(font="arial", font_size=(7.5, 8.5), text="it is managed by"),
    ResultStandardExtraction.MANAGEMENT_COMPANY.name,
    "managment company",
)

text_filter_manco = manco.text_filter(
    manco.Between(after="it is managed by", before=r"\(the")
)

# `IM-5`, p71: tredici righe `<gestore> for <comparti>`, una sotto l'altra, sotto l'intestazione
# `Investment Manager`. Tutta la pagina e' in arial 7.98 -- intestazioni comprese -- quindi la
# sezione non si chiude sulla famiglia tipografica -- la riga **subito dopo** l'intestazione ha
# lo stesso carattere e lo stesso corpo, e la sezione si chiuderebbe vuota: `family` diventa
# allora la frase che la chiude davvero.
# Il corpo si restringe per **ascissa**, perche' le voci rientrano a `x=56,6` mentre i trattini
# dell'elenco e la prosa attorno stanno a `x=41,5`.
pdf_extract_inv_managers = PdfExtractSectionStandard(
    PdfLineSelection(text="^Investment Manager$", font="arial", font_size=(7.5, 8.5)),
    OnePdfBlockType.RELEVANT_BLOCK.name,
    "investment managers",
    family=PdfLineSelection.text("^The Management Company keeps the control"),
    body=PdfLineSelection(area=(50.0, 0.0, 600.0, 850.0)),
)

read_inv_managers = inv_managers.ConnectorLine()


def text_filter_inv_managers(pdf_blks, filter_data):
    """`R15`: il residuo e' della societa' di gestione, che pero' sta su un'altra pagina.

    Per questo la classe `manco_note` viene **prima** nello `algorithms_schedule.csv` e il suo passo
    si chiude: qui la si ritrova fra i risultati, e `assign` sa a chi dare i comparti che le
    tredici righe non nominano.
    """
    assignment = inv_managers.assign(
        read_inv_managers(pdf_blks),
        inv_managers.fund_set(
            result.name for result in filter_data if isinstance(result, Fund)
        ),
        manco=manco.declared(filter_data),
    )
    return inv_managers.text_blocks(assignment)


pipelines = {
    # Nessun `DeserializerInvestmentsManagerFromManco` qui: i comparti che restano alla societa'
    # di gestione li calcola `assign` sulla pagina dei gestori, e darglieli tutti da questa parte
    # vorrebbe dire scrivere due volte le stesse righe.
    "manco_note": Pipeline(
        pdf_extract_manco,
        text_filter_manco,
        DeserializerManagmentCompanyStandard(),
    ),
    # Il secondo deserializzatore serve al comparto che **solo** questa sezione nomina:
    # `Willerfunds - Private Suite - Fidelity USD Bond` non compare fra gli investimenti, e senza
    # di lui `funds.csv` guadagnerebbe una riga senza rapporto ne' pagina.
    "inv_managers": Pipeline(
        pdf_extract_inv_managers,
        text_filter_inv_managers,
        (DeserializerInvestmentsManagerStandard(), DeserializerFundStandard()),
    ),
}
