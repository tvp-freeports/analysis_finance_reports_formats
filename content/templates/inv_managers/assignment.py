"""L'assegnazione dei fondi ai gestori: `A5`, e il **solo** posto dove si decide.

# Perché esiste

Un bilancio non dice quasi mai chi gestisce che cosa per intero. Dice le **eccezioni** — i comparti
affidati a un gestore delegato — e lascia intendere il resto: *se non è detto altrimenti, il gestore
è la società di gestione* (`R6`). Quel «resto» è il **residuo**, e calcolarlo è aritmetica di
insiemi che tre formati scrivono oggi a mano, ognuno a modo suo: `fineco_en23_ir` esplicitamente,
`fineco_en23_lux` quasi uguale, `eurizon_en23` di nascosto, come primo elemento di una lista.

Questo modulo è quell'aritmetica scritta una volta. Non legge nessuna pagina: riceve ciò che il
`text_filter` ha già letto — coppie *nome → fondi*, dove i fondi possono mancare — e l'insieme dei
fondi che il job ha visto negli investimenti, e **assegna**.

# Le sette regole, che sono sette righe

Sono `R6` corretta da `R15`, corretta a sua volta da `R21` e `R22`. Sono cambiate tre volte in tre
revisioni, ed è la ragione per cui vivono in un helper Python con i suoi test invece che nel motore:
qui la prossima correzione costa una funzione e sette prove, non una superficie pubblica.

| che cosa dichiara la pagina | che cosa succede | regola |
|---|---|---|
| nessun gestore | tutti i fondi alla società di gestione, **avvisando** | `R6` + `R3` |
| **un** gestore senza fondi | prende lui tutto il residuo; la `manco` resta solo `manco` | `R15` |
| il primo senza fondi, gli altri con | il primo prende il residuo, gli altri i fondi dichiarati | `R15` |
| **più d'uno** senza fondi | il residuo **a tutti quanti**, **avvisando** | `R21` |
| un gestore su **parte** di un comparto | entra per quel comparto **senza toglierlo** al residuo | `R21` |
| più società sotto una sola specificazione | entrano **tutte** | `R21` |
| `SUB-`, `SUB-SUB-`, `SUB-SUB-SUB-` | **appiattiti**: nessun livello, e lo stesso nome è una voce sola | `R22` |

Le righe due e tre sono **la stessa regola** una volta scritta come si deve: *se c'è esattamente un
gestore senza fondi, il residuo è suo*. Quando è anche l'unico dichiarato, il residuo è tutto.

# Che cosa questo modulo non fa

- **non legge la pagina.** Le coppie gliele passa il `text_filter`, che è dove `R23` mette ogni
  interpretazione del testo — riconoscere una parentesi, un connettore `for`, una qualificazione
  temporale `(until …)`. Qui arriva già tutto deciso;
- **non costruisce blocchi.** Quello lo fa `blocks.py`, che è due funzioni sopra questa;
- **non decide quali fondi interessano.** L'insieme `funds` lo passa il chiamante, di solito con il
  decoratore `investment_fund_filter_data` del motore, che lo ricava dagli investimenti già
  estratti — cioè scritto come lo scrivono loro, che è quanto `R24` chiede.
"""

from dataclasses import dataclass, replace

from freeports import log
from freeports.output import InvestmentsManager
from freeports.utils.text_filter import MatchFund


def fund_set(funds):
    """L'insieme di identità di fondo corrispondente a `funds`.

    Accetta ciò che i `text_filter` hanno per le mani: stringhe, `MatchFund`, o qualunque oggetto
    che porti un `.name` (un `Fund` d'uscita, per esempio). Le identità confrontano sé stesse dopo
    normalizzazione profonda, quindi `"Alpha Fund"` e `"ALPHA  fund"` sono lo stesso elemento.
    """
    return frozenset(_fund(f) for f in funds)


