"""Modulo d'autore di AMUNDI-EN24: il modulo periodico SFDR, e cinque altri dati.

Centotre moduli, il blocco piu' numeroso dei documenti di prova, tutti con una `X` di testo in
Calibri-Bold. Due cose lo distinguono dagli altri nove formati:

- **due moduli su centotre scrivono le etichette in francese** (`X Oui` / `Non`) con la domanda in
  inglese, ed e' la ragione per cui `sfdr.ENGLISH` porta `Oui`/`Non` fra le etichette;
- il **nome del prodotto va a capo**, sempre: l'etichetta e' su una riga e il nome occupa le due
  righe sotto. `PdfExtractLabelledValueStandard` restituisce un blocco per riga e non le riunisce,
  quindi qui i tubi predefiniti non bastano.

Oltre al modulo, la nota `1 INTRODUCTION` di p510 dichiara le **ridenominazioni** dell'esercizio
(`FC-1`), ed è il caso che il template `renaming` è stato scritto per: tre sezioni una sotto
l'altra con la stessa tipografia — comparti lanciati, ridenominati, liquidati — e solo la seconda
porta un dato.

Da p778 arriva `EI-2`, gli **indicatori di sostenibilità in tabella**: il nome sopra, una riga per
serie — il prodotto e il suo indice di riferimento — e una colonna per esercizio. Si tiene la cella
all'incrocio fra la riga del prodotto e la colonna dell'esercizio in corso; l'indice non è un dato
del comparto e l'esercizio precedente non si estrae (`R5`). Il comparto lo nomina la pagina prima,
e arriva con una promessa legata al numero di pagina.

Da p360 in poi arriva `FA-5`, il prospetto patrimoniale: **due comparti per pagina**, ognuno con
due colonne datate, e **l'intestazione in grassetto è il totale** — la riga si chiama `Assets` e il
numero che porta è il totale dell'attivo, non la prima voce di un elenco. Della coppia di colonne si
tiene quella dell'esercizio in corso (`R5`), e una colonna che porta solo trattini è un comparto che
quell'anno non esisteva: si salta.

Il prospetto sta su **due pagine affiancate**: la sinistra porta il titolo e le etichette di riga,
la destra altri quattro comparti alle **stesse ordinate** e nessuna etichetta. La destra si legge
da sola (`fund_assets_right`), con le finestre agganciate all'intestazione di data della prima
colonna, che su tutte le diciannove destre sta nello stesso punto. Riconoscerla invece non si può
da sola: lo Statement of Operations ha destre composte allo stesso modo, e a distinguerle è solo la
pagina che le precede — che è il mestiere di `compute_page_class`.

La societa' di gestione (`C01`) sta a p7, nel prospetto `Organisation`, sulla **stessa riga**
dell'etichetta che ne dichiara il ruolo:

```
MANAGEMENT COMPANY                                   Amundi Luxembourg S.A.
                                                     5, allée Scheffer
```

L'utente l'aveva vista in copertina, dov'e' in grassetto da 12 e senza etichetta. Si legge invece
da qui, perche' qui una etichetta dice **che cos'e'** quel nome, e perche' tutte le righe di quel
prospetto hanno la stessa forma: `MC-3`, il nome dentro la riga, con il template `manco`.

E da p8→9 arriva `IM-2`, che è la ricetta in cui **l'elenco non dice per quali comparti**: sotto
`INVESTMENT MANAGERS` e `SUB-INVESTMENT MANAGERS` stanno una ventina di società, ciascuna col suo
indirizzo e nessuna con una specificazione. È il ramo 4 di `A5` (`R21`): il residuo va **a tutti
quanti**, e il motore lo dichiara con un avviso, perché non è un dato letto ma una deduzione
presa per eccesso. I due gruppi si leggono insieme, che `R22` vuole i sub-gestori appiattiti.
"""

import re

import carryover
import sfdr
from freeports.core import PdfBlock, Pipeline
from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.core import TextBlock
from freeports.interfaces.text_blks import OneTextBlockType
from freeports.utils.pdf_extract import PdfLineSelection, get_groups, pdflines_from_pagedict
from freeports.utils.text_filter import MatchFund, investment_fund_filter_data

# La sezione è tutta la nota: si apre sull'intestazione in grassetto e si chiude sulla prossima
# intestazione dello stesso carattere, che è il comportamento per difetto di `family`.
# La sezione delle ridenominazioni (`FC-1`) e' configurazione: `section` nel `pdf_extract`.

