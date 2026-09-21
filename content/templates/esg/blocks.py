"""Dagli indicatori letti ai blocchi, e dai blocchi alle righe di `funds_esg_indicators.csv`.

Il `text_filter` fa due cose: chiama il lettore e attacca ciascun indicatore **al comparto di cui
la pagina parla**. Il `deserialize` non fa niente più che il casting del valore, che è tutto ciò
che `R23` gli lascia.

# Di che comparto parla questa pagina

È la domanda che questo template **non** risponde da sé, perché la risposta cambia da formato a
formato: su KAIROS-EN23 il nome sta sulla stessa pagina del modulo, su FINECO-EN23@IR sta sulla
pagina **prima**, su EURIZON-EN23 arriva da una promessa depositata dal tubo del nome del prodotto.
Il chiamante passa quindi `fund`, che può essere un nome o una promessa, ed è lui a saperlo.

Quando il nome sta sulla pagina prima, la risposta è **`carryover.PageCarryover`** — la decisione
dell'utente del 2026-09-21 — e si passa così:

```python
carry = carryover.PageCarryover("esg-fund")
text_filter = esg.text_filter(read, carry.owner())
```
"""

from freeports.core import TextBlock
from freeports.interfaces.text_blks import OneTextBlockType
from freeports.output import FundEsgIndicator

BLOCK = OneTextBlockType.RELEVANT_BLOCK.name
"""Il tipo di blocco che questo template scrive, e che il suo `deserialize` si aspetta."""


def text_filter(read, fund):
    """Il `text_filter` di una pipeline di indicatori: legge, e attacca il comparto a ciascuno.

    `fund` dice di chi è la pagina, e si passa in due forme: una stringa, quando il nome è noto al
    formato, o una funzione `(pdf_blks, filter_data) -> nome o promessa`, quando va cercato.
    """

    def filter_blocks(pdf_blks, filter_data):
        indicators = read(pdf_blks)
        if not indicators:
            # `R11`: una sezione senza numeri non è una sezione mancata, è una sezione che dice
            # che non ci sono misure. Non si avvisa, perché non c'è niente di anomalo da riferire.
            return []
        owner = fund(pdf_blks, filter_data) if callable(fund) else fund
        if owner is None:
            return []
        return [_block(indicator, owner) for indicator in indicators]

    return filter_blocks


def _block(indicator, owner):
    """Il blocco di testo che porta l'indicatore fino al `deserialize`."""
    return TextBlock(
        BLOCK,
        {"fund": owner, "name": indicator.name, "value": indicator.value},
        indicator.block,
    )


def deserialize(txt_blk):
    """Una riga per blocco: il nome e il valore così come la pagina li scrive."""
    metadata = txt_blk.metadata
    return FundEsgIndicator(
        fund=metadata["fund"], name=metadata["name"], value=metadata["value"]
    )
