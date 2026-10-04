"""UBS-EN23: la società di gestione, i gestori delegati, e l'articolo SFDR.

`IM-6`, che è la ricetta in cui i **comparti si elencano prima** del gestore:

```
Portfolio Managers
BPER International SICAV                 (tondo)
– Open Selection Defence                 (corsivo)
– Open Selection Growth
…
Banca Cesare Ponti, Milano, Italy        (tondo: è il gestore)
The Management Company delegated to Banca Cesare Ponti S.p.A. …
```

La sezione comincia in fondo alla **colonna di sinistra** di p4, prosegue per tutta la colonna di
destra e finisce a metà della colonna di sinistra di p5: l'ordine di lettura è **per colonne**, e
leggerla per ordinata mescolerebbe due discorsi diversi.

Sulla stessa pagina la sezione scrive i gestori in **due modi**, e per `R27` sono due letture:
l'elenco appena mostrato, e il paragrafo di prosa *«The Management Company delegated to Nordea
Investment Management AB the day to day portfolio management of BPER International SICAV – Low
Duration European Covered Bond.»*, che è l'unico posto in cui tre delegati sono nominati. Senza il
secondo, due comparti finirebbero nel residuo della società di gestione — cioè attribuiti a chi il
documento dice esplicitamente che non li gestisce.

La `manco` sta su p4 come i primi gestori, e quindi nella **stessa pipeline**: due dati sulla
stessa pagina si uniscono nel `text_filter`, che riceve i blocchi di tutt'e tre i `pdf_extract`.

Da p139→p140 arriva `EI-1`, gli **indicatori di sostenibilità scritti a coppie `etichetta: valore`**
in fondo all'allegato SFDR. Ogni misura è scritta due volte, una per il comparto e una per il suo
indice di riferimento, e quella dell'indice non si estrae; e la sezione si ferma prima di
`…and compared to previous periods?`, che ripete le stesse misure dell'esercizio prima. Il comparto
lo nomina l'allegato, cioè la pagina prima, e arriva con una promessa legata al numero di pagina.

Da p14→p16 arriva `FA-9`, il prospetto patrimoniale in cui **la pagina non nomina il comparto**:
il nome sta sul titolo di apertura della sezione del comparto, e fra i due ci stanno il commento
di gestione e la tabella dei tre esercizi. Le distanze misurate sul documento sono **una, due, tre
e quattro pagine**, quindi la promessa con la distanza fissa non serve: si prende il titolo più
vicino che precede, e si prende nel `text_filter` (`carryover.PageCarryover.nearest`).
"""

import re

import carryover
import esg
import inv_managers
import sfdr

from freeports.core import Pipeline, PdfBlock, TextBlock
from freeports.interfaces.pdf_blks import OnePdfBlockType, ResultStandardExtraction
from freeports.interfaces.text_blks import OneTextBlockType
from freeports.standard_funcs.pdf_extract import (
    PdfExtractCurrencyStandard,
    PdfExtractLabelledValueStandard,
    PdfExtractManagmentCompanyStandard,
)
from freeports.standard_funcs.deserialize import (
    DeserializerAssetsStandard,
    DeserializerFundStandard,
    DeserializerInvestmentsManagerStandard,
    DeserializerManagmentCompanyStandard,
)
from freeports.standard_funcs.text_filter import TextFilterAssetsStandard
from freeports.utils.deserialize import to_float
from freeports.utils.pdf_extract import (
    LabelledValueWhere,
    PdfLineSelection,
    get_groups,
    pdflines_from_pagedict,
)
from freeports.utils.text_filter import MatchFund, investment_fund_filter_data

# Il corpo della sezione è tutto da 10: il tondo per i nomi e la prosa, il corsivo per i comparti.
# Il grassetto è delle sole intestazioni, e serve solo a trovare dove la sezione comincia.
_BODY = (
    PdfLineSelection(font="frutiger45light", font_size=(9.5, 10.5))
    | PdfLineSelection(font="frutiger45lightitalic", font_size=(9.5, 10.5))
)
_HEADING = PdfLineSelection(
    font="frutiger45lightbold", font_size=(9.5, 10.5), text="^Portfolio Managers"
)

