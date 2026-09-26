"""Il dato che una pagina lascia a quella dopo quando il legame **è la pagina**, non il nome.

# Perché serve un secondo veicolo accanto a `Carryover`

`Carryover` appaia due pagine **col nome del comparto**, perché il prospetto del passivo nomina il
comparto di cui parla. Il modulo periodico europeo non offre questo appiglio: il nome del prodotto
sta in testa al modulo e gli indicatori di sostenibilità sulla pagina **dopo**, che il comparto non
lo nomina affatto. Lì l'unica cosa che lega le due pagine è la loro contiguità.

Tre documenti hanno questa forma — FINECO-EN23@IR p893→894, AMUNDI-EN24 p777→778, EURIZON-IT24
p54→55 — e UBS-EN23 ne ha una variante con **due** pagine di distanza, il titolo del comparto a p14
e il suo prospetto patrimoniale a p16. KAIROS-EN23 **non** è di questa famiglia: lì il nome sta
sulla stessa pagina, e a mancare è la mappa Unicode del carattere.

# La scelta, e che cosa costa

È la decisione dell'utente del 2026-09-21, fra due strade. Questa — la promessa con il numero di
pagina nella chiave — vive **tutta nel formato**: il motore non cambia, e la superficie pubblica
dei tipi d'uscita nemmeno. L'altra — far portare a `FundSfdrClassification` la pagina da cui viene,
e cercare la più vicina che precede — non si romperebbe se fra le due pagine se ne infilasse una
terza, ma aggiungerebbe una colonna a un tipo d'uscita, cioè codice pre-esistente del motore.

Il punto debole è dichiarato: **se fra le due pagine se ne infila una terza, la promessa non si
risolve e la riga sparisce in silenzio.** Nei documenti misurati le pagine sono adiacenti, e
`offset` esiste perché la distanza è una proprietà del formato, non una costante.

# Il numero di pagina è quello **stampato**

Il `pdf_extract` riceve il dizionario della pagina e non il suo indice, quindi il numero lo legge
dalla pagina: è `page_number`, che prende la selezione dove il formato stampa il piede. Non è un
difetto che sia quello stampato invece che quello del PDF — le due pipeline devono solo calcolare
la **stessa** chiave, e il piede è l'unica cosa che tutt'e due vedono.

# Come si mette insieme

```python
import carryover
import esg

carry = carryover.PageCarryover("esg-fund")

def pdf_extract_product(page):
    lines = pdflines_from_pagedict(page)
    number = carryover.page_number(lines, FOOT)
    return [PdfBlock(BLOCK, {"page": number}, name)]

pipelines = {
    # la pagina del modulo, che il nome ce l'ha
    "esg_fund": Pipeline(pdf_extract_product, text_filter_product, carry.deposit),
    # la pagina degli indicatori, che il nome non ce l'ha
    "esg_indicators": Pipeline(pdf_extract_section, esg.text_filter(read, carry.owner()),
                               esg.deserialize),
}
```

Nello `algorithms_schedule.csv` le due classi **non** hanno bisogno di stare in due step se si usa
`promise`: quella la risolve il motore alla fine del job, non il `text_filter`. Con `nearest`
invece servono, perché lì è il `text_filter` a cercare fra ciò che le pagine prima hanno lasciato, e
`filter_data` porta soltanto i risultati degli step **chiusi**.

# Due forme, e quando serve la seconda

| | come si risolve | quando |
|---|---|---|
| `promise(page)` | il **motore**, alla fine del job | la distanza fra le due pagine è una costante del formato — FINECO-EN23@IR e AMUNDI-EN24, dove il nome è sulla pagina immediatamente prima |
| `nearest(filter_data, page)` | il **`text_filter`**, leggendo `deposited` | la distanza **varia**: su UBS-EN23 fra il titolo di un comparto e il suo prospetto ci stanno una, due, tre o quattro pagine, perché in mezzo ci sono il commento di gestione e la tabella dei tre esercizi |
"""

from freeports import log
from freeports.core import Promise
from freeports.utils.pdf_extract import PdfLineSelection


def page_number(lines, selection=None):
    """Il numero stampato sulla pagina, o `None` se la pagina non ne porta.

    `selection` è la selezione del piede, che ogni formato scrive a modo suo. Per difetto si
    guardano le due strisce in fondo alla pagina — sinistra e destra — che è dove i formati della
    raccolta mettono il numero quando non lo centrano.

    Delle righe selezionate si prende **l'ultima in basso che sia un numero**: un piede porta spesso
    anche il nome del fondo o la data, e scartare ciò che numero non è costa meno che descrivere il
    piede di ogni formato.
    """
    if selection is None:
        selection = PdfLineSelection.area(0.0, 780.0, 150.0, 1e6) | PdfLineSelection.area(
            450.0, 780.0, 1e6, 1e6
        )
    candidates = sorted(selection.select(lines), key=lambda line: line.bbox[1])
    for line in reversed(candidates):
        text = line.text.strip()
        if text.isdigit():
            return int(text)
    log.debug("this page carries no printed page number: nothing can be carried over from it")
    return None


