"""ANIMA_EN23 format submodule"""

import logging as log
from typing import List, TypeAlias
import re
from freeports.core import Pipeline, PdfBlock, TextBlock
from freeports.output import Fund, FundMerge
from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractCurrencyStandard,
    PdfExtractFundStandard,
    PdfExtractManagmentCompanyStandard,
)
from freeports.interfaces.pdf_blks import (
    OnePdfBlockType,
)
from freeports.interfaces.text_blks import (
    OneTextBlockType,
    ResultStandardFiltering
)
from freeports.standard_funcs.text_filter import (
    TextFilterManagmentCompanyStandard,
)
from freeports.utils.pdf_extract import (
    PdfLineSelection,
    pdflines_from_pagedict,
    get_groups
)
from freeports.standard_funcs.deserialize import (
    DeserializerManagmentCompanyStandard,
    DeserializerInvestmentsManagerFromManco,
)
from freeports.utils.deserialize import (
    to_date_with_en_month
)
from freeports.utils.text_filter import MatchFund

logger = log.getLogger(__name__)


PdfBlockType: TypeAlias = OnePdfBlockType
TextBlockType: TypeAlias = ResultStandardFiltering


def pdf_extract_investments(dict_root) -> List[PdfBlock]:
    """PDF filter for ANIMA_EN23 format with dynamic table bounds calculation.

    This PDF filter dynamically calculates the bounds of the table by
    using the position of "Fair Value" text as a reference point.

    Parameters
    ----------
    xml_root : etree.Element
        XML root element of the PDF page

    Returns
    -------
    List[PdfBlock]
        List of PDF blocks extracted from the page

    Notes
    -----
    The filter:
    - Locates "Fair Value" text to determine table position
    - Dynamically calculates currency set bounds
    - Identifies table areas based on font patterns
    - Uses standard PDF filtering with calculated parameters
    """
    lines = pdflines_from_pagedict(dict_root)
    fair_value_line = PdfLineSelection(
        font="Helvetica-Bold", text="^Fair Value$"
    ).select(lines)

    if len(fair_value_line) == 0:
        return []
    x0, y0, x1, y1 = fair_value_line[0].bbox
    y_offset = 10
    currency_set = PdfLineSelection(
        font="Helvetica-Bold",
        font_size=(8.9800, 8.9804),
        area=(x0 - 5, y0 + y_offset, x1 + 5, y1 + y_offset + 10),
    )
    tables = PdfLineSelection(font="Helvetica-Bold", area=(0.0, 0.0, 105, 1e6)).select(
        lines
    )
    if len(tables) == 0:
        return []
    if len(tables) == 1:
        area = None
    else:
        if tables[-1].text == "Holdings":
            y0 = tables[-1].bbox[1]
            y1 = 1e6
        else:
            for i, table in enumerate(tables):
                if table.text == "Holdings":
                    y0 = table.bbox[1]
                    y1 = tables[i + 1].bbox[1]
        area = (0.0, y0, 1e6, y1)

    std = PdfExtractInvestmentsStandard(
        body_set=PdfLineSelection(font="Helvetica-Light", area=area)
    )
    res = std(dict_root)
    std_currency = PdfExtractCurrencyStandard(currency_set)
    res.extend(std_currency(dict_root))

    return res


pdf_extract_funds = PdfExtractFundStandard(
    PdfLineSelection(font="Helvetica-Condensed-Blac", area=(0.0, 62.0, 1e6, 82.0))
)



def pdf_extract_merges(page):
    lines = pdflines_from_pagedict(page)
    body = PdfLineSelection.area_from_bounds(
        x0=0.0,
        y0=PdfLineSelection.text("Funds merged during the financial year"),
        x1=1e6,
        y1=PdfLineSelection.text("Dividends Paid"),
    ).select(lines)
    groups = get_groups(body, 20)
    n_groups = max(groups) + 1
    return [
        PdfBlock(
            OnePdfBlockType.RELEVANT_BLOCK.name,
            {},
            " ".join((b.text for g, b in zip(groups, body) if group == g)),
        )
        for group in range(n_groups)
    ]


merge_regex = re.compile(
    "(.+) was automatically converted into (.+) on ([0-9]+.+[0-9]+)"
)


def text_filter_merges(pdf_blks, filter_data):
    funds = set(
        map(
            lambda x: MatchFund(name=x.name),
            filter(lambda x: isinstance(x, Fund), filter_data),
        )
    )
    res = []
    for blk in pdf_blks:
        m = merge_regex.match(blk.content)
        old_name = m.group(1)
        current_name = MatchFund(name=m.group(2))
        date = m.group(3)
        if current_name in funds:
            res.append(
                TextBlock(
                    OneTextBlockType.RELEVANT_BLOCK.name,
                    {
                        "old_name": old_name,
                        "current_name": current_name.name,
                        "date": date,
                    },
                    blk,
                )
            )
    return res


def deserialize_merges(txt_blk):
    md = {**txt_blk.metadata}
    return FundMerge(
        old_name=md["old_name"],
        current_name=md["current_name"],
        date=to_date_with_en_month(md["date"]),
    )


pipelines = {
    "manco": Pipeline(
        pdf_extract=PdfExtractManagmentCompanyStandard(
            PdfLineSelection.area_from_movewindow(
                PdfLineSelection(
                    text="Manager, Promoter and Distributor", font="helvetica-bold"
                ),
                (-0.1, 1.0),
                1.3,
                1.5,
            )
        ),
        text_filter=TextFilterManagmentCompanyStandard(),
        deserialize=(
            DeserializerManagmentCompanyStandard(),
            DeserializerInvestmentsManagerFromManco(),
        ),
    ),
    "investments": Pipeline(
        pdf_extract=(
            pdf_extract_investments,
            pdf_extract_funds,
        )
    ),
    "year_events": Pipeline(pdf_extract_merges, text_filter_merges, deserialize_merges),
}
