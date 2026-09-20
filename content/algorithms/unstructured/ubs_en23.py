import re

import sfdr

from freeports.standard_funcs.pdf_extract import PdfExtractManagmentCompanyStandard
from freeports.standard_funcs.text_filter import TextFilterManagmentCompanyStandard
from freeports.standard_funcs.deserialize import DeserializerManagmentCompanyStandard
from freeports.utils.pdf_extract import PdfLineSelection
from freeports.core import Pipeline

pipelines = {
    "manco": Pipeline(
        pdf_extract=PdfExtractManagmentCompanyStandard(
            PdfLineSelection.area_from_movewindow(
                PdfLineSelection(font="frutiger45lightbold",font_size=(9.9,10.1),text="Management Company and Domiciliation Agent"),
                (-0.2,1.9),1.1,1.3
            )
        ),
        text_filter=TextFilterManagmentCompanyStandard(),
        deserialize=DeserializerManagmentCompanyStandard()
    ),
    # Il segno e' una `X` di testo, salvo p189 dove e' il `3` di Wingdings 2 -- lo stesso modulo,
    # due tipografie, e i riconoscitori sono tutti attivi per difetto.
    "sfdr_classification": sfdr.ENGLISH.pipeline(
        product_joined=True,
        # `(the "subfund")` sta attaccato al nome su otto moduli su nove, e la
        # normalizzazione lo incolla al nome invece di toglierlo: `R24` non reggerebbe.
        product_prefix=(
            re.compile(r"Product name\s*:\s*"),
            re.compile(r"\s*\((?:the|il|la)\s[^)]*\)\s*$"),
        ),
    ),
}