# Le due colonne, misurate: la sinistra comincia a 84 e finisce a 314, la destra comincia a 325.
# La riga di avvertenza in fondo a p5 le attraversa tutt'e due, e l'ascissa la lascia fuori da sola.
_COLUMNS = (("L", (0.0, 0.0, 320.0, 755.0)), ("R", (320.0, 0.0, 600.0, 755.0)))

_PARAGRAPH = 15.0
"""Lo stacco che separa un paragrafo dal successivo.

Le righe di un paragrafo distano 12 punti, i paragrafi fra 18 e 24: il valore sta in mezzo, e
non può salire. A 20 i due paragrafi di p5 che distano 18,5 si fondono, e il nome del comparto si
porta appresso la frase che lo segue."""


def _columns(lines, top):
    """I blocchi della sezione, **per colonne**, con il paragrafo di ciascuno nei metadati.

    `top` è l'ordinata sotto la quale la colonna di sinistra entra nella sezione; la colonna di
    destra ci entra tutta, perché il discorso della pagina passa di lì dopo aver finito a sinistra.
    La chiave di gruppo porta la colonna, o i paragrafi delle due si confonderebbero: `get_groups`
    conta da zero ogni volta che la si chiama.
    """
    blocks = []
    for tag, area in _COLUMNS:
        column = [
            line
            for line in (_BODY & PdfLineSelection.area(*area)).select(lines)
            if tag == "R" or line.bbox[1] >= top
        ]
        for group, line in zip(get_groups(column, _PARAGRAPH), column):
            blocks.append(
                PdfBlock(
                    OnePdfBlockType.RELEVANT_BLOCK.name,
                    {"group": "{}{}".format(tag, group)},
                    line.text,
                )
            )
    return blocks


def pdf_extract_inv_managers_begin(page):
    """p4: la sezione comincia sotto `Portfolio Managers` e prende anche la colonna di destra."""
    lines = pdflines_from_pagedict(page)
    heading = _HEADING.select(lines)
    top = heading[0].bbox[1] if heading else 0.0
    return _columns(lines, top)


def pdf_extract_inv_managers_end(page):
    """p5: la sezione è già aperta, e finisce dove finisce la colonna di sinistra."""
    lines = pdflines_from_pagedict(page)
    return [block for block in _columns(lines, 0.0) if block.metadata["group"].startswith("L")]


# `umbrella` va dichiarato perché a p4 la riga dell'ombrello è in **tondo** mentre i comparti sono
# in corsivo: un elenco che si riconosce dal trattino non la prenderebbe, e i comparti uscirebbero
# senza il prefisso con cui `funds.csv` li scrive (`R24`).
#
# `strip` toglie la città: questo formato scrive il gestore come `Banca Cesare Ponti, Milano,
# Italy`, cioè la sede dentro la ragione sociale, e l'anagrafica vuole `Banca Cesare Ponti`. La
# prosa lo scriverebbe per esteso — `Banca Cesare Ponti S.p.A.` — ma leggere il nome dalla prosa
# costa piu' di quanto renda, e qui la riga dell'elenco basta. Vale per questo formato e non è una
# regola: su FIDEURAM-EN23 p71 `Vontobel Asset Management S.A., Milan Branch` è **un** nome solo.
read_listed = inv_managers.Adjacent(
    inv_managers.Listing(umbrella="BPER International SICAV"),
    where=inv_managers.Where.ABOVE,
    take=inv_managers.Take.FIRST,
    strip=(r",.*$",),
)

# `for` non c'entra: qui il connettore è tutta la formula, e il nome sta fra le due espressioni.
read_prose = inv_managers.ConnectorLine(
    connector=" the day to day portfolio management of ",
    after="The Management Company delegated to ",
)


