"""La società di gestione letta **dentro** la riga che la dichiara.

Il motore sa già prendere la riga intera, ed è quello che serve dove l'etichetta sta sopra il valore
e il valore è tutto lì. Questo pacchetto copre gli altri quattro modi misurati — l'etichetta sulla
stessa riga, la parentesi che chiude il nome, la frase di prosa, la virgola — e la regola `U6` su
quale delle due società si tiene quando il bilancio le nomina tutte e due.

Una pipeline `manco` completa somiglia a questa:

```python
import manco

pipelines = {
    "manco": Pipeline(
        PdfExtractLabelledValueStandard(
            PdfLineSelection.text("^Società di Gestione del Risparmio"),
            ResultStandardExtraction.MANAGEMENT_COMPANY.name,
            "managment company",
        ),
        manco.text_filter(manco.Between(after="Società di Gestione del Risparmio")),
        (DeserializerManagmentCompanyStandard(), DeserializerInvestmentsManagerFromManco()),
    ),
}
```

Il `pdf_extract` è `A1` e resta del motore: *dove* sta il valore rispetto all'etichetta è geometria
(`R23`). Quello che il formato aggiunge qui è *quale pezzo della riga sia il nome*, che è
interpretazione di testo e non si può fare prima.

Il secondo deserializzatore non è un dettaglio: senza, la società di gestione esce in
`assets_managers.csv` e **nessun fondo** le viene legato in
`investments_managers_to_funds.csv` — `R15`, il residuo va a lei quando nessun gestore delegato è
dichiarato.
"""

from .blocks import declared, text_filter
from .reading import Between, first, most_recent

__all__ = ["Between", "declared", "first", "most_recent", "text_filter"]
