"""Unstructured module for EURIZON-IT24"""

import re

import sfdr

from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.core import Pipeline
from freeports.utils.pdf_extract import (
    PdfLineSelection,
    pdflines_from_pagedict,
    get_groups,
    get_table_coordinates,
    TablePosAlgorithm,
)
from freeports.utils.deserialize import to_date_with_it_month, deserialize_block_type
from freeports.utils.text_filter import MatchFund
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

# `C30`. La valuta e' **scritta**, nell'intestazione della colonna degli importi: `Controvalore in`
# su una riga e `euro` su quella sotto. Prima era imposta dalla configurazione, col suo avviso; ma
# un valore che la pagina dichiara non si impone. La classe `investments` e' ancorata a tutte e due
# le intestazioni (`Titolo` **e** `Controvalore in`), quindi ogni pagina della classe porta anche
# questa riga: il tubo non puo' trovarsi senza niente da leggere.
# La riga **e'** la valuta, quindi la si seleziona per quello che dice e non per dove sta rispetto
# all'intestazione: una finestra mobile misurata su un documento era arrivata corta sull'altro, dove
# il corpo e' 6 invece di 5,99814, e la pagina degli investimenti cadeva per intero — un fondo e
# undici investimenti persi. Il grassetto la distingue dagli `Euro` in tondo del resto del
# documento.
currency_set = PdfLineSelection(
    font="trebuchetmsbold", font_size=(5.5, 6.5), text="^euro$"
)

# La frase apre la sezione e il nome le sta dentro, fino alla prima virgola: `La società di
# gestione EURIZON CAPITAL SGR S.p.A., di seguito "la SGR"...`. E' la stessa forma di FIDEURAM-EN23
# e di ANIMA_SGR-IT24, e dal 2026-09-20 la scrive il template `manco` invece di una regex qui.
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


# Il `text_filter` e il `deserialize` sono del motore: `esg` legge gli indicatori nella forma
# che questa pagina usa e li attacca al comparto, `esg_indicator` costruisce la riga. Quale
# lettore e di chi sia la pagina stanno in
# `content/algorithms/semistructured/args/text_filter.yaml`.


# I due prospetti patrimoniali (`FA-2` e `FA-3`) sono **tutti configurazione**: `currency_constant`
# + `fund` + `labelled_value` nel `pdf_extract`, `labelled_assets` nel `text_filter`,
# `carryover_deposit` e `assets` nel `deserialize`. La geometria delle colonne e il comparto che la
# pagina non nomina stanno nei commenti di `args/pdf_extract.yaml` e `args/text_filter.yaml`.
#
# Anche la `manco` e' configurazione: `labelled_value` sull'ancora `^La società di gestione`, e il
# ritaglio del nome e' l'`after`/`before` dell'algoritmo `manco`.


pipelines = {
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
    "sfdr_classification": sfdr.ITALIAN.pipeline(
        product="Nome prodotto",
        product_prefix=re.compile(r"Nome prodotto\s*:\s*"),
        made="ha effettuato investimenti sostenibili",
        promoted="ha promosso caratteristiche Ambientali",
        also_deserialize=(esg_indicators_deserialize_fund,),
    ),
    "esg_indicators": Pipeline(
        esg_indicators_pdf_extract,
    ),
}
