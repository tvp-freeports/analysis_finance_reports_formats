"""KAIROS-EN23 format submodule"""

import re

from freeports.standard_funcs.text_filter import (
    TextFilterInvestmentsStandard
)
from freeports.interfaces.text_blks import OneTextBlockType
from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.utils.deserialize import to_int_en_month
from freeports.utils.pdf_extract import (
    PdfLineSelection,
    pdflines_from_pagedict,
    get_table_coordinates,
    TablePosAlgorithm,
)
from freeports.utils.text_filter import MatchFund,investment_fund_filter_data
from freeports.core import Pipeline
from freeports.core import TextBlock, PdfBlock
from freeports.output import (
    FundRename,
    FundMerge,
    Fund,
    FundEsgIndicator,
)
from datetime import date

market_value_regex = re.compile(r"(([0-9]+,)?[0-9]+,?[0-9]+\.[0-9]{2}) ")
# non sono sicuro di come ho riscritto questa regex e a cosa servivano le parentesi

#: Il nome del comparto porta il confronto con l'esercizio prima fra parentesi
#: (`Kairos International Sicav - Bond (2023: 4.21%)`) e, su alcune pagine, un asterisco: niente
#: dei due fa parte del nome. Ripulirlo nei **due** posti in cui finisce -- il blocco del fondo e
#: la chiave `fund` dei metadati di ogni titolo -- lo fa il tubo del motore da quando `C28` gli ha
#: dato `remove_from_fund_regexes`: era un pezzo condiviso del repo, ed e' una parametrizzazione.
FUND_NAME_CUTS = (r"\s*\(.*\)", r"\*")

cleaned_std = TextFilterInvestmentsStandard(
    nominal_quantity_pos=0,
    perc_net_assets_pos=3,
    acquisition_currency_pos=1,
    market_value_pos=2,
    remove_from_fund_regexes=FUND_NAME_CUTS,
)


def remove_fund_excess(txt):
    """Gli stessi tagli su una stringa sola: lo chiama la lettura delle fusioni.

    Il tubo del motore li fa sui blocchi; qui il nome arriva da un'espressione regolare sulla prosa
    della nota, che di blocchi non ne ha.
    """
    for pattern in FUND_NAME_CUTS:
        txt = re.sub(pattern, "", txt)
    return " ".join(txt.split())


def pdf_extract_rename(page):
    lines = pdflines_from_pagedict(page)
    renames = PdfLineSelection.area_from_movewindow(
        PdfLineSelection.text("has changed its name"), (-0.1, 0.0), 1.2, 2.5
    ).select(lines)
    rename = "".join((r.text for r in renames))
    return [PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {}, rename)]


rename_regex = re.compile(
    "As at (.+ [0-9]+, [0-9]+), the Sub-Fund ([^*]+) has changed .+ in ([^*]+)"
)


def text_filter_rename(pdf_blks, filter_data):
    funds = set(
        map(
            lambda x: MatchFund(name=x.name),
            filter(lambda x: isinstance(x, Fund), filter_data),
        )
    )
    m = rename_regex.match(pdf_blks[0].content)
    current_name = MatchFund(m.group(3))
    if current_name in funds:
        return [
            TextBlock(
                OneTextBlockType.RELEVANT_BLOCK.name,
                {
                    "old_name": m.group(2),
                    "current_name": current_name.name,
                    "date": m.group(1),
                },
                pdf_blks[0],
            )
        ]
    else:
        return []


merges_regex = re.compile(r"([^,]+ [0-9]+, [0-9]+), ([^*]+)\*? merged into ([^*,]+)")


