"""Unstructured module for FINECO-EN23@IR"""

import re

import esg
import sfdr
from freeports.core import PdfBlock, Pipeline
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict

from . import investments
from . import inv_managers
from . import managment_company
from . import fund_assets
from . import esg_indicators

#: Il nome del prodotto, che su questo formato **va a capo**.
#:
#: `A1` restituisce un blocco per riga e non le riunisce, quindi qui il tubo se lo scrive il
#: formato: e' la stessa regione che l'algoritmo precedente usava come `fund_selection`, e la stessa
#: concatenazione dall'alto in basso, in modo che le righe che ne uscivano continuino a uscirne.
product_set = (
    PdfLineSelection.area_from_bounds(
        # The left edge is the end of the annex's "means" label, which sits alone in the glossary
        # column and is written both "means " and " means" -- so the column, not the spelling, is
        # what identifies it.  Some pages also carry a body sentence containing "means" ("... which
        # means, that the majority ..."), and its right edge lies past the fixed x1 below: taken as
        # the left edge it inverts the window, and the page is lost.
        x0=PdfLineSelection(text="means", area=(0.0, 0.0, 150.0, 1e6)),
        x1=372.94,
        y0=PdfLineSelection.text("Regulation (EU) 2020/852"),
        y1=PdfLineSelection.text("Did this financial product"),
    )
    / (PdfLineSelection.text("^ $") | PdfLineSelection.text("^  $"))
    / (
        PdfLineSelection.area_from_movewindow(
            PdfLineSelection(text="Legal entity identifier")
            | PdfLineSelection(text="Legal Entity Identifier"),
            (0.0, 0.0),
            30.0,
            3.0,
        )
    )
) | PdfLineSelection.text("Product name")


def pdf_extract_product(page):
    """Le righe del nome, dall'alto in basso, in un blocco solo."""
    lines = pdflines_from_pagedict(page)
    selected = sorted(product_set.select(lines), key=lambda line: line.bbox[1])
    name = "".join(line.text for line in selected)
    return [PdfBlock(sfdr.PRODUCT_BLOCK, {}, name)] if name.strip() else []


pipelines = {
    "investments": Pipeline(
        pdf_extract=(
            investments.pdf_extract,
            investments.pdf_extract_fund,
            investments.pdf_extract_currency,
        )
    ),
    "inv_managers_table": Pipeline(
        inv_managers.pdf_filter,
        inv_managers.text_extract,
        (inv_managers.deserialize, inv_managers.deserialize_fund),
    ),
    "manco": Pipeline(
        managment_company.pdf_filter,
        managment_company.text_extract,
        (managment_company.deserialize, managment_company.deserialize_inv_manager),
    ),
    "fund_assets": Pipeline(
        fund_assets.pdf_extract, fund_assets.text_filter, fund_assets.deserialize
    ),
    # Tre impaginazioni nello stesso documento -- il segno e' un'immagine su ventotto moduli, una
    # `X` di testo su sei e un glifo `funddsymbol` su uno -- e il modello le legge tutt'e tre senza
    # che il formato scelga. Il nome del prodotto invece e' del formato, perche' va a capo: v.
    # `pdf_extract_product`.
    "sfdr_classification": sfdr.ENGLISH.pipeline(
        product_pipes=(pdf_extract_product,),
        product_prefix=re.compile(r"Product name.*:\s*"),
    ),
    # La pagina del modulo legge il nome **due volte**: una per l'articolo SFDR, una per lasciarlo
    # alla pagina degli indicatori, che il comparto non lo nomina. Sono due dati diversi sulla
    # stessa pagina, quindi due pipeline (`R27`), tutt'e due sulla classe `sfdr_classification`.
    "esg_fund": Pipeline(
        esg_indicators.pdf_extract_fund,
        esg_indicators.text_filter_fund,
        esg_indicators.carry.deposit,
    ),
    "esg_indicators": Pipeline(
        esg_indicators.pdf_extract_indicators,
        esg_indicators.text_filter_indicators,
        esg.deserialize,
    ),
}
