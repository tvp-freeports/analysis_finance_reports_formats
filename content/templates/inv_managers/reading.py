"""Come una pagina lega un gestore ai suoi comparti: i lettori che precedono l'assegnazione.

# Che cosa sta qui e che cosa sta altrove

`assignment.py` **assegna** e non legge: riceve coppie *nome → comparti* e decide di chi è il
residuo. Questo modulo è il pezzo che manca dall'altra parte — **costruisce quelle coppie** leggendo
i blocchi che il `pdf_extract` ha estratto dalla sezione dei gestori.

Sedici formati dichiarano qualcosa da leggere, e non lo scrivono allo stesso modo. Per `R27` sono
pipeline diverse che condividono il `pdf_extract` e divergono qui, nel `text_filter` — la stessa
struttura che `A7` ha per le ridenominazioni.

| come la pagina lega il gestore ai suoi comparti | lettore | misurato su |
|---|---|---|
| la specificazione sta **sotto** il nome, fra parentesi | `Adjacent(where=BELOW)` | MEDIOLANUM-IT24.A p5 · EURIZON-EN23 p9 · CARNE-EN23 p4 |
| la specificazione sta **sopra**, e copre le società che seguono | `Adjacent(where=ABOVE)` | FINECO-EN23@LUX p6 |
| i comparti elencati **prima**, poi il gestore, poi la frase che conferma | `Adjacent(where=ABOVE, take=FIRST, spec=Listing(...))` | UBS-EN23 p4–5 |
| **sulla riga**, `<gestore> for <comparti>` | `ConnectorLine` | FIDEURAM-EN23 p71 |
| **una riga per comparto** in tabella | `Table` | FINECO-EN23@IR p155 |

Le prime tre righe sono **un lettore solo**. Il piano ne contava due — `…Adjacent` e `…Block` — e
misurandole si è visto che la differenza fra UBS-EN23 e FINECO-EN23@LUX non è la struttura ma due
parametri: *dove* sta la specificazione rispetto al nome, e *quante* società ne dipendono. Vale
la pena dirlo perché la seconda differenza è l'unica che conta davvero: sotto la specificazione di
FINECO-EN23@LUX stanno **tre** società, sotto quella di UBS-EN23 una sola, seguita da un paragrafo
di prosa nello stesso carattere del nome.

# Il gruppo è il parametro nascosto

Un'entrata della pagina non è una riga: è un nome, il suo indirizzo, e la specificazione. Ciò che le
separa è **lo spazio verticale**, che è geometria e quindi `R23` la mette nel `pdf_extract`. I
lettori qui la leggono dai metadati, sotto la chiave `group_key`, e **se non c'è trattano ogni
blocco come un'entrata a sé** — che è la condizione giusta quando il `pdf_extract` ha già separato
nome e specificazione in due tipi di blocco, come fa EURIZON-EN23.

Quando invece i gruppi ci sono, un cambio di gruppo **chiude una specificazione rimasta aperta**.
Non è una raffinatezza: MEDIOLANUM-IT24.A p5 scrive `(Mediolanum Global Impact` **senza parentesi
chiusa**, e chiudere al gruppo recupera un'assegnazione che si perderebbe.
"""

from dataclasses import dataclass
from enum import Enum, auto

from freeports import log

from .assignment import Declared

NOTE_MARKS = "*†‡¹²³⁴⁵"
"""I richiami di nota che si tolgono dal nome di un comparto (`R16`, `U3`).

Le identità di fondo si confrontano dopo normalizzazione profonda, ma la normalizzazione **non**
toglie un asterisco: `MatchFund("Global High Yield*")` e `MatchFund("Global High Yield")` sono due
elementi diversi. Il richiamo va tolto qui, leggendo, o il comparto non si riconosce.
"""


class Where(Enum):
    """Dove sta la specificazione rispetto al nome del gestore."""

    BELOW = auto()
    ABOVE = auto()


class Take(Enum):
    """Quante società dipendono da una specificazione che le precede."""

    FIRST = auto()
    ALL = auto()


