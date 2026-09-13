"""Unstructured module for EURIZON-IT24"""

from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractCurrencyConstant,
    PdfExtractFundStandard,
    PdfExtractSfdrArticleStandard
)
from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.core import Pipeline
from freeports.utils.pdf_extract import (
    ExtractTextPdfBlockOrFailPage,
    PdfLineSelection,
    pdflines_from_pagedict,
    get_groups,
    get_table_coordinates,
    TablePosAlgorithm,
)
from freeports.standard_funcs.text_filter import (
    TextFilterSfdrArticleStandard
)
from freeports.interfaces.text_blks import OneTextBlockType,StandardManagmentCompanyTextBlock
from freeports.standard_funcs.deserialize import (
    DeserializeSfdrArticleStandard,
    DeserializerManagmentCompanyStandard,
    DeserializerInvestmentsManagerFromManco
)
from freeports.utils.deserialize import to_date_with_it_month, deserialize_block_type
from freeports.utils.text_filter import MatchFund,investment_fund_filter_data
from freeports.consts import Currency, SfdrArticle
from freeports.core import Promise
from freeports.core import PageParseFail, PdfBlock, TextBlock
from freeports.output import (
    Fund,
    FundMerge,
    FundRename,
    FundSfdrClassification,
    FundEsgIndicator,
)
import re
from enum import Enum, auto


class TypeChangeName(Enum):
    MERGING = auto()
    RENAMING = auto()


fund_set = PdfLineSelection(
    font="TrebuchetMSItalic", font_size=(4, 6.5), area=(270, 700, 595, 805)
)

body_set = PdfLineSelection.font("TrebuchetMS")

pdf_filter_manco = ExtractTextPdfBlockOrFailPage(
    PdfLineSelection.text("^La società di gestione"),
    "managment company",
    OnePdfBlockType.RELEVANT_BLOCK.name,
)

manco_regex = re.compile("gestione ([^,]+)")


def text_filter_manco(pdf_blks, filter_data):
    funds = set(
        map(
            lambda x: MatchFund(x.name),
            filter(lambda x: isinstance(x, Fund), filter_data),
        )
    )
    m = manco_regex.search(pdf_blks[0].content)
    found = None
    if m:
        found = m.group(1).strip()
    else:
        raise PageParseFail("Managment regex didn't matched anything")
    return [StandardManagmentCompanyTextBlock.from_name(found, funds)]


deselection_list = [
    PdfLineSelection(font="TrebuchetMS", text="Totale"),
    PdfLineSelection(font="TrebuchetMS", text="Altri strumenti finanziari"),
]


def pdf_extract_change_name(page):
    lines = pdflines_from_pagedict(page)
    body = PdfLineSelection.font("trebuchetms").select(lines)
    groups = get_groups(body, 10)
    text = (
        " ".join((b.text for g, b in zip(groups, body) if g == 0))
        .replace("”", '"')
        .replace("“", '"')
    )
    return [PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {}, text)]


regex_change_name = re.compile(
    r'Il fondo "(.+)" \(già denominato (.+)\) è stato istituito'
)
regex_rename = re.compile(r'"(.+)" fino al ([0-9]+ [a-z]+ [0-9]+)')
# Every incorporation in the paragraph, read one by one instead of splitting the paragraph on
# "in data": the same sentence also introduces them with "il <date>", with "e in data <date>" and
# with "; il <date>", and a split that misses one of those forms hands two incorporations to a
# single date.  The fund names come quoted, one for "il fondo" and a list for "i fondi", whose
# items are separated by a comma, by "e" or by "ed" -- often all three in the same list.
regex_merge = re.compile(
    r'([0-9]+ [a-zàèéìòù]+ [0-9]+) ha incorporato il? [Ff]ond[oi] '
    r'("[^"]*"(?:(?:,| ed?) "[^"]*")*)'
)


