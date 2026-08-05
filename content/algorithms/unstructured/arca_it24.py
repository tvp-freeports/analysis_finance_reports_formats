"""Unstructured module for ARCA-IT24"""

from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractFundStandard,
    PdfExtractCurrencyConstant,
    PdfExtractSfdrArticleStandard,
)
from freeports.consts import Currency
from freeports.utils.pdf_extract import (
    pdfline_selection_from_str,
    PdfLineSelection,
)
from freeports.standard_funcs.text_filter import TextFilterSfdrArticleStandard
from freeports.standard_funcs.deserialize import DeserializeSfdrArticleStandard
from freeports.core import Pipeline


subfund_set = PdfLineSelection.area(0.0, 0.0, 1e6, 60.0) & (
    PdfLineSelection.font("Calibri") | PdfLineSelection.font("Lato-Regular")
)


body_set = PdfLineSelection(
    font="TrebuchetMS", font_size=(6.95, 6.97)
) & PdfLineSelection.area_from_bounds(
    x0=0.0,
    y0=PdfLineSelection(
        font="Lato-Regular",
        text="Elenco analitico dei principali strumenti finanziari detenuti dal Fondo",
        font_size=(11.9, 12.1),
    ),
    x1=1e6,
    y1=1e6,
)

pipelines = {
    "investments": Pipeline(
        pdf_extract=(
            PdfExtractInvestmentsStandard(body_set=body_set),
            PdfExtractFundStandard(subfund_set),
            PdfExtractCurrencyConstant(Currency.EUR),
        )
    ),
    "sfdr_classification": Pipeline(
        PdfExtractSfdrArticleStandard(
            PdfLineSelection.text(
                "informativa periodica per i prodotti finanziari di cui all'articolo 9"
            ),
            PdfLineSelection.text(
                "informativa periodica per i prodotti finanziari di cui all'articolo 8"
            ),
            PdfLineSelection(text="Nome del prodotto"),
        ),
        TextFilterSfdrArticleStandard(["Nome del prodotto: "]),
        DeserializeSfdrArticleStandard(),
    ),
}