@dataclass(frozen=True)
class Parenthetical:
    """La specificazione è una **frase fra parentesi**, che può andare a capo più volte.

    - `markers` — la frase che precede l'elenco, da togliere. Si provano **nell'ordine**, quindi il
      marcatore più lungo va per primo: FINECO-EN23@LUX scrive sia `(Only in respect of the
      Sub-Fund X)` sia `(Only in respect of A, B and C)`, e cercare il corto per primo lascerebbe
      `the Sub-Fund X` come nome di comparto;
    - **se nessun marcatore corrisponde, la specificazione non nomina comparti** e la dichiarazione
      resta *senza fondi*, cioè prende il residuo. È il caso della prima voce di EURIZON-EN23 p9,
      dove la frase fra parentesi dice *quando* un delegato è subentrato e non *che cosa* gestisce;
    - `partial_markers` — la frase che dice «solo una parte del comparto». CARNE-EN23 p4: *«in
      charge for the USD nominated securities in the subfund …»*. Il gestore entra per quel
      comparto, ma il comparto **resta** nel residuo (`R21`);
    - `block_type` — quando il `pdf_extract` ha già separato la specificazione in un tipo di blocco
      suo, il riconoscimento è per tipo e non per parentesi.
    """

    markers: tuple = ()
    partial_markers: tuple = ()
    separators: tuple = (",", " and ")
    opener: str = "("
    closer: str = ")"
    block_type: str = None
    note_marks: str = NOTE_MARKS

    def opens(self, block):
        """Se questo blocco apre una specificazione."""
        if self.block_type is not None:
            return block.type_block == self.block_type
        return _text(block).startswith(self.opener)

    def continues(self, block, accumulated):
        """Se questo blocco fa ancora parte della specificazione cominciata prima."""
        if self.block_type is not None:
            return block.type_block == self.block_type
        return accumulated.count(self.opener) > accumulated.count(self.closer)

    def read(self, lines):
        """I comparti della specificazione, o `None` se non ne nomina, più il flag di parzialità."""
        text = " ".join(line for line in (part.strip() for part in lines) if line)
        partial = any(marker in text for marker in self.partial_markers)
        body = text
        if body.startswith(self.opener):
            body = body[len(self.opener):]
        if self.closer in body:
            body = body.rsplit(self.closer, 1)[0]
        if self.markers:
            for marker in self.markers:
                position = body.find(marker)
                if position >= 0:
                    body = body[position + len(marker):]
                    break
            else:
                log.debug(
                    "'{}' names no sub-fund: the manager it belongs to takes the residual"
                    .format(text)
                )
                return None, partial
        return _split(body, self.separators, self.note_marks), partial


@dataclass(frozen=True)
class Listing:
    """La specificazione è un **elenco**, un comparto per riga, sotto il nome di un ombrello.

    UBS-EN23 p4–5 scrive `BPER International SICAV` e sotto `– Open Selection Defence`, `– Open
    Selection Growth`… Il nome che serve è la composizione dei due, e le identità di fondo la
    riconoscono: `BPER International SICAV – Open Selection Defence` e la riga di `funds.csv`
    normalizzano allo stesso elemento.

    `umbrella` si può dichiarare, e va dichiarato quando la riga dell'ombrello **non arriva fra i
    blocchi**: a p4 di UBS-EN23 è in tondo mentre i comparti sono in corsivo, quindi una selezione
    sul corsivo la lascia fuori; a p5 è in corsivo come loro e si legge da sola.

    Perché la riga dell'ombrello si legga da sola serve però `block_type`: senza, l'elenco si
    riconosce dal prefisso delle sue voci, e una riga che quel prefisso non ce l'ha non entra
    nell'elenco affatto. Le due strade coprono le due pagine, e nessuna delle due copre l'altra.
    """

    block_type: str = None
    item_prefix: str = "–"
    umbrella: str = None
    note_marks: str = NOTE_MARKS

    def opens(self, block):
        """Se questo blocco apre un elenco."""
        if self.block_type is not None:
            return block.type_block == self.block_type
        return _text(block).startswith(self.item_prefix)

    def continues(self, block, accumulated):
        """Un elenco continua finché continuano le righe che lo compongono."""
        return self.opens(block)

    def read(self, lines):
        """I comparti dell'elenco, composti con l'ombrello, e mai parziali."""
        umbrella = self.umbrella
        funds = []
        for line in (part.strip() for part in lines):
            if not line:
                continue
            if not line.startswith(self.item_prefix):
                if self.umbrella is None:
                    umbrella = line
                continue
            item = line[len(self.item_prefix):].strip()
            funds.append("{} {}".format(umbrella, item) if umbrella else item)
        return _split("\n".join(funds), ("\n",), self.note_marks), False


