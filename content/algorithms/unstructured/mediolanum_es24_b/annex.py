"""L'**annesso** di MEDIOLANUM-ES24.B: il modulo periodico SFDR, in un file suo.

Questo non è un formato. È il secondo file dello stesso rapporto — il modulo periodico che il
regolamento vuole allegato — e il posto in cui si legge è **lo stesso job** del documento principale:
`freeports -f MEDIOLANUM-ES24.B -i rapporto.pdf -i annesso.pdf`. Le pagine dei due file si
classificano una per documento e poi si programmano sull'unione, quindi lo step dell'annesso vede
ciò che gli step del documento principale hanno estratto. È `R30`, e fino al 2026-09-26 era invece
un formato a parte, `MEDIOLANUM-ES24.Bax`: un formato a parte non può stare nello stesso job del
documento a cui appartiene, perché un job ha **un** formato, ed è la ragione per cui la fusione
andava fatta.

**Nessun file di questo annesso esiste**, né fra i documenti di prova né fra i 905 della raccolta.
Il cablaggio è quindi quello che il testo dell'allegato spagnolo fa aspettare, e va verificato il
giorno in cui un rapporto arriva. Due cose lo distinguono dalle pagine SFDR degli altri formati:

- il nome del prodotto **va a capo** nella colonna di destra della testatina, e `A1` restituisce un
  blocco per riga senza riunirle: il tubo se lo scrive il formato, come su FINECO-EN23@IR;
- il fondo **non lo dichiara l'annesso**: lo dichiara la copertina del documento principale, e qui
  il nome del prodotto serve soltanto a verificare che i due parlino dello stesso comparto
  (`sfdr.only_declared_funds`). Finché era un formato a sé l'annesso dichiarava il fondo da solo,
  e non poteva fare altrimenti: nessun'altra pagina del suo job lo nominava.
"""

import sfdr
from freeports.core import PdfBlock
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict

#: La colonna di destra della testatina, fra il richiamo al regolamento e l'identificativo.
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
