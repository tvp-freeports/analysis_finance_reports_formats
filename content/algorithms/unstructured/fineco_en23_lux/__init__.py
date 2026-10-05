"""Custom pdf filter for FINECO-EN23@LUX format"""


from freeports.core import Pipeline

from . import inv_managers

pipelines = {
    "inv_managers": Pipeline((inv_managers.pdf_extract, inv_managers.pdf_extract_manco)),
    # Lo stesso documento scrive il nome del prodotto in due impaginazioni -- sulla riga
    # dell'etichetta a p223, accanto a p197 -- e il modello le legge tutt'e due. Il segno e'
    # un'immagine su quattro moduli, una `X` di testo su uno e un **tracciato vettoriale** sul
    # sesto: l'unico di tutta la raccolta.
}