@dataclass(frozen=True)
class Adjacent:
    """La specificazione sta **accanto** al nome — sotto, o sopra e valida per chi segue.

    - `where` — `BELOW` è la forma comune: il nome apre l'entrata e la specificazione la chiude.
      `ABOVE` è quella in cui la specificazione apre uno *scopo*, e le società che seguono ci
      ricadono dentro;
    - `take` — quante società ricadono nello scopo di una specificazione `ABOVE`. `ALL` fino alla
      prossima specificazione (FINECO-EN23@LUX p6: una specificazione, **tre** società), `FIRST`
      solo la prima (UBS-EN23, dove dopo il nome c'è un paragrafo di prosa nello stesso carattere).

    Di ogni entrata si prende **la prima riga che non è specificazione**: le altre sono l'indirizzo,
    che nessuno chiede. Un'entrata senza specificazione è un gestore *senza fondi dichiarati*, cioè
    quello a cui `assignment.assign` dà il residuo (`R15`).
    """

    spec: object
    where: Where = Where.BELOW
    take: Take = Take.ALL
    group_key: str = "group"

    def __call__(self, blocks):
        """Le dichiarazioni lette dai blocchi, nell'ordine in cui la pagina le scrive."""
        events = _scan(blocks, self.spec, self.group_key)
        return _below(events) if self.where is Where.BELOW else _above(events, self.take)


def _below(events):
    """Il nome apre l'entrata, la specificazione la chiude e gli si attacca."""
    declarations = []
    named = False
    for kind, payload in events:
        if kind is _ENTRY:
            named = False
        elif kind is _SPEC:
            if declarations:
                declarations[-1] = _merge(declarations[-1], payload)
            else:
                log.debug("a specification opens the section before any manager is named")
        elif not named:
            named = True
            declarations.append(_declared(payload, None))
    return declarations


def _above(events, take):
    """La specificazione apre uno scopo, e le società che seguono ci ricadono dentro."""
    declarations = []
    pending = None
    taken = 0
    named = False
    for kind, payload in events:
        if kind is _ENTRY:
            named = False
        elif kind is _SPEC:
            pending, taken = payload, 0
        elif not named:
            named = True
            if pending is None:
                log.debug("'{}' is named before any specification: dropped".format(_text(payload)))
            elif take is Take.ALL or not taken:
                declarations.append(_declared(payload, pending))
                taken += 1
    return declarations


@dataclass(frozen=True)
class ConnectorLine:
    """`<gestore> for <comparti>`: la riga dice tutto, e un connettore la divide in due.

    FIDEURAM-EN23 p71 mette tredici righe di questa forma una sotto l'altra. I due lati si separano
    diversamente, e la ragione sta nella pagina: `Vontobel Asset Management S.A., Milan Branch` è
    **un** gestore con una virgola dentro, mentre l'elenco dei comparti le virgole le usa per
    separare. Perciò a sinistra si divide solo su ` and `, a destra anche sulla virgola.

    Un gestore può esserci due volte su righe diverse, e due gestori possono stare sulla stessa
    riga (`FIL Investments International and FIL (Luxembourg) S.A. for …`): ciascuno diventa una
    dichiarazione, e `assignment.assign` le fonde per nome (`R22`).
    """

    connector: str = " for "
    manager_separators: tuple = (" and ",)
    fund_separators: tuple = (",", " and ")
    terminators: str = ",.;"
    group_key: str = "group"
    note_marks: str = NOTE_MARKS

    def __call__(self, blocks):
        """Le dichiarazioni lette dai blocchi, una o più per riga."""
        declarations = []
        for entry in _entries(blocks, self.group_key):
            text = " ".join(line for line in (_text(block) for block in entry) if line)
            if self.connector not in text:
                log.debug("'{}' carries no '{}': dropped".format(text, self.connector.strip()))
                continue
            names, funds = text.split(self.connector, 1)
            funds = _split(funds.strip().rstrip(self.terminators), self.fund_separators,
                           self.note_marks)
            for name in _split(names, self.manager_separators, ""):
                declarations.append(Declared(name, funds=funds, block=entry[0]))
        return declarations


@dataclass(frozen=True)
class Table:
    """Una riga per comparto: il gestore sta in una colonna, il comparto in un'altra.

    FINECO-EN23@IR p155 elenca trentacinque comparti con la data di avvio e il gestore, e lo stesso
    gestore torna su molte righe. Le colonne le scopre il `pdf_extract` (`A2` con `rows=True`, che
    scrive `table-row` e `table-col` nei metadati); qui si dice solo **quali** delle colonne servono.
    """

    fund_col: int = 0
    manager_col: int = 1
    row_key: str = "table-row"
    col_key: str = "table-col"
    note_marks: str = NOTE_MARKS

    def __call__(self, blocks):
        """Le dichiarazioni lette dalla tabella, una per gestore distinto."""
        rows = {}
        for block in blocks:
            if self.row_key not in block.metadata or self.col_key not in block.metadata:
                continue
            row = rows.setdefault(int(block.metadata[self.row_key]), {})
            row[int(block.metadata[self.col_key])] = block
        order = []
        funds = {}
        origin = {}
        for _, cells in sorted(rows.items()):
            fund, manager = cells.get(self.fund_col), cells.get(self.manager_col)
            if fund is None or manager is None:
                continue
            name = _text(manager)
            if name not in funds:
                order.append(name)
                funds[name] = []
                origin[name] = manager
            funds[name].append(_clean(_text(fund), self.note_marks))
        return [
            Declared(origin[name], funds=[f for f in funds[name] if f])
            for name in order
        ]


