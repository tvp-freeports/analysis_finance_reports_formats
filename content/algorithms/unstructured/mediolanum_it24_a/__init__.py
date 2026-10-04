
import mediolanum_24
from freeports.core import Pipeline

from . import esg_indicators as esg


compute_page_class = mediolanum_24.compute_page_class

pipelines = {
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
    "esg_indicators": Pipeline(
        esg.pdf_extract,
        esg.text_filter,
        esg.deserialize
    )
}
