"""MEDIOLANUM-ES24.Bax

L'**annesso** di MEDIOLANUM-ES24.B, e il solo modulo SFDR della raccolta che nessuno ha mai potuto
provare: **non esiste un documento `.Bax`**, né fra i test né fra i 905 della raccolta (`R30`). Il
cablaggio è quindi quello che l'allegato spagnolo fa aspettare, e va verificato il giorno in cui un
rapporto arriva.

Due cose lo distinguono dagli altri cinque formati:

- il nome del prodotto **va a capo** nella colonna di destra della testatina, e `A1` restituisce un
  blocco per riga senza riunirle: il tubo se lo scrive il formato, come su FINECO-EN23@IR;
- dal nome del prodotto si **dichiara anche il fondo**, perché l'annesso è un documento a sé e
  nessun'altra pagina del job lo ha nominato. Per la stessa ragione il filtro sui fondi
  d'interesse è spento: il confronto con il documento principale lo fa il multidocumento.
"""

import sfdr
from freeports.core import PdfBlock
from freeports.output import Fund
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict

product_set = PdfLineSelection.area_from_bounds(
    x0=PdfLineSelection.text("significa una inversión"),
    x1=1e6,
    y0=PdfLineSelection.text("eglamento (UE) 2020/852"),
    y1=PdfLineSelection.text("dentificador de entidad"),
) & PdfLineSelection(font="calibri")


def pdf_extract_product(page):
    """Le righe del nome del prodotto, dall'alto in basso, in un blocco solo."""
    lines = pdflines_from_pagedict(page)
    selected = sorted(product_set.select(lines), key=lambda line: line.bbox[1])
    name = "".join(line.text for line in selected)
    return [PdfBlock(sfdr.PRODUCT_BLOCK, {}, name)] if name.strip() else []


def deserialize_fund(txt_blk):
    return Fund(name=txt_blk.content)


pipelines = {
    "sfdr_classification": sfdr.SPANISH.pipeline(
        product_pipes=(pdf_extract_product,),
        product_prefix=[],
        demand_investment_funds_match=False,
        also_deserialize=(deserialize_fund,),
    ),
}