def text_filter_merges(pdf_blks, filter_data):
    funds = set(
        map(
            lambda x: MatchFund(name=x.name),
            filter(lambda x: isinstance(x, Fund), filter_data),
        )
    )
    merges = pdf_blks[0].content.split("- On ")[1:]
    res = []
    for mrg in merges:
        m = merges_regex.match(mrg)
        current_name = MatchFund(remove_fund_excess(m.group(3)))
        if current_name in funds:
            old_name = remove_fund_excess(m.group(2))
            date = m.group(1)
            res.append(
                TextBlock(
                    OneTextBlockType.RELEVANT_BLOCK.name,
                    {
                        "old_name": old_name,
                        "current_name": current_name.name,
                        "date": date,
                    },
                    pdf_blks[0],
                )
            )
    return res


def to_date(txt):
    parts = txt.replace(",", "").split()
    return date(int(parts[2]), to_int_en_month(parts[0]), int(parts[1]))


def deserialize_rename(txt_blk):
    md = txt_blk.metadata
    return FundRename(
        old_name=md["old_name"],
        current_name=md["current_name"],
        date=to_date(md["date"]),
    )


def deserialize_merges(txt_blk):
    md = txt_blk.metadata
    return FundMerge(
        old_name=md["old_name"],
        current_name=md["current_name"],
        date=to_date(md["date"]),
    )



def esg_indicators_pdf_extact_art8(page):
    lines = pdflines_from_pagedict(page)
    r = PdfLineSelection.text("RATING").select(lines)
    if len(r) == 0:
        return []
    l = PdfLineSelection.area_from_bounds(
        PdfLineSelection.text("Characteristics promoted"),
        PdfLineSelection.text("Indicator"),
        1e6,
        PdfLineSelection.text("RATING"),
    ).select(lines)
    f = PdfLineSelection.text("Product name: ").select(lines)
    rows, cols = zip(
        *get_table_coordinates(
            l,
            algorithm_flags=TablePosAlgorithm.USE_RULER_AREA
            | TablePosAlgorithm.BIG_CELL_RULE,
            col_tolerance=-0.2,
            row_tolerance=-0.2,
            collapse=True,
        )
    )
    # nrows=max(rows)+1
    # ncols=max(cols)+1
    # blks=[PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name,{"table-row":r,"table-col":c},ll.text) for ll,(r,c) in zip(l,cc)]
    # values=[ll.text for ll,r,c in zip(l,rows,cols) for row in range(n_rows) if c==1 and row==r]

    res = []
    for row in sorted(set(rows)):
        key = "".join(
            (ll.text for r, c, ll in zip(rows, cols, l) if row == r and c == 0)
        ).strip()
        value = "".join(
            (ll.text for r, c, ll in zip(rows, cols, l) if row == r and c == 1)
        ).strip()

        res.append((key, value))
    return [PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {k: v for k, v in res}, f[0].text)]


@investment_fund_filter_data
def esg_indicators_text_filter_art8(pdf_blks, filter_funds):
    if len(pdf_blks) == 0:
        return []
    blk = next(iter(pdf_blks))
    fund_name = blk.content.removeprefix("Product name: ")
    fund = MatchFund(name=fund_name)
    if fund in filter_funds:
        return [
            TextBlock.from_content(
                OnePdfBlockType.RELEVANT_BLOCK.name, {"index": k, "fund": fund_name}, v
            )
            for k, v in blk.metadata.items()
        ]
    else:
        return []


def esg_indicators_deserialize_art8(txt_blk):
    return FundEsgIndicator(
        name=txt_blk.metadata["index"],
        value=txt_blk.content,
        fund=txt_blk.metadata["fund"],
    )


pipelines = {
    # Le due classi di pagina sono due impaginazioni dello stesso allegato, e si leggono con lo
    # stesso modulo: quello che cambia e' come il rapporto intitola l'allegato e come scrive
    # l'etichetta del prodotto.
    "esg_indicators": Pipeline(
        esg_indicators_pdf_extact_art8,
        esg_indicators_text_filter_art8,
        esg_indicators_deserialize_art8,
    ),
    "renaming": Pipeline(pdf_extract_rename, text_filter_rename, deserialize_rename),
    "merges": Pipeline(text_filter=text_filter_merges, deserialize=deserialize_merges),
}
