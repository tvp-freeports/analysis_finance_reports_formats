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
"""

from .blocks import BLOCK, deserialize, text_filter
from .reading import MARKER, NUMBER, Indicator, LeadingNumber

__all__ = [
    "BLOCK",
    "MARKER",
    "NUMBER",
    "Indicator",
    "LeadingNumber",
    "deserialize",
    "text_filter",
]
