"""Custom pdf filter for FINECO-EN23@LUX format"""

import re

import sfdr
from freeports.core import Pipeline

from . import inv_managers
from . import fund_assets

pipelines = {
    "inv_managers": Pipeline(
        (inv_managers.pdf_extract, inv_managers.pdf_extract_manco),
        inv_managers.text_filter,
        (
            inv_managers.deserialize,
            inv_managers.deserialize_fund,
            inv_managers.deserialize_manco,
        ),
    ),
    "fund_assets": Pipeline(
        pdf_extract=fund_assets.pdf_extract,
        text_filter=fund_assets.text_filter,
        deserialize=fund_assets.deserialize,
    ),
    # Lo stesso documento scrive il nome del prodotto in due impaginazioni -- sulla riga
    # dell'etichetta a p223, accanto a p197 -- e il modello le legge tutt'e due. Il segno e'
    # un'immagine su quattro moduli, una `X` di testo su uno e un **tracciato vettoriale** sul
    # sesto: l'unico di tutta la raccolta.
    "sfdr_classification": sfdr.ENGLISH.pipeline(product_prefix=re.compile(r"Product name.*:\s*")),
}
