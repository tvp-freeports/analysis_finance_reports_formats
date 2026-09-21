"""`A7` — le ridenominazioni e le fusioni di comparto, lette una volta per tutti i formati.

Cinque formati dichiarano la stessa cosa in tre impaginazioni diverse, e per `R27` sono tre
pipeline che condividono il `pdf_extract` — una sezione aperta da un'intestazione — e divergono nel
`text_filter`, che è dove `R23` mette ogni interpretazione del testo.

```python
import renaming
from freeports.core import Pipeline

read = renaming.Listed(
    renamed=(r"have been renamed",),
    merged=(r"have been merged",),
)

pipelines = {
    "renaming": Pipeline(
        pdf_extract=pdf_extract_section,
        text_filter=renaming.text_filter(read),
        deserialize=renaming.deserialize(),
    ),
}
```

La sezione vuota che **dichiara l'assenza** — ARCA-IT24 p6, `Non si segnalano eventi rilevanti` —
non ha bisogno di niente in più: gli stessi lettori non trovano nessun cambio e la pipeline non
scrive nessuna riga. Che sia stata letta lo dimostra il `pdf_extract`, e per questo il test di
quella pagina si scrive lo stesso.
"""

from .blocks import BLOCK, deserialize, text_filter
from .reading import DATE, Change, Listed, Sentence

__all__ = [
    "BLOCK",
    "DATE",
    "Change",
    "Listed",
    "Sentence",
    "deserialize",
    "text_filter",
]
