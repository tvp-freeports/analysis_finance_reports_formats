import re

import mediolanum_24
import sfdr
from freeports.core import Pipeline

from . import fund_assets
from . import esg_indicators as esg


compute_page_class = mediolanum_24.compute_page_class

pipelines = {
    "fund_assets": Pipeline(
        pdf_extract=fund_assets.pdf_extract,
        text_filter=fund_assets.text_filter,
        deserialize=fund_assets.deserialize,
    ),
    "inv_managers_begin": Pipeline(
        pdf_extract=mediolanum_24.inv_managers.PdfExtractBeginPage("^INVESTMENT "),
        text_filter=mediolanum_24.inv_managers.text_filter_begin_page,
        deserialize=(
            mediolanum_24.inv_managers.deserialize,
            mediolanum_24.inv_managers.deserialize_fund,
            mediolanum_24.inv_managers.deserialize_manco,
        ),
    ),
    "inv_managers": Pipeline(
        pdf_extract=mediolanum_24.inv_managers.pdf_extract,
        text_filter=mediolanum_24.inv_managers.text_filter,
        deserialize=(
            mediolanum_24.inv_managers.deserialize,
            mediolanum_24.inv_managers.deserialize_fund,
        ),
    ),
    "inv_managers_end": Pipeline(
        pdf_extract=mediolanum_24.inv_managers.PdfExtractEndPage("^BANCA "),
        text_filter=mediolanum_24.inv_managers.text_filter,
        deserialize=(
            mediolanum_24.inv_managers.deserialize,
            mediolanum_24.inv_managers.deserialize_fund,
        ),
    ),
    # Il modulo di questo formato **non ha titolo**: prima l'articolo si deduceva fiutando la prosa
    # ("obiettivo di investimento sostenibile di questo" ⇒ 9), adesso si legge dalla casella, che
    # qui e' un'immagine sola nella banda -- la vuota e' disegnata.
    "sfdr_classification": sfdr.ITALIAN.pipeline(
        product_prefix=(
            "Nome del prodotto: ",
            re.compile(r" \(.*\)"),
            re.compile(r", un comparto .*"),
        )
    ),
    "esg_indicators": Pipeline(
        esg.pdf_extract,
        esg.text_filter,
        esg.deserialize
    )
}