_ENTRY = object()
"""Comincia un'entrata della pagina: un nome nuovo può aprirsi qui."""

_SPEC = object()
"""Una specificazione si è chiusa: porta con sé i comparti che nomina."""

_TEXT = object()
"""Un blocco che non è specificazione — il nome, oppure l'indirizzo che lo segue."""

_NOTHING = object()
"""Nessun gruppo ancora visto, che non è lo stesso di «gruppo assente»."""


def _scan(blocks, spec, group_key):
    """I blocchi della pagina letti come eventi: entrata, specificazione, testo.

    Una specificazione **attraversa** i confini d'entrata quando la pagina non porta i gruppi, e si
    chiude su un confine quando li porta: senza i gruppi una frase fra parentesi che va a capo
    verrebbe spezzata in tre pezzi (EURIZON-EN23 p9 ne ha una lunga trentuno righe), con i gruppi
    una parentesi mai chiusa rimarrebbe aperta per il resto della pagina (MEDIOLANUM-IT24.A p5).
    """
    grouped = any(_group_of(block, group_key) is not None for block in blocks)
    lines = []
    previous = _NOTHING
    for block in blocks:
        group = _group_of(block, group_key)
        if not grouped or previous is _NOTHING or group != previous:
            previous = group
            if lines and grouped:
                yield _SPEC, _closed(spec, lines)
                lines = []
            yield _ENTRY, None
        if lines and spec.continues(block, " ".join(lines)):
            lines.append(_text(block))
            continue
        if lines:
            yield _SPEC, _closed(spec, lines)
            lines = []
        if spec.opens(block):
            lines = [_text(block)]
            continue
        yield _TEXT, block
    if lines:
        yield _SPEC, _closed(spec, lines)


def _closed(spec, lines):
    """La specificazione letta, dicendolo se la pagina non l'ha mai chiusa."""
    text = " ".join(lines)
    closer = getattr(spec, "closer", None)
    if closer is not None and text.count(spec.opener) > text.count(closer):
        log.debug("'{}' is never closed: read as it stands, to the end of its entry".format(text))
    return spec.read(lines)


def _entries(blocks, group_key):
    """I blocchi divisi in entrate: per gruppo se i metadati lo dicono, altrimenti uno per uno.

    Senza la chiave di gruppo ogni blocco è un'entrata a sé, che è la lettura giusta quando il
    `pdf_extract` ha già separato per tipo ciò che la geometria separerebbe.
    """
    entries = []
    previous = None
    for block in blocks:
        group = _group_of(block, group_key)
        if group is None or previous is None or group != previous:
            entries.append([])
        entries[-1].append(block)
        previous = group
    return entries


def _group_of(block, group_key):
    """Il gruppo del blocco, o `None` se il `pdf_extract` non ne ha messo uno."""
    try:
        return block.metadata[group_key]
    except (KeyError, TypeError, IndexError):
        return None


def _declared(block, spec):
    """Una dichiarazione dal blocco del nome e dalla specificazione che gli tocca."""
    funds, partial = (None, False) if spec is None else spec
    return Declared(block, funds=funds, partial=partial)


def _merge(declaration, spec):
    """La specificazione arrivata dopo, attaccata alla dichiarazione che l'aspettava."""
    funds, partial = spec
    if funds is None:
        return declaration
    before = () if declaration.funds is None else declaration.funds
    return Declared(
        declaration.name,
        funds=frozenset(before) | frozenset(funds),
        partial=partial if declaration.funds is None else declaration.partial and partial,
        block=declaration.block,
    )


def _split(text, separators, note_marks):
    """Il testo diviso su tutti i separatori, ripulito, senza i pezzi vuoti."""
    parts = [text]
    for separator in separators:
        parts = [piece for part in parts for piece in part.split(separator)]
    return tuple(name for name in (_clean(part, note_marks) for part in parts) if name)


def _clean(text, note_marks):
    """Un nome senza spazi di troppo e senza il richiamo di nota che lo segue (`R16`)."""
    return text.strip().rstrip(note_marks).strip() if note_marks else text.strip()


def _text(block):
    """Il testo del blocco, senza gli spazi che la riga del PDF si porta dietro."""
    return str(block.content).strip()
