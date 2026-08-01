from freeports.standard_funcs.pdf_extract import PdfExtractManagmentCompanyStandard
from freeports.standard_funcs.text_filter import TextFilterManagmentCompanyStandard
from freeports.standard_funcs.deserialize import DeserializerManagmentCompanyStandard, DeserializerInvestmentsManagerFromManco
from freeports.utils.pdf_extract import PdfLineSelection
from freeports.core import Pipeline

pipelines = {
    "manco": Pipeline(
        pdf_extract=PdfExtractManagmentCompanyStandard(
            PdfLineSelection.area_from_movewindow(
                PdfLineSelection(font="arial",font_size=(9.9,10.1),text="Società di gestione:"),
                (-0.2,1.5),100.0,1.2
            )
        ),
        text_filter=TextFilterManagmentCompanyStandard(),
        deserialize=(
            DeserializerManagmentCompanyStandard(),
            DeserializerInvestmentsManagerFromManco()
        )
    )
}