# `on 15 March 2024` sta nell'intestazione, e vale per tutte le righe che seguono. Le due sezioni
# sorelle non portano il connettore ` into `, quindi chiudono lo scopo invece di aprirne uno.
# Il `text_filter` e il `deserialize` sono del motore: `renaming` legge i cambi nella forma
# che questa sezione usa, tiene quelli che riguardano un comparto del job (`R24`) e converte
# la data. Gli schemi stanno in `content/algorithms/semistructured/args/text_filter.yaml`.

_BOLD = PdfLineSelection(font="arial-boldmt", font_size=(6.5, 7.5))

_COLUMN_EDGE = 198.5
"""L'ascissa dove finisce la colonna delle etichette e comincia quella dei valori.

La pagina dell'organizzazione è fatta a due colonne, e **l'intestazione di sezione e il nome di una
società hanno la stessa tipografia**: `INVESTMENT MANAGERS` e `Amundi Hong Kong Ltd` sono tutt'e
due in `arial-boldmt` 7. Quello che le separa è la colonna — un'intestazione finisce prima del
bordo, un nome lo supera — ed è geometria, quindi sta qui e non nel `text_filter` (`R23`).

Misurato su p8: `INVESTMENT MANAGERS` occupa 42,5–130,4 e `GUARANTOR` 42,5–87,9, mentre
`Amundi Japan` occupa 42,8–246,7 e `Amundi Asset Management S.A.S.` 198,4–312,1.
"""


def compute_page_class(classes):
    """Una pagina destra (`right_facing`) è di `FA-5` solo se la precede la sinistra del prospetto.

    Le altre — le destre dello Statement of Operations — tornano non classificate. Si guarda la
    classe **grezza** della pagina prima, e la 398, il combinato, non ha destra: la 399 è un altro
    prospetto e l'ancora di `right_facing` non la prende.
    """
    return [
        ("fund_assets_right" if i > 0 and classes[i - 1] == "fund_assets" else None)
        if cls == "right_facing"
        else cls
        for i, cls in enumerate(classes)
    ]


def _named(lines, top, bottom):
    """Le righe in grassetto della sezione che sono **nomi di società** e non intestazioni."""
    return [
        PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {}, line.text)
        for line in _BOLD.select(lines)
        # `>= top`, non `> top`: la prima società di una sezione sta **sulla riga
        # dell'intestazione**, alla sua destra, e un confronto stretto la perderebbe.
        if top <= line.bbox[1] < bottom
        and line.bbox[2] > _COLUMN_EDGE
        and line.text.strip()
    ]


def _edge(lines, text, default):
    """L'ordinata dell'intestazione `text`, o `default` se questa pagina non la porta."""
    found = (_BOLD & PdfLineSelection.text(text)).select(lines)
    return found[0].bbox[1] if found else default


def pdf_extract_inv_managers_begin(page):
    """p8: la sezione si apre su `INVESTMENT MANAGERS` e arriva in fondo alla pagina."""
    lines = pdflines_from_pagedict(page)
    return _named(lines, _edge(lines, "^INVESTMENT MANAGERS", 0.0), 1e6)


def pdf_extract_inv_managers_end(page):
    """p9: la sezione è già aperta e si chiude su `INVESTMENT ADVISORS`.

    Ciò che sta in mezzo sono la coda dei gestori e **tutti** i sub-gestori: `R22` li vuole
    appiattiti, quindi la divisione fra i due gruppi qui non serve a niente e non si legge.
    Gli *investment advisors* invece restano fuori: consigliano, non gestiscono.
    """
    lines = pdflines_from_pagedict(page)
    return _named(lines, 0.0, _edge(lines, "^INVESTMENT ADVISORS", 1e6))


# Il `text_filter` e il `deserialize` dei gestori stanno nel livello `semistructured`: il blocco
# **e'** la dichiarazione (`read: named`), e il residuo va a tutti quanti con l'avviso che `R21`
# impone. Le due pagine si trattano allo stesso modo e **non** si passano il conto — qui il residuo
# non e' cio' che resta da dividere, e' l'intero insieme dei comparti, e darne una metà a ciascuna
# pagina scriverebbe una divisione che il documento non fa — e per questo nessuna delle due dichiara
# `already_assigned`.



# ----------------------------------------------------------------------------------------------
# Gli indicatori di sostenibilità, e il comparto che sta sulla pagina prima (`EI-2`)
# ----------------------------------------------------------------------------------------------

esg_carry = carryover.PageCarryover("amundi-esg-fund")

