"""`A6` — gli indicatori ESG del modulo periodico, letti una volta per tutti i formati.

```python
import esg
from freeports.core import Pipeline

read = esg.LeadingNumber()

pipelines = {
    "esg_indicators": Pipeline(
        pdf_extract=pdf_extract_section,
        text_filter=esg.text_filter(read, fund_of_the_page),
        deserialize=esg.deserialize,
    ),
}
```

La regola che tiene insieme tutta la famiglia è una sola: **un indicatore senza numero non
esiste** (`R11`). Una sezione di sola prosa non ha quindi bisogno di nessun ramo suo — il lettore
non ci trova valori e la pipeline non scrive righe — ed è per questo che ANIMA_SGR-IT24 p1726 si
legge con la stessa configurazione di FINECO-EN23@IR p894.

# I tre lettori

| come la pagina scrive l'indicatore | lettore | ricette |
|---|---|---|
| una frase numerata che **comincia col valore** | `LeadingNumber` | `EI-3`, `EI-4` |
| una **tabella**: il nome sopra, una riga per serie, una colonna per esercizio | `DatedRows` | `EI-2`, `EI-5` |
| **`etichetta: valore`**, una voce per riga | `LabelledPairs` | `EI-1` |

Due cose ricorrono in tutti e tre, e sono scelte e non dettagli:

- **l'esercizio precedente non si estrae** (`R5`). Tre pagine su cinque ripetono le stesse misure
  dell'anno prima, e scriverle vorrebbe dire due righe indistinguibili per lo stesso indicatore
  dello stesso comparto. Dove la ripetizione è una sezione, la si chiude prima; dove è una colonna,
  si prende la colonna della data più recente;
- **la riga dell'indice di riferimento non è un dato del comparto.** `DatedRows` la lascia fuori
  col parametro `series`, `LabelledPairs` con `drop`.
"""

from .blocks import BLOCK, deserialize, text_filter
from .reading import MARKER, NUMBER, DatedRows, Indicator, LabelledPairs, LeadingNumber

__all__ = [
    "BLOCK",
    "MARKER",
    "NUMBER",
    "DatedRows",
    "Indicator",
    "LabelledPairs",
    "LeadingNumber",
    "deserialize",
    "text_filter",
]