def _text_filter(pdf_blks, funds, already_assigned=(), settle=True, manco=None):
    """Le due letture sugli stessi blocchi, e l'assegnazione che le riunisce.

    Un paragrafo di prosa non apre nessun elenco, quindi il primo lettore lo lascia cadere; una
    riga d'elenco non porta la formula, quindi il secondo lascia cadere lei. I nomi che compaiono
    in tutt'e due le letture `assign` li fonde (`R22`).
    """
    relevant = [
        block
        for block in pdf_blks
        if block.type_block == OnePdfBlockType.RELEVANT_BLOCK.name
    ]
    return inv_managers.assign(
        list(read_listed(relevant)) + list(read_prose(relevant)),
        funds,
        manco=manco,
        already_assigned=already_assigned,
        settle=settle,
    )


@investment_fund_filter_data
def text_filter_begin(pdf_blks, funds):
    """p4: i gestori dell'elenco e della prosa, più la società di gestione con tutti i comparti.

    Il residuo qui **non** si decide (`settle=False`): la sezione continua a p5, e deciderlo con
    mezza sezione letta darebbe alla società di gestione comparti che la pagina dopo attribuisce a
    Morgan Stanley.
    """
    assignment = _text_filter(pdf_blks, funds, settle=False)
    manco = next(
        (b for b in pdf_blks
         if b.type_block == ResultStandardExtraction.MANAGEMENT_COMPANY.name),
        None,
    )
    blocks = list(inv_managers.text_blocks(assignment))
    if manco is not None:
        blocks.append(inv_managers.management_company_block(assignment, manco))
    return blocks


def text_filter_end(pdf_blks, filter_data):
    """p5: la sezione finisce, e il residuo si calcola su ciò che p4 non ha già assegnato."""
    assignment = _text_filter(
        pdf_blks,
        inv_managers.fund_set(_funds_of(filter_data)),
        already_assigned=inv_managers.assigned_funds(filter_data),
        manco=_declared_manco(filter_data),
    )
    return inv_managers.text_blocks(assignment)


def _declared_manco(filter_data):
    """La società di gestione che p4 ha già letto, a cui tocca ciò che nessun delegato rivendica."""
    from freeports.output import ManagementCompany

    return next(
        (result.name for result in filter_data if isinstance(result, ManagementCompany)),
        None,
    )


def _funds_of(filter_data):
    """I comparti che gli investimenti hanno visto, come li scrivono loro (`R24`)."""
    from freeports.output import Investment

    return [
        result.fund
        for result in filter_data
        if isinstance(result, Investment) and result.fund
    ]




# ----------------------------------------------------------------------------------------------
# Il prospetto patrimoniale, e il comparto che sta sul titolo di qualche pagina prima (`FA-9`)
# ----------------------------------------------------------------------------------------------

assets_carry = carryover.PageCarryover("ubs-fund")

_FOOT = PdfLineSelection(font="frutiger45light", font_size=(6.5, 7.5)) & (
    PdfLineSelection.area(0.0, 785.0, 200.0, 1e6)
    | PdfLineSelection.area(450.0, 785.0, 1e6, 1e6)
)
"""Il piede, dove sta il numero di pagina **stampato**.

Due bande e non una: il documento è impaginato come un libro, e il numero sta **a sinistra sulle
pagine pari e a destra sulle dispari**. Con la sola banda di sinistra sei sezioni su quattordici
non trovavano il loro numero, e il prospetto restava senza comparto.

Il numero stampato non coincide con quello della pagina del PDF — p16 del file porta stampato
`14` — e non importa: le due pipeline devono solo calcolare la stessa chiave, e il piede è ciò che
tutt'e due vedono.
"""

_TITLE = PdfLineSelection(font="ubsheadline", font_size=(21.0, 23.0))
"""Il titolo del comparto, in corpo 22, che **va a capo** quando il nome è lungo."""

