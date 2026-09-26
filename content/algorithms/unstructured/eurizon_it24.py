"""Unstructured module for EURIZON-IT24"""

import re

import carryover
import esg
import manco
import sfdr

from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractCurrencyConstant,
    PdfExtractFundStandard,
    PdfExtractLabelledValueStandard,
)
from freeports.interfaces.pdf_blks import OnePdfBlockType, ResultStandardExtraction
from freeports.core import Pipeline
from freeports.utils.pdf_extract import (
    LabelledValueWhere,
    PdfLineSelection,
    pdflines_from_pagedict,
    get_groups,
    get_table_coordinates,
    TablePosAlgorithm,
)
from freeports.standard_funcs.text_filter import TextFilterAssetsStandard
from freeports.standard_funcs.deserialize import (
    DeserializerAssetsStandard,
    DeserializerManagmentCompanyStandard,
    DeserializerInvestmentsManagerFromManco
)
from freeports.utils.deserialize import to_date_with_it_month, to_int, deserialize_block_type
from freeports.utils.text_filter import MatchFund
from freeports.consts import Currency
from freeports.core import Promise
from freeports.core import PdfBlock, TextBlock
from freeports.output import (
    Fund,
    FundMerge,
    FundRename,
)
from enum import Enum, auto


class TypeChangeName(Enum):
    MERGING = auto()
    RENAMING = auto()


fund_set = PdfLineSelection(
    font="TrebuchetMSItalic", font_size=(4, 6.5), area=(270, 700, 595, 805)
)

body_set = PdfLineSelection.font("TrebuchetMS")

# La frase apre la sezione e il nome le sta dentro, fino alla prima virgola: `La società di
# gestione EURIZON CAPITAL SGR S.p.A., di seguito "la SGR"...`. E' la stessa forma di FIDEURAM-EN23
# e di ANIMA_SGR-IT24, e dal 2026-09-20 la scrive il template `manco` invece di una regex qui.
pdf_filter_manco = PdfExtractLabelledValueStandard(
    PdfLineSelection.text("^La società di gestione"),
    ResultStandardExtraction.MANAGEMENT_COMPANY.name,
    "managment company",
)

text_filter_manco = manco.text_filter(manco.Between(after="gestione", before=","))


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


def esg_indicators_deserialize_fund(txt_blk):
    return {"esg-indicator-fund": txt_blk.content}


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

    # La tabella ha **tre** colonne: il nome dell'indicatore a sinistra, la descrizione in mezzo —
    # venti righe di prosa — e il valore a destra. Prima di oggi il nome si prendeva dalla colonna
    # di mezzo, e `funds_esg_indicators.csv` portava paragrafi interi al posto dei nomi. Il nome è
    # la **prima** colonna e il valore l'**ultima**; la riga d'intestazione si salta.
    name_col = min(cols)
    value_col = max(cols)
    blocks = []
    for row in sorted(set(rows))[1:]:
        name = " ".join(
            line.text
            for line, r, c in zip(table_lines, rows, cols)
            if r == row and c == name_col
        ).strip()
        value = " ".join(
            line.text
            for line, r, c in zip(table_lines, rows, cols)
            if r == row and c == value_col
        ).strip()
        if not name:
            continue
        blocks.append(
            PdfBlock(
                OnePdfBlockType.RELEVANT_BLOCK.name,
                {"indicator": name, "series": 0, "column": 0},
                value,
            )
        )
    return blocks


read_esg_indicators = esg.DatedRows()
"""Il lettore del template: una cella per indicatore, e `R11` scarta ciò che numero non è.

La tabella non ha né serie né esercizi — un indicatore, un valore — quindi `series` e `column`
valgono zero per tutte le celle, e il lettore fa il solo lavoro che qui serve: tenere le celle che
portano un numero. Prima di oggi non le filtrava nessuno, e il secondo documento di prova scriveva
una riga col nome vuoto e il valore vuoto.
"""


def _esg_owner(_pdf_blks, _filter_data):
    """Il comparto è quello che l'allegato ha depositato: un documento, un comparto."""
    return Promise("esg-indicator-fund")


esg_indicators_text_filter = esg.text_filter(read_esg_indicators, _esg_owner)


# ----------------------------------------------------------------------------------------------
# La situazione patrimoniale, che sta su due pagine (`FA-2` e `FA-3`)
# ----------------------------------------------------------------------------------------------
# Un comparto per documento, e la pagina del prospetto **non lo nomina**: il nome sta sulla pagina
# degli investimenti, che lo `algorithms_schedule.csv` fa girare prima. E' l'altro caso di `U7` —
# un valore che una pagina prende da un'altra — e lo risolve `carryover.sole_fund`, che lo
# dichiara come valore imposto (`R3`) perche' imposto e'.

TOT_ASSETS = "TOT_ASSETS"
LIABILITIES = "LIABILITIES"
NET_ASSETS = "NET_ASSETS"
ASSETS_DATE = "ASSETS_DATE"

