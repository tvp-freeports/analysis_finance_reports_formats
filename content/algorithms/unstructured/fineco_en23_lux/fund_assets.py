from freeports.utils.pdf_extract import PdfLineSelection
from freeports.utils.deserialize import to_int
from freeports.standard_funcs.pdf_extract import (
    AssetsColumn,
    PdfExtractAssetsStandard,
)
from freeports.standard_funcs.text_filter import TextFilterAssetsStandard
from freeports.standard_funcs.deserialize import DeserializerAssetsStandard


x0 = PdfLineSelection(font="arialnarrow-bold", font_size=(8.9, 9.1), text="Notes")

y0 = PdfLineSelection(
    font="arialnarrow-bold",
    font_size=(13.9, 14.1),
    text="Statement of Net Assets",
)
y1 = PdfLineSelection(font="arialnarrow-bold", font_size=(8.9, 9.1), text="^ASSETS")

x1 = 1e6


pdf_extract = PdfExtractAssetsStandard(
    fund_set=PdfLineSelection.area_from_bounds(x0=x0, y0=y0, x1=x1, y1=y1),
    currency_set=None,
    tot_assets=AssetsColumn(
        PdfLineSelection(font="arialnarrow-bold", font_size=(8.9, 9.1), text="LIABILITIES"),
        vec=(1.2, -3.5),
        mult=(100.0, 3.0),
    ),
    liabilities=AssetsColumn(
        PdfLineSelection(font="arialnarrow-bold", font_size=(8.9, 9.1), text="TOTAL NET ASSETS"),
        vec=(1.2, -3.5),
        mult=(100.0, 3.0),
    ),
    net_assets=AssetsColumn(
        PdfLineSelection(font="arialnarrow-bold", font_size=(8.9, 9.1), text="TOTAL NET ASSETS"),
        mult=(100.0, 2.2),
    ),
    table_condition=True
)

text_filter = TextFilterAssetsStandard()
deserialize = DeserializerAssetsStandard(num_converter=to_int)