_TOTALS = PdfLineSelection(font="frutiger45lightbold", font_size=(6.5, 7.5))
_STATEMENT = PdfLineSelection(
    font="frutiger45lightbold", font_size=(9.5, 10.5), text="^Statement of Net Assets"
)
_LABEL_ASSETS = _TOTALS & PdfLineSelection(text="^Assets")

# La colonna dei valori comincia oltre 460: fra l'etichetta e il valore la riga porta un blocco
# vuoto a 449,7, e senza questo vincolo `where=RIGHT` prenderebbe quello.
_VALUE = PdfLineSelection.area(460.0, 0.0, 1e6, 1e6)

TOT_ASSETS = "TOT_ASSETS"
LIABILITIES = "LIABILITIES"
NET_ASSETS = "NET_ASSETS"
ASSETS_DATE = "ASSETS_DATE"
ASSETS_PAGE = "ASSETS_PAGE"


def pdf_extract_fund_title(page):
    """Il titolo del comparto, riunito, con il numero di pagina stampato."""
    lines = pdflines_from_pagedict(page)
    number = carryover.page_number(lines, _FOOT)
    parts = sorted(_TITLE.select(lines), key=lambda line: line.bbox[1])
    name = " ".join(part.text.strip() for part in parts if part.text.strip())
    if not name or number is None:
        return []
    return [PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {"page": number}, name)]


@investment_fund_filter_data
def text_filter_fund_title(pdf_blks, investment_funds):
    """Il titolo, e solo se è un comparto d'interesse.

    Il filtro sta qui perché è l'unico posto in cui si può fare: sulla pagina del prospetto il
    comparto arriva da questa promessa, e una promessa non si confronta con niente.
    """
    if not pdf_blks:
        return []
    block = next(iter(pdf_blks))
    name = str(block.content).strip()
    if not name or MatchFund(name=name) not in investment_funds:
        return []
    return [TextBlock.from_content(OneTextBlockType.RELEVANT_BLOCK.name, block.metadata, name)]


def pdf_extract_assets_page(page):
    """Il numero stampato della pagina del prospetto, che serve a ritrovare il titolo."""
    number = carryover.page_number(pdflines_from_pagedict(page), _FOOT)
    return [] if number is None else [PdfBlock(ASSETS_PAGE, {}, str(number))]


pdf_extract_tot_assets = PdfExtractLabelledValueStandard(
    _TOTALS & PdfLineSelection(text="^Total Assets"),
    TOT_ASSETS,
    "tot_assets",
    where=LabelledValueWhere.RIGHT,
    value=_VALUE,
)

pdf_extract_liabilities = PdfExtractLabelledValueStandard(
    _TOTALS & PdfLineSelection(text="^Total Liabilities"),
    LIABILITIES,
    "liabilities",
    where=LabelledValueWhere.RIGHT,
    value=_VALUE,
)

pdf_extract_net_assets = PdfExtractLabelledValueStandard(
    _TOTALS & PdfLineSelection(text="^Net assets at the end of the financial year"),
    NET_ASSETS,
    "net_assets",
    where=LabelledValueWhere.RIGHT,
    value=_VALUE,
)

# `R17`: la data si prende dalla colonna, che qui è la riga dell'etichetta `Assets`.
#
# Il valore si cerca **da quella riga in giù**: la riga sopra porta la valuta alla stessa ascissa,
# e la banda di ordinate che `where=RIGHT` apre sulla scatola dell'etichetta la sfiora — misurato,
# la data sta a 132,4 e `EUR` a 123,4, e senza questo vincolo la data diventa `EUR`.
pdf_extract_assets_date = PdfExtractLabelledValueStandard(
    _LABEL_ASSETS,
    ASSETS_DATE,
    "assets date",
    where=LabelledValueWhere.RIGHT,
    value=_VALUE - PdfLineSelection.area_from_bounds(x0=0.0, y0=0.0, x1=1e6, y1=_LABEL_ASSETS),
)