class PageCarryover:
    """Il valore che la pagina `n` lascia alla pagina `n + offset`.

    ```python
    carry = carryover.PageCarryover("esg-fund")
    ```

    Come `Carryover`, si costruisce **una volta per formato** e lo usano tutt'e due le pipeline:
    l'identificativo della promessa è scritto in un posto solo, e le due pagine non possono
    chiamarlo in due modi diversi.
    """

    def __init__(self, field, page_key="page", offset=1, separator="-page-"):
        if not field:
            raise ValueError("a carryover with no field would carry nothing")
        if offset < 1:
            raise ValueError("a page can only leave something to a page that comes after it")
        self.field = field
        self.page_key = page_key
        self.offset = offset
        self.separator = separator

    def __repr__(self):
        return "PageCarryover({!r}, page_key={!r}, offset={!r})".format(
            self.field, self.page_key, self.offset
        )

    def promise_id(self, page):
        """L'identificativo, scritto qui e in nessun altro posto.

        Vale **dentro un job**, come ogni promessa: due documenti della stessa corsa che portano la
        stessa pagina stampata sono due job diversi e non si vedono.
        """
        return "{}{}{}".format(self.field, self.separator, page)

    def deposit(self, block):
        """Il `deserialize` della prima pagina: la promessa che lascia a quella dopo.

        Si passa così com'è come deserializzatore — `deserialize=carry.deposit` — perché un
        dizionario è la forma in cui il motore riconosce delle promesse. Il valore è il contenuto
        del blocco, che è il nome del prodotto come il `text_filter` l'ha ripulito.
        """
        page = block.metadata.get(self.page_key)
        if page is None:
            log.error(
                "a block with no '{}' cannot leave anything to the next page: it is dropped"
                .format(self.page_key)
            )
            return {}
        return {self.promise_id(page): str(block.content).strip()}

    def promise(self, page):
        """La promessa che la pagina `page` deve chiedere: quella lasciata `offset` pagine prima.

        È la forma **per pagine adiacenti**: la chiave si calcola, e chi la risolve è il motore
        alla fine del job. Dove la distanza non è una costante del formato serve `nearest`.
        """
        return Promise(self.promise_id(page - self.offset))

    def deposited(self, filter_data):
        """`{pagina: valore}` di ciò che le pagine precedenti di questo job hanno lasciato.

        Le promesse depositate attraversano il confine verso Python **come dizionari**, quindi si
        riconoscono per tipo e per prefisso della chiave. Le chiavi di un altro `PageCarryover`
        della stessa corsa si lasciano stare.
        """
        prefix = self.field + self.separator
        out = {}
        for result in filter_data:
            if not isinstance(result, dict):
                continue
            for key, value in result.items():
                text = str(key)
                if not text.startswith(prefix):
                    continue
                tail = text[len(prefix):]
                if tail.isdigit():
                    out[int(tail)] = value
        return out

    def nearest(self, filter_data, page):
        """Il valore lasciato dalla pagina **più vicina prima** di `page`, o `None`.

        È la seconda forma, e serve dove la distanza fra le due pagine **non è una costante del
        formato**. Su UBS-EN23 il titolo di un comparto e il suo prospetto patrimoniale distano
        una, due, tre o quattro pagine — in mezzo ci stanno il commento di gestione e la tabella
        dei tre esercizi, che sono lunghi quanto capita — e `promise` lì non si può usare.

        La risoluzione avviene **qui**, nel `text_filter`, e non nel motore: appaiare due pagine
        per vicinanza è un'interpretazione, e `R23` le vuole tutte in questo segmento. Il prezzo è
        che la pipeline che deposita deve stare in uno **step precedente** dello
        `algorithms_schedule.csv`, o `filter_data` non porta ancora niente.
        """
        left = self.deposited(filter_data)
        before = [number for number in left if number < page]
        if not before:
            log.error(
                "no '{}' was left by any page before {}: this page cannot say which fund it is "
                "about, and its row is dropped".format(self.field, page)
            )
            return None
        return left[max(before)]

    def owner(self):
        """La funzione che dice *di chi è questa pagina*, nella forma che `esg.text_filter` vuole.

        Restituisce `None` quando la pagina non porta il suo numero: senza numero non c'è chiave, e
        una riga attaccata al comparto sbagliato è peggio di una riga che manca (`R12` vale al
        contrario solo quando il dato è giusto).
        """

        def of_page(pdf_blks, _filter_data):
            page = _page_of(pdf_blks, self.page_key)
            if page is None:
                log.error(
                    "this page carries no '{}': the indicators cannot be tied to a fund and the "
                    "rows are dropped".format(self.page_key)
                )
                return None
            return self.promise(page)

        return of_page


def _page_of(blocks, page_key):
    """Il numero di pagina che il `pdf_extract` ha messo nei metadati, dal primo blocco che ce l'ha."""
    for block in blocks:
        try:
            page = block.metadata[page_key]
        except (KeyError, TypeError, IndexError):
            continue
        if page is not None:
            return page
    return None