def assigned_funds(filter_data):
    """I comparti che i gestori già estratti in questo job si sono presi.

    Una sezione dei gestori che comincia su una pagina e finisce su quella dopo vede, nella seconda,
    i risultati della prima: il residuo va calcolato su ciò che resta. È l'aritmetica che
    `mediolanum_24` ed `eurizon_en23` scrivono a mano prima di ogni `text_filter` di seconda pagina.
    """
    return frozenset(
        MatchFund(name)
        for result in filter_data
        if isinstance(result, InvestmentsManager)
        for name in result.managed_funds
    )


def _fund(value):
    """Una singola identità di fondo, da una stringa, da un `MatchFund` o da un oggetto con nome."""
    if isinstance(value, MatchFund):
        return value
    if isinstance(value, str):
        return MatchFund(value)
    return MatchFund(value.name)


def _content_of(value):
    """Il nome scritto in `value`, che può essere una stringa o un blocco che la porta."""
    if isinstance(value, str):
        return value.strip()
    return str(value.content).strip()


@dataclass(frozen=True)
class Declared:
    """Un gestore **come la pagina lo dichiara**, prima di ogni assegnazione.

    - `name` — il nome, o il blocco da cui viene: passando il blocco, la riga d'uscita conserva la
      pagina da cui è stata letta, che altrimenti si perde;
    - `funds` — i comparti che la pagina gli attribuisce, oppure `None` se la pagina **non lo dice**.
      `None` e l'insieme vuoto non sono la stessa cosa: il primo è il gestore che prende il residuo,
      il secondo è un gestore che non gestisce niente;
    - `partial` — vero quando la specificazione copre **una parte** del comparto e non il comparto
      (CARNE-EN23 p4: *«in charge for the USD nominated securities in the subfund …»*). Il gestore
      entra per quel comparto, ma il comparto **resta** nel residuo, perché il gestore di default
      continua a rispondere del resto.
    """

    name: str
    funds: frozenset = None
    partial: bool = False
    block: object = None

    def __post_init__(self):
        if not isinstance(self.name, str):
            object.__setattr__(self, "block", self.block if self.block is not None else self.name)
            object.__setattr__(self, "name", _content_of(self.name))
        else:
            object.__setattr__(self, "name", self.name.strip())
        if self.funds is not None:
            object.__setattr__(self, "funds", fund_set(self.funds))


@dataclass(frozen=True)
class Assigned:
    """Un gestore **dopo** l'assegnazione: il residuo è stato calcolato, i fondi sono definitivi."""

    name: str
    funds: frozenset
    block: object = None
    is_manco: bool = False


@dataclass(frozen=True)
class Assignment:
    """L'esito di `assign`, cioè tutto ciò che il `text_filter` deve scrivere.

    - `managers` — i gestori, nell'ordine in cui la pagina li dichiara, con la società di gestione
      in coda quando è lei a prendersi il residuo;
    - `funds` — **tutti** i fondi del documento, che sono i `managed_funds` della società di
      gestione: `R26` la vuole uno a molti su tutto, mentre `inv_managers` è molti a molti;
    - `new_funds` — i comparti che un gestore rivendica e che il job non aveva ancora visto. Vanno
      dichiarati come fondi, o le righe che li citano cadono;
    - `to_manco` — vero se la società di gestione è finita fra i gestori, cioè se il residuo non
      aveva nessun altro a cui andare.
    """

    managers: tuple
    funds: frozenset
    new_funds: frozenset
    to_manco: bool