# Il piede porta il numero stampato, che su questo prospetto **coincide** con quello della pagina
# del PDF, e sta a sinistra sulle pari e a destra sulle dispari.
ESG_FOOT = PdfLineSelection.area(0.0, 795.0, 120.0, 1e6) | PdfLineSelection.area(
    480.0, 795.0, 1e6, 1e6
)

_ESG_QUESTION = PdfLineSelection(
    font="calibri-bolditalic", font_size=(8.0, 8.5)
) & PdfLineSelection(text="^How did the sustainability indicators perform")

# La colonna di glossario del modello europeo sta a `x≈38`: la tabella comincia a 212, e l'ascissa
# è ciò che le separa. Dentro la tabella il nome dell'indicatore rientra meno della serie — 212,2
# contro 223,9 — e i valori cominciano oltre 395.
_ESG_TABLE_LEFT = 205.0
_ESG_SERIES_LEFT = 218.0
_ESG_VALUE_LEFT = 395.0

_ESG_ROW = 4.0
"""Lo stacco entro il quale due righe sono la stessa riga di tabella: le righe distano dieci punti."""

_ESG_COLUMN = 12.0
"""Lo scostamento entro il quale due celle sono la stessa colonna.

I bordi destri misurati sono 428,9 e 430,0 per l'esercizio in corso e 465,3 e 466,5 per il
precedente: un punto di differenza fra un numero intero e una percentuale, trentasei fra le due
colonne."""

_ESG_DATE = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{2})\s*$")

_ESG_HEADING = PdfLineSelection(font="calibri-bold")
"""Il titolo di famiglia — `Environmental performance`, `Social performance`, `Governance
performance` — che chiude ciò che sta sopra e non porta valori."""

_ESG_NOTE = PdfLineSelection(font="calibri-italic")
"""Le note di fonte e di unità di misura, che chiudono un blocco: `Source Montpensier Finance …`."""

_ESG_SUB = PdfLineSelection(font="arial-bolditalicmt")
"""Il corsivo grassetto, che la tabella usa per **una sola voce**: `Coverage (% invested)`.

Non è un indicatore di sostenibilità del comparto, è la copertura della *misura* — quanta parte del
portafoglio l'indicatore di sopra ha potuto misurare — e la tabella la ripete sotto ognuno dei sei
blocchi. Estrarla vorrebbe dire scrivere sei righe che si chiamano tutte allo stesso modo per lo
stesso comparto: la chiave d'unicità di `funds_esg_indicators` le farebbe collassare in una, e
quale delle sei sopravvive non lo decide nessuno. Si lascia fuori, e la tipografia è il modo in cui
la pagina stessa la distingue dalle altre.
"""


def _esg_cluster(edges, edge):
    """L'indice del gruppo di `edges` a cui `edge` appartiene, o `None`."""
    for index, known in enumerate(edges):
        if abs(known - edge) <= _ESG_COLUMN:
            return index
    return None


def _esg_columns(values):
    """Le colonne, **ordinate dalla più recente**, dai bordi destri delle righe di data.

    L'ordine non si dà per scontato: la tabella scrive `28/06/24` e `30/06/23` e la più recente è a
    sinistra, ma è una proprietà dell'impaginazione e non una regola. Si legge dalle date, che la
    tabella ripete su ogni blocco, e si confronta `AA MM GG` — due cifre d'anno bastano, che un
    prospetto non porta mai due esercizi a un secolo di distanza.
    """
    dated = {}
    for line in values:
        found = _ESG_DATE.match(line.text)
        if not found:
            continue
        day, month, year = found.groups()
        dated.setdefault(line.bbox[2], (year, month, day))
    if not dated:
        return []
    edges = []
    for edge in sorted(dated, key=lambda e: dated[e], reverse=True):
        if _esg_cluster(edges, edge) is None:
            edges.append(edge)
    return edges