# `TOTALE ATTIVITA'` e' in tondo e `TOTALE PASSIVITA'` in nero: due corpi, non uno.
assets_body_set = PdfLineSelection(font="TrebuchetMS", font_size=(5.9, 6.1))
assets_bold_set = PdfLineSelection(font="TrebuchetMSBold", font_size=(5.9, 6.1))

# `R5`: l'esercizio precedente non si estrae. Sull'attivo il valore finisce a 319,6 e la
# percentuale comincia a 352,6; sul passivo il valore finisce a 397,7 e l'esercizio precedente
# comincia a 459,8.
current_year_on_assets = PdfLineSelection.area(0.0, 0.0, 335.0, 1e6)
current_year_on_liabilities = PdfLineSelection.area(0.0, 0.0, 430.0, 1e6)

assets_carryover = carryover.Carryover("tot_assets")

pdf_extract_tot_assets = PdfExtractLabelledValueStandard(
    assets_body_set & PdfLineSelection(text="^TOTALE ATTIVITA'"),
    TOT_ASSETS,
    "tot_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year_on_assets,
)

pdf_extract_liabilities = PdfExtractLabelledValueStandard(
    assets_bold_set & PdfLineSelection(text="^TOTALE PASSIVITA'"),
    LIABILITIES,
    "liabilities",
    where=LabelledValueWhere.RIGHT,
    value=current_year_on_liabilities,
)

# `Valore complessivo netto della classe` e' la classe di quote e sta nello stesso carattere:
# a distinguerla e' solo `del fondo`.
pdf_extract_net_assets = PdfExtractLabelledValueStandard(
    assets_body_set & PdfLineSelection(text="^Valore complessivo netto del fondo"),
    NET_ASSETS,
    "net_assets",
    where=LabelledValueWhere.RIGHT,
    value=current_year_on_liabilities,
)

# `R17`: la data si prende dalla colonna. `Situazione a fine esercizio` e' l'altra.
pdf_extract_assets_date = PdfExtractLabelledValueStandard(
    assets_body_set & PdfLineSelection(text="^Situazione al"),
    ASSETS_DATE,
    "assets date",
    where=LabelledValueWhere.BELOW,
)

record_begin = carryover.Record(currency="CURRENCY_STATEMENT", tot_assets=TOT_ASSETS)

record_end = carryover.Record(
    currency="CURRENCY_STATEMENT",
    date=ASSETS_DATE,
    liabilities=LIABILITIES,
    net_assets=NET_ASSETS,
)

assets_filter = TextFilterAssetsStandard()


def text_filter_fund_assets_begin(pdf_blks, filter_data):
    fund = carryover.sole_fund(filter_data)
    if fund is None:
        return []
    return assets_filter(record_begin(pdf_blks, also={"fund": fund}), filter_data)


def text_filter_fund_assets_end(pdf_blks, filter_data):
    fund = carryover.sole_fund(filter_data)
    if fund is None:
        return []
    blocks = assets_filter(record_end(pdf_blks, also={"fund": fund}), filter_data)
    return assets_carryover.resume(blocks, filter_data)


pipelines = {
    "fund_assets_begin": Pipeline(
        pdf_extract=(
            PdfExtractCurrencyConstant(Currency.EUR),
            pdf_extract_tot_assets,
        ),
        text_filter=text_filter_fund_assets_begin,
        deserialize=assets_carryover.deposit,
    ),
    "fund_assets_end": Pipeline(
        pdf_extract=(
            PdfExtractCurrencyConstant(Currency.EUR),
            pdf_extract_assets_date,
            pdf_extract_liabilities,
            pdf_extract_net_assets,
        ),
        text_filter=text_filter_fund_assets_end,
        deserialize=DeserializerAssetsStandard(to_int),
    ),
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
    # L'articolo si leggeva **fiutando la prosa** della seconda pagina dell'allegato -- se c'era
    # scritto `obiettivo di investimento sostenibile` era il 9, se c'era `soddisfatte le
    # caratteristiche ambientali` era l'8 -- e la prima pagina gli passava il fondo con una
    # promessa. Adesso si legge dalla casella, su una pagina sola e senza promessa.
    #
    # Tre cose di questo formato non sono quelle dell'allegato italiano: l'etichetta del prodotto e'
    # `Nome prodotto` e non `Nome del prodotto`, e le due opzioni della riga sotto cominciano in
    # minuscolo. Il titolo l'allegato non ce l'ha -- su tutti e 200 i moduli della raccolta -- e
    # `R34` non ha niente da verificare.
    "sfdr_page_1": sfdr.ITALIAN.pipeline(
        product="Nome prodotto",
        product_prefix=re.compile(r"Nome prodotto\s*:\s*"),
        made="ha effettuato investimenti sostenibili",
        promoted="ha promosso caratteristiche Ambientali",
        also_deserialize=(esg_indicators_deserialize_fund,),
    ),
    "esg_indicators": Pipeline(
        esg_indicators_pdf_extract,
        esg_indicators_text_filter,
        esg.deserialize,
    ),
}