def text_filter_change_name(pdf_blks, filter_data):
    funds = set(
        map(
            lambda x: MatchFund(x.name),
            filter(lambda x: isinstance(x, Fund), filter_data),
        )
    )
    # The line breaks of the PDF reach the block as runs of spaces, and the day of a date is
    # written both "1" and "1°": both are noise for the patterns below, and normalising them here
    # once keeps every pattern free of the alternatives.
    text = re.sub(r"\s+", " ", pdf_blks[0].content.replace("°", "")).strip()
    m = regex_change_name.match(text)
    if not m:
        return []
    current_name = MatchFund(m.group(1))
    if current_name not in funds:
        return []

    rename = regex_rename.match(
        m.group(2).replace(" ed", ",").split(", ")[-1].strip()
    )
    merges_text = text.partition("Il Fondo è operativo a partire dal")[2]

    # A renaming written in some other shape costs the renaming alone.  The incorporations below
    # are independent facts that happen to share the paragraph, and dropping them along with it
    # would lose more than it protects.
    res = [
        TextBlock(
            TypeChangeName.RENAMING.name,
            {
                "old_name": rename.group(1),
                "current_name": current_name.name,
                "date": rename.group(2),
            },
            pdf_blks[0],
        )
    ] if rename else []
    for mrg in regex_merge.finditer(merges_text):
        date_merge = mrg.group(1)
        tmp = mrg.group(2).split('"')
        for i in range(1, len(tmp), 2):
            res.append(
                TextBlock(
                    TypeChangeName.MERGING.name,
                    {
                        "old_name": tmp[i],
                        "current_name": current_name.name,
                        "date": date_merge,
                    },
                    pdf_blks[0],
                )
            )
    return res


@deserialize_block_type(TypeChangeName.RENAMING.name)
def deserialize_rename(txt_blk):
    md = txt_blk.metadata
    return FundRename(
        old_name=md["old_name"],
        current_name=md["current_name"],
        date=to_date_with_it_month(md["date"]),
    )


@deserialize_block_type(TypeChangeName.MERGING.name)
def deserialize_merge(txt_blk):
    md = txt_blk.metadata
    return FundMerge(
        old_name=md["old_name"],
        current_name=md["current_name"],
        date=to_date_with_it_month(md["date"]),
    )


def sfdr_pdf_extract_1(page):
    lines = pdflines_from_pagedict(page)
    fund_name = next(iter(PdfLineSelection.text("Nome prodotto: ").select(lines))).text
    return [PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {}, fund_name)]


@investment_fund_filter_data
def sfdr_text_filter_1(pdf_blks, investment_funds):
    fund_name = next(iter(pdf_blks)).content
    fund_name = fund_name.replace("Nome prodotto: ", "")
    fund = MatchFund(name=fund_name)
    if fund in investment_funds:
        return [TextBlock.from_content(OneTextBlockType.RELEVANT_BLOCK.name, {}, fund_name)]
    else:
        return []


def sfdr_deserialize_1(txt_blk):
    return FundSfdrClassification(article=Promise("sfdr-article"), fund=txt_blk.content)


def esg_indicators_deserialize_fund(txt_blk):
    return {"esg-indicator-fund": txt_blk.content}


def sfdr_pdf_extract_2(page):
    lines = pdflines_from_pagedict(page)
    art = SfdrArticle.ART_6
    if (
        len(
            PdfLineSelection.text("obiettivo di investimento sostenibile").select(lines)
        )
        > 0
    ):
        art = SfdrArticle.ART_9
    elif (
        len(
            PdfLineSelection.text(
                "soddisfatte le caratteristiche ambientali e/o sociali promosse"
            ).select(lines)
        )
        > 0
    ):
        art = SfdrArticle.ART_8
    return [PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {"article": art}, "")]


def sfdr_text_filter_2(pdf_blks, _):
    blk = next(iter(pdf_blks))
    return [TextBlock(OneTextBlockType.RELEVANT_BLOCK.name, blk.metadata, blk)]