# La valuta non ha etichetta: sta nella banda fra il titolo del prospetto e la riga `Assets`,
# sulla colonna dei valori. È geometria, ed è per questo che si scrive come un'area e non come
# un'etichetta.
pdf_extract_currency = PdfExtractCurrencyStandard(
    _TOTALS
    & PdfLineSelection.area_from_bounds(x0=450.0, y0=_STATEMENT, x1=1e6, y1=_LABEL_ASSETS)
)

record_assets = carryover.Record(
    currency="CURRENCY_STATEMENT",
    date=ASSETS_DATE,
    tot_assets=TOT_ASSETS,
    liabilities=LIABILITIES,
    net_assets=NET_ASSETS,
)

assets_filter = TextFilterAssetsStandard()


def text_filter_fund_assets(pdf_blks, filter_data):
    """Il prospetto, col comparto preso dal titolo più vicino che precede."""
    page = next((b for b in pdf_blks if b.type_block == ASSETS_PAGE), None)
    if page is None:
        return []
    fund = assets_carry.nearest(filter_data, int(str(page.content)))
    if fund is None:
        return []
    return assets_filter(record_assets(pdf_blks, also={"fund": fund}), filter_data)


def _magnitude(text):
    """Il valore come grandezza: su questo prospetto il passivo porta il meno, ed è tipografia."""
    return abs(to_float(text))



# ----------------------------------------------------------------------------------------------
# Gli indicatori di sostenibilità dell'allegato SFDR (`EI-1`)
# ----------------------------------------------------------------------------------------------

esg_carry = carryover.PageCarryover("ubs-esg-fund")
"""Un veicolo suo, distinto da quello del prospetto patrimoniale.

Sono due dati a cavallo di pagine diverse, e due chiavi separate: le pagine dell'allegato e quelle
dei prospetti sono in parti diverse del documento, e una chiave sola le confonderebbe."""

_ESG_HEADING = PdfLineSelection(font="frutiger45lightbold", font_size=(9.5, 10.5))

# Le voci che portano un dato sono quelle del **secondo** livello dell'elenco, che rientra a 238,9;
# il primo livello sta a 211,9 e porta prosa. La continuazione di una voce rientra a 252,9.
_ESG_ENTRY_LEFT = 245.0
_ESG_BODY_LEFT = 230.0

_ESG_BODY = PdfLineSelection(
    font="frutiger45light", font_size=(9.5, 10.5)
) & PdfLineSelection.area(_ESG_BODY_LEFT, 0.0, 1e6, 1e6)

_ESG_OPENS = _ESG_HEADING & PdfLineSelection.text(
    "^How did the sustainability indicators perform"
)
_ESG_CLOSES = _ESG_HEADING & PdfLineSelection.text("^…and compared to previous periods")
"""La sezione si ferma qui, perché sotto le stesse misure sono ripetute per l'esercizio prima.

È la stessa scelta di FINECO-EN23@IR: lo stesso indicatore dello stesso comparto uscirebbe due
volte senza niente che distingua i due valori.
"""


def pdf_extract_esg(page):
    """Le voci della sezione, una per gruppo, con il numero di pagina stampato.

    Una voce comincia dove l'elenco rientra di meno — la riga del trattino `o`, a 238,9 — e
    continua nelle righe che rientrano di più, a 252,9: è così che il valore, che sta sulla riga
    dopo l'etichetta, resta attaccato alla sua etichetta. Il gruppo è geometria, e sta qui (`R23`).
    """
    lines = pdflines_from_pagedict(page)
    opens = _ESG_OPENS.select(lines)
    if not opens:
        return []
    closes = _ESG_CLOSES.select(lines)
    start = opens[0].bbox[1]
    end = closes[0].bbox[1] if closes else 1e6
    number = carryover.page_number(lines, _FOOT)

    blocks = []
    group = -1
    for line in sorted(_ESG_BODY.select(lines), key=lambda line: line.bbox[1]):
        if not line.text.strip() or not start < line.bbox[1] < end:
            continue
        if line.bbox[0] < _ESG_ENTRY_LEFT:
            group += 1
        if group < 0:
            continue
        blocks.append(
            PdfBlock(
                OnePdfBlockType.RELEVANT_BLOCK.name,
                {"group": group, "page": number},
                line.text,
            )
        )
    return blocks