def pdf_extract_esg(page):
    """Una cella per blocco, con dentro quale indicatore, quale serie e quale esercizio.

    Tutto ciò che sta qui è geometria: dove comincia la tabella, quali righe sono nomi e quali
    serie, e in quale colonna cade una cella. *Quale* serie e *quale* colonna si tengano lo decide
    il lettore del template (`R23`).
    """
    lines = pdflines_from_pagedict(page)
    question = _ESG_QUESTION.select(lines)
    if not question:
        return []
    top = question[0].bbox[1]
    body = sorted(
        (
            line
            for line in lines
            if line.bbox[1] > top
            and line.bbox[0] >= _ESG_TABLE_LEFT
            and line.text.strip()
        ),
        key=lambda line: line.bbox[1],
    )
    if not body:
        return []

    values = [line for line in body if line.bbox[0] >= _ESG_VALUE_LEFT]
    columns = _esg_columns(values)
    if not columns:
        return []

    number = carryover.page_number(lines, ESG_FOOT)
    groups = list(get_groups(body, _ESG_ROW))
    blocks = []
    scope = None
    indicator = None
    series = -1
    named = False
    for group in sorted(set(groups)):
        row = [line for index, line in zip(groups, body) if index == group]
        labels = [line for line in row if line.bbox[0] < _ESG_VALUE_LEFT]
        cells = [line for line in row if line.bbox[0] >= _ESG_VALUE_LEFT]
        if labels:
            first = labels[0]
            if _ESG_HEADING.select([first]) or _ESG_NOTE.select([first]):
                scope, indicator, named = None, None, False
                continue
            if first.bbox[0] < _ESG_SERIES_LEFT:
                # Due righe in grassetto una sotto l'altra: la prima è l'ambito e la seconda
                # l'indicatore. `Scopes 1 et 2` apre due indicatori, e l'ambito resta in vigore
                # fino alla nota che chiude il blocco.
                if _ESG_SUB.select([first]):
                    indicator, named = None, False
                    continue
                if named:
                    scope = indicator
                indicator, named, series = first.text.strip(), True, -1
                continue
            named = False
            series += 1
        if indicator is None or series < 0:
            continue
        name = "{} — {}".format(scope, indicator) if scope else indicator
        for cell in cells:
            column = _esg_cluster(columns, cell.bbox[2])
            if column is None:
                continue
            blocks.append(
                PdfBlock(
                    OnePdfBlockType.RELEVANT_BLOCK.name,
                    {
                        "indicator": name,
                        "series": series,
                        "column": column,
                        "page": number,
                    },
                    cell.text,
                )
            )
    return blocks


# Il `text_filter` e il `deserialize` sono del motore: `esg` legge gli indicatori nella forma
# che questa pagina usa e li attacca al comparto, `esg_indicator` costruisce la riga. Quale
# lettore e di chi sia la pagina stanno in
# `content/algorithms/semistructured/args/text_filter.yaml`.


_ESG_PRODUCT_PIPES = sfdr.ENGLISH.joined_pipes()
"""Il tubo del nome del prodotto del template, quello stesso che il modulo SFDR usa qui.

Il nome su questo formato non va solo a capo: il PDF lo spezza in frammenti — `AMUNDI FUNDS
MONTPENSIER `, `G`, `REAT`, `UROPEAN`, `M`, `ODELS` — e riunirli è il lavoro di
`sfdr.joined_pipes`, misurato su cinque formati. Riscriverlo qui sarebbe scriverlo male una
seconda volta; quello che serve in più è soltanto il numero di pagina.
"""

_ESG_PRODUCT_PREFIXES = (
    re.compile(r"^\s*Product name\s*:?\s*"),
    # L'ombrello davanti al comparto: `R24` vuole il nome come lo scrivono gli investimenti.
    re.compile(r"^AMUNDI FUNDS\s+"),
)


def pdf_extract_esg_fund(page):
    """Il nome del prodotto del modulo, col numero di pagina, per la pagina degli indicatori."""
    number = carryover.page_number(pdflines_from_pagedict(page), ESG_FOOT)
    if number is None:
        return []
    blocks = []
    for pipe in _ESG_PRODUCT_PIPES:
        for block in pipe(page):
            if block.type_block != sfdr.PRODUCT_BLOCK:
                continue
            name = str(block.content)
            for prefix in _ESG_PRODUCT_PREFIXES:
                name = prefix.sub("", name).strip()
            if name:
                blocks.append(
                    PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {"page": number}, name)
                )
    return blocks


@investment_fund_filter_data
def text_filter_esg_fund(pdf_blks, investment_funds):
    """Il nome, e solo se è un comparto d'interesse: di là il comparto è una promessa."""
    if not pdf_blks:
        return []
    block = next(iter(pdf_blks))
    name = str(block.content).strip()
    if not name or MatchFund(name=name) not in investment_funds:
        return []
    return [TextBlock.from_content(OneTextBlockType.RELEVANT_BLOCK.name, block.metadata, name)]


pipelines = {
    "esg_fund": Pipeline(
        pdf_extract_esg_fund, text_filter_esg_fund, esg_carry.deposit
    ),
    "esg_indicators": Pipeline(pdf_extract_esg),
    "inv_managers_begin": Pipeline(pdf_extract=pdf_extract_inv_managers_begin),
    "inv_managers_end": Pipeline(
        pdf_extract=pdf_extract_inv_managers_end,
    ),
}
