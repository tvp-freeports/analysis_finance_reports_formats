"""The investments table of EURIZON-EN23, tabularised against columns read off the page.

The body of this format's portfolio tables is regular except in one respect: the column of company
names is **left**-aligned, and the names differ enormously in length. `HESS CORP.` is thirty-five
points wide, `CONSTELLATION ENERGY CORP.` is ninety-seven, and they begin at the same `x`. The
tabularizer groups a column around a ruler cell, and no single name overlaps all the others, so the
one column comes out as three — which shifts every offset the text filter reads from the anchor and
turns a market value into a percentage.

A tolerance wide enough to reunite them is not the answer: measured over the whole format it costs
two thousand rows, because the same width welds columns that are legitimately close on other pages.

So the columns are not guessed here, they are **read off the page**: cells that overlap horizontally
belong to the same column, and the relation is followed transitively — `HESS CORP.` reaches
`TARGA RESOURCES CORP.` through `CONSTELLATION ENERGY CORP.`. The bands that come out are handed to
the tabularizer as an explicit `TableConfig`, which is a thing the engine already accepts. Nothing
in the engine changes, and no other format is affected.
"""

from freeports.core import PdfBlock
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.standard_funcs.pdf_extract import (
    PdfExtractCurrencyStandard,
    PdfExtractFundStandard,
)
from freeports.utils.pdf_extract import (
    ColumnConfig,
    Limits,
    PdfLineSelection,
    TableConfig,
    TablePosAlgorithm,
    get_table_coordinates,
    pdflines_from_pagedict,
)

# The three selections that used to sit in `args.csv` and `deselection_lists.csv`. They moved here
# with the pipe: the structured level configures the segments it still owns, and a segment is
# configured in one place or the other, never half in each.
body_set = PdfLineSelection(font="Frutiger-Light", area=(0.0, 160.0, 1e6, 765.0))
subfund_set = PdfLineSelection(font="Frutiger-Black", area=(0.0, 0.0, 1e6, 85.0))
# The interval is the one `[11.9735]` means in the compact grammar: the size, give or take the
# thousandth that separates it from a neighbouring size.
currency_set = PdfLineSelection(
    font="Frutiger-Black", font_size=(11.9725, 11.9745), text="PORTFOLIO AS AT"
)

# A footnote runs the width of the page and a lone asterisk sits in the margin: either of them
# bridges two columns, and a bridge is the one thing that defeats reading the columns off the page.
deselection_list = [
    PdfLineSelection(font="Frutiger-Light", area=(0.0, 160.0, 1e6, 765.0), text=t)
    for t in ("^*", "The price of this", "security is in default")
]


def _body_lines(page):
    selection = body_set
    for deselection in deselection_list:
        selection = selection / deselection
    return selection.select(pdflines_from_pagedict(page))


def _merge(spans):
    """The maximal runs of overlapping `x` intervals, from a sorted list of them."""
    bands = []
    low, high = spans[0]
    for x0, x1 in spans[1:]:
        if x0 <= high:
            high = max(high, x1)
        else:
            bands.append((low, high))
            low, high = x0, x1
    bands.append((low, high))
    return bands


def column_bands(lines):
    """The page's columns, as the maximal runs of horizontally overlapping cells.

    Transitive on purpose. Two cells share a column when their `x` intervals meet, and a chain of
    such meetings is still one column — which is exactly what a left-aligned column of names of
    very different lengths needs, and what a single ruler cell cannot express.

    Transitivity has one enemy, and it is handled here rather than left to a list to maintain: a
    line that runs across the gap between two columns joins them for everybody. On these pages that
    is always prose and never a cell — a footnote (`Cross umbrella holding, see further information
    in Note 2h.`), a section heading (`Unrealised loss on forward foreign exchange contracts`), a
    column title. So the bands are measured **without** the lines that hold two of them together,
    recognised by the only property that matters: remove one and the page has more columns than it
    had. The line itself is not discarded — it is still a block, and the tabularizer puts it in the
    first band it meets, exactly as before.
    """
    spans = sorted((line.bbox[0], line.bbox[2]) for line in lines)
    # A page can carry two bridges over the same gap, and then neither is visible on its own: a
    # second pass sees the one that the first uncovered. The loop is bounded because every pass
    # that changes anything removes at least one span.
    while True:
        kept = [s for group in _groups(spans) for s in _without_bridges(group)]
        if not kept or len(kept) == len(spans):
            return _partition(_merge(spans if not kept else kept), lines)
        spans = kept


def _groups(spans):
    """The sorted spans split into the bands they currently form."""
    groups, current, high = [], [spans[0]], spans[0][1]
    for span in spans[1:]:
        if span[0] <= high:
            current.append(span)
            high = max(high, span[1])
        else:
            groups.append(current)
            current, high = [span], span[1]
    groups.append(current)
    return groups


def _without_bridges(group):
    """One band's spans, minus the ones that alone keep it from falling into several.

    Removing a span can only ever split the band it belongs to, so the test is run band by band
    rather than over the whole page: on a table of six columns that is six small problems instead
    of one large one, and the page has a few hundred lines.
    """
    if len(group) < 3:
        return group
    return [s for i, s in enumerate(group) if len(_merge(group[:i] + group[i + 1 :])) == 1]


def _partition(bands, lines):
    """The bands widened until they tile the whole strip the page's cells occupy.

    The bands measure where the columns *are*; a declared column also has to say where everything
    else goes. A line left outside every band — the prose that was set aside above, a stray mark in
    the margin — would make the tabularizer invent a column of its own and then refuse the page for
    having more columns than were declared. So the boundary between two columns is put halfway
    across the gap between them, and the outermost two reach the ends of the strip.
    """
    low = min(line.bbox[0] for line in lines)
    high = max(line.bbox[2] for line in lines)
    cuts = [(left[1] + right[0]) / 2.0 for left, right in zip(bands, bands[1:])]
    edges = [min(low, bands[0][0]), *cuts, max(high, bands[-1][1])]
    return [(a, b) for a, b in zip(edges, edges[1:]) if b > a]


def pdf_extract(page):
    lines = _body_lines(page)
    if not lines:
        return []

    config = TableConfig(
        cols=[ColumnConfig(limits=Limits(low, high)) for low, high in column_bands(lines)]
    )
    # `USE_RULER_AREA` is what makes a declared band capture the cells that *overlap* it. The
    # default predicate asks instead that the band's midpoint fall inside the cell, which a band
    # spanning a whole column of names never does.
    coordinates = get_table_coordinates(
        lines, table_cfg=config, algorithm_flags=TablePosAlgorithm.USE_RULER_AREA
    )

    widths = [line.bbox[2] - line.bbox[0] for line in lines]
    max_width = max(widths)
    return [
        PdfBlock(
            ResultStandardExtraction.TABLE_BODY.name,
            {"table-row": row, "table-col": col, "is-max-width": width == max_width},
            line.text,
        )
        for line, (row, col), width in zip(lines, coordinates, widths)
    ]


pdf_extract_fund = PdfExtractFundStandard(subfund_set)
pdf_extract_currency = PdfExtractCurrencyStandard(currency_set)