def sfdr_deserialize_2(txt_blk):
    return {"sfdr-article": txt_blk.metadata["article"]}


# The heading the sustainability-indicator table hangs from.  The pipe runs on two page classes now
# -- the second page of the SFDR annex carries the table whenever the annex is short enough -- so it
# checks the heading itself instead of trusting the class: without it `area_from_bounds` falls back
# to the whole page and builds a table out of the article's prose.
esg_indicators_title = PdfLineSelection.text(
    "stata la prestazione degli indicatori di sostenibi"
)


def esg_indicators_pdf_extract(page):
    lines = pdflines_from_pagedict(page)
    if len(esg_indicators_title.select(lines)) == 0:
        return []
    table_lines = (
        PdfLineSelection.area_from_bounds(
            0.0,
            PdfLineSelection.text("stata la prestazione degli indicatori di sostenibi"),
            1e6,
            PdfLineSelection.text("il prodotto finanziario promuove l'interazione"),
        )
        / (
            PdfLineSelection.text("^ $")
            | PdfLineSelection.text("^  $")
            | PdfLineSelection.area(0.0, 780, 1e6, 1e6)
        )
    ).select(lines)
    if len(table_lines) == 0:
        return []
    rows, cols = zip(
        *get_table_coordinates(
            table_lines,
            algorithm_flags=TablePosAlgorithm.USE_RULER_AREA
            | TablePosAlgorithm.BIG_CELL_RULE,
            col_tolerance=0.0,
            row_tolerance=0.0,
            collapse=True,
        )
    )

    res = []
    for row in sorted(set(rows))[1:]:
        key = " ".join(
            (
                table_lines.text
                for r, c, table_lines in zip(rows, cols, table_lines)
                if row == r and c == 1
            )
        ).strip()
        value = " ".join(
            (
                table_lines.text
                for r, c, table_lines in zip(rows, cols, table_lines)
                if row == r and c == 2
            )
        ).strip()
        res.append((key, value))
    return [PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {k: v for k, v in res}, "")]


def esg_indicators_text_filter(pdf_blks, _):
    if len(pdf_blks) == 0:
        return []
    blk = next(iter(pdf_blks))
    m = blk.metadata
    return [
        TextBlock(OneTextBlockType.RELEVANT_BLOCK.name, {"key": k, "value": v}, blk)
        for k, v in m.items()
    ]


def esg_indicators_deserialize(txt_blk):
    m = txt_blk.metadata
    return FundEsgIndicator(
        fund=Promise(f"esg-indicator-fund"), name=m["key"], value=m["value"]
    )


pipelines = {
    "manco": Pipeline(
        pdf_extract=pdf_filter_manco,
        text_filter=text_filter_manco,
        deserialize=(
            DeserializerManagmentCompanyStandard(),
            DeserializerInvestmentsManagerFromManco(),
        ),
    ),
    "investments": Pipeline(
        pdf_extract=(
            PdfExtractInvestmentsStandard(
                body_set=body_set,
                deselection_list=deselection_list,
            ),
            PdfExtractFundStandard(fund_set),
            PdfExtractCurrencyConstant(Currency.EUR),
        )
    ),
    "merges": Pipeline(
        pdf_extract_change_name,
        text_filter_change_name,
        (deserialize_rename, deserialize_merge),
    ),
    "sfdr_page_1": Pipeline(
        sfdr_pdf_extract_1,
        sfdr_text_filter_1,
        (sfdr_deserialize_1, esg_indicators_deserialize_fund),
    ),
    "sfdr_page_2": Pipeline(sfdr_pdf_extract_2, sfdr_text_filter_2, sfdr_deserialize_2),
    "esg_indicators": Pipeline(
        esg_indicators_pdf_extract,
        esg_indicators_text_filter,
        esg_indicators_deserialize,
    ),
}
