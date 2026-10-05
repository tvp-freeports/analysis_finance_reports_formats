"""Unstructured module for FINECO-EN23@IR"""

import esg
from freeports.core import Pipeline
from freeports.utils.pdf_extract import PdfLineSelection

from . import investments
from . import inv_managers
from . import managment_company
from . import esg_indicators

#: La regione del nome del prodotto, che su questo formato **va a capo**.
#:
#: Il modulo SFDR non la usa piu': la sua pipeline e' passata al livello `semistructured`
#: (`sfdr_annex` con `product_joined`), che chiude la colonna sull'identificativo della persona
#: giuridica invece che su un'ascissa fissa -- v. la voce `C33` e il commento nello YAML. Questa
#: resta per la pagina degli **indicatori ESG**, che del nome ha bisogno insieme al numero di
#: pagina e quindi non puo' usare il tubo del motore cosi' com'e': v.
#: `esg_indicators.pdf_extract_fund`.
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


pipelines = {
    "investments": Pipeline(
        pdf_extract=(
            investments.pdf_extract,
            investments.pdf_extract_fund,
            investments.pdf_extract_currency,
        )
    ),
    "inv_managers": Pipeline(inv_managers.pdf_filter),
    "manco": Pipeline(managment_company.pdf_filter),
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