read_esg = esg.LabelledPairs(
    # L'indice di riferimento è scritto con la stessa formula del comparto: `of the benchmark` è
    # l'unica cosa che le distingue, e il valore dell'indice non è un dato del comparto.
    drop=(r"of the benchmark",),
    # Il trattino dell'elenco e la coda che dice di chi è la misura non fanno parte del nome.
    strip=(r"^o\s+", r"\s+of the financial product$"),
)

text_filter_esg = esg.text_filter(read_esg, esg_carry.owner())


def pdf_extract_esg_fund(page):
    """Il nome del prodotto dell'allegato, col numero di pagina, per la pagina degli indicatori."""
    number = carryover.page_number(pdflines_from_pagedict(page), _FOOT)
    if number is None:
        return []
    blocks = []
    for pipe in sfdr.ENGLISH.product_pipes(None, None):
        for block in pipe(page):
            if block.type_block != sfdr.PRODUCT_BLOCK:
                continue
            name = str(block.content)
            name = re.sub(r"^\s*Product name\s*:?\s*", "", name)
            name = re.sub(r"\s*\((?:the|il|la)\s[^)]*\)\s*$", "", name).strip()
            if name:
                blocks.append(
                    PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {"page": number}, name)
                )
    return blocks


@investment_fund_filter_data
def text_filter_esg_fund(pdf_blks, investment_funds):
    """Il nome, e solo se è un comparto d'interesse: di là il comparto è una promessa."""
    for block in pdf_blks:
        name = str(block.content).strip()
        if name and MatchFund(name=name) in investment_funds:
            return [
                TextBlock.from_content(
                    OneTextBlockType.RELEVANT_BLOCK.name, block.metadata, name
                )
            ]
    return []


pipelines = {
    "esg_fund": Pipeline(pdf_extract_esg_fund, text_filter_esg_fund, esg_carry.deposit),
    "esg_indicators": Pipeline(pdf_extract_esg, text_filter_esg, esg.deserialize),
    "fund_title": Pipeline(
        pdf_extract=pdf_extract_fund_title,
        text_filter=text_filter_fund_title,
        deserialize=assets_carry.deposit,
    ),
    "fund_assets": Pipeline(
        pdf_extract=(
            pdf_extract_assets_page,
            pdf_extract_currency,
            pdf_extract_assets_date,
            pdf_extract_tot_assets,
            pdf_extract_liabilities,
            pdf_extract_net_assets,
        ),
        text_filter=text_filter_fund_assets,
        deserialize=DeserializerAssetsStandard(num_converter=_magnitude),
    ),
    "manco": Pipeline(
        pdf_extract=(
            PdfExtractManagmentCompanyStandard(
                PdfLineSelection.area_from_movewindow(
                    PdfLineSelection(font="frutiger45lightbold",font_size=(9.9,10.1),text="Management Company and Domiciliation Agent"),
                    (-0.2,1.9),1.1,1.3
                )
            ),
            pdf_extract_inv_managers_begin,
        ),
        text_filter=text_filter_begin,
        deserialize=(
            DeserializerManagmentCompanyStandard(),
            DeserializerInvestmentsManagerStandard(),
            DeserializerFundStandard(),
        ),
    ),
    "inv_managers_end": Pipeline(
        pdf_extract=pdf_extract_inv_managers_end,
        text_filter=text_filter_end,
        deserialize=(
            DeserializerInvestmentsManagerStandard(),
            DeserializerFundStandard(),
        ),
    ),
}