def assign(declared, funds, manco=None, already_assigned=()):
    """Assegna i fondi ai gestori, e restituisce l'[`Assignment`][] che ne esce.

    `declared` sono le coppie lette dalla pagina (`Declared`), `funds` i fondi che il job ha visto,
    `manco` la società di gestione — un nome o il suo blocco — o `None` se il formato non la legge.

    `already_assigned` sono i comparti che **altre pagine dello stesso job** hanno già dato a un
    gestore: una sezione che comincia su una pagina e finisce su quella dopo calcola il residuo su
    ciò che resta, non su tutto. Si ricavano con `assigned_funds(filter_data)`, e non producono
    nessuna riga qui — la riga l'ha già scritta la pagina che li ha letti.

    Avvisa in due casi, che sono i due in cui il dato d'uscita **non** sta scritto nel documento:
    quando il residuo va alla società di gestione (`R3`, valore imposto) e quando più gestori
    restano senza fondi e il residuo va a tutti quanti (`R21`, ambiguità risolta per eccesso).
    """
    funds = fund_set(funds)
    declarations = _flatten(declared)
    declarations = [_respell(d, funds) for d in declarations]
    kept = [d for d in declarations if _is_of_interest(d, funds)]

    claimed = fund_set(already_assigned)
    claimed |= frozenset().union(*[d.funds for d in kept if d.funds is not None and not d.partial])
    named = frozenset().union(*[d.funds for d in kept if d.funds is not None])
    new_funds = named - funds
    residual = funds - claimed

    unspecified = [d for d in kept if d.funds is None]
    managers = [
        Assigned(d.name, residual if d.funds is None else d.funds, d.block)
        for d in kept
    ]
    to_manco = False

    if not unspecified:
        if residual and manco is not None:
            managers.append(Assigned(_content_of(manco), residual, _block_of(manco), is_manco=True))
            to_manco = True
            log.warn_imposed(
                field="investments_manager",
                value=_content_of(manco),
                reason="the residual of a report that names no manager for these funds",
            )
        elif residual:
            log.error(
                "{} funds have no investments manager and the format reads no management company"
                .format(len(residual))
            )
    elif len(unspecified) > 1:
        log.warn(
            "the report names {} managers without saying which funds each has: "
            "every one of them is credited with all {} residual funds"
            .format(len(unspecified), len(residual))
        )

    return Assignment(
        managers=tuple(managers),
        funds=funds | new_funds,
        new_funds=new_funds,
        to_manco=to_manco,
    )


def _flatten(declared):
    """Le dichiarazioni con lo stesso nome fuse in una, l'ordine della pagina conservato (`R22`).

    È ciò che «appiattire i sub-gestori» vuol dire una volta arrivati qui: la gerarchia l'ha già
    tolta il `text_filter`, e quello che resta da fare è non contare due volte la stessa società
    quando compare sotto due etichette. `None` è assorbente — un nome dichiarato una volta senza
    fondi resta il gestore del residuo anche se altrove porta un elenco.
    """
    order = []
    merged = {}
    for d in declared:
        key = d.name
        if key not in merged:
            order.append(key)
            merged[key] = d
            continue
        before = merged[key]
        if before.funds is None or d.funds is None:
            merged[key] = replace(before, funds=None, partial=before.partial and d.partial)
        else:
            merged[key] = replace(
                before,
                funds=before.funds | d.funds,
                partial=before.partial and d.partial,
            )
    return [merged[name] for name in order]


def _respell(declaration, funds):
    """I fondi della dichiarazione riscritti **come li scrivono gli investimenti** (`R24`).

    Le identità si confrontano normalizzate, quindi il fondo è già lo stesso elemento comunque sia
    scritto; ma il nome che finisce nell'uscita è quello dell'elemento tenuto, e deve essere quello
    delle fasi precedenti, non quello della pagina dei gestori. Un comparto che il job non conosce
    resta scritto come lo scrive la pagina: è tutto ciò che si ha.
    """
    if declaration.funds is None:
        return declaration
    known = {f: f for f in funds}
    return replace(declaration, funds=frozenset(known.get(f, f) for f in declaration.funds))


def _is_of_interest(declaration, funds):
    """Se la dichiarazione riguarda il documento, o è rumore da lasciar cadere.

    Un gestore che non nomina nessun fondo riguarda sempre il documento — il residuo è suo. Uno che
    li nomina tutti fuori dall'insieme del job sta parlando d'altro (un altro comparto ombrello, una
    tabella vicina): cade, e lo dice a chi sta scrivendo il formato, perché una riga che manca
    nell'uscita è quasi sempre il `text_filter` (`R12`) e questo è il punto in cui sparisce.
    """
    if declaration.funds is None:
        return True
    if not declaration.funds.isdisjoint(funds):
        return True
    log.debug(
        "'{}' names only funds this job has not seen: dropped".format(declaration.name)
    )
    return False


def _block_of(value):
    """Il blocco da cui `value` viene, o `None` se è solo un nome."""
    return None if isinstance(value, str) else value
