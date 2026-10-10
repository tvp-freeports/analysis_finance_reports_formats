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
la distanza fra le due pagine è una proprietà del formato e non una costante, e la dice la
cella `offset` del motore.

# Il numero di pagina è quello **stampato**

Il `pdf_extract` riceve il dizionario della pagina e non il suo indice, quindi il numero lo legge
dalla pagina: è `page_number`, che prende la selezione dove il formato stampa il piede. Non è un
difetto che sia quello stampato invece che quello del PDF — le due pipeline devono solo calcolare
la **stessa** chiave, e il piede è l'unica cosa che tutt'e due vedono.

# Come si mette insieme

Il `pdf_extract` resta d'autore, perche' il numero di pagina si legge dal piede e quello e'
geometria; il `text_filter` e il `deserialize` degli indicatori sono del motore (`esg` e
`esg_indicator`), e la chiave che li lega a questa pagina e' la cella
`fund: {kind: page_promise, field: ...}`:

```python
import carryover

carry = carryover.PageCarryover("esg-fund")

def pdf_extract_product(page):
    lines = pdflines_from_pagedict(page)
    number = carryover.page_number(lines, FOOT)
    return [PdfBlock(BLOCK, {"page": number}, name)]

pipelines = {
    # la pagina del modulo, che il nome ce l'ha: deposita
    "esg_fund": Pipeline(pdf_extract_product, text_filter_product, carry.deposit),
    # la pagina degli indicatori, che il nome non ce l'ha: il motore la risolve
    "esg_indicators": Pipeline(pdf_extract_section),
}
```

Nello `algorithms_schedule.csv` le due classi **non** hanno bisogno di stare in due step se la
chiave si calcola: quella la risolve il motore alla fine del job, non il `text_filter`. Con
`nearest` — che adesso e' la cella `fund: {kind: nearest_page}` di `labelled_assets` — servono,
perche' li' e' il `text_filter` a cercare fra cio' che le pagine prima hanno lasciato, e
`filter_data` porta soltanto i risultati degli step **chiusi**.

# Le due forme, che adesso sono due celle del motore

| | come si risolve | dove si scrive |
|---|---|---|
| la chiave si **calcola** | il **motore**, alla fine del job | `fund: {kind: page_promise, field: ...}` di `esg` |
| la chiave si **cerca** fra quelle lasciate prima | il **`text_filter`** | `fund: {kind: nearest_page, field: ...}` di `labelled_assets` |

La prima serve dove la distanza fra le due pagine e' una costante del formato — FINECO-EN23@IR e
AMUNDI-EN24, dove il nome e' sulla pagina immediatamente prima. La seconda dove **varia**: su
UBS-EN23 fra il titolo di un comparto e il suo prospetto patrimoniale ci stanno una, due, tre o
quattro pagine, perche' in mezzo ci sono il commento di gestione e la tabella dei tre esercizi.

Qui resta soltanto il **deposito**, piu' `page_number` che legge il numero dal piede: la
risoluzione, in tutt'e due le forme, e' del motore.

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
    """Il valore che una pagina lascia a una di qualche pagina dopo: qui il **deposito**.

    Chi lo ritrova e' il motore — `fund: {kind: page_promise}` di `esg`, o
    `fund: {kind: nearest_page}` di `labelled_assets` — e li' sta anche la distanza fra le due
    pagine. Questo oggetto scrive la chiave e nient'altro.

    ```python
    carry = carryover.PageCarryover("esg-fund")
    ```

    Come `Carryover`, si costruisce **una volta per formato** e lo usano tutt'e due le pipeline:
    l'identificativo della promessa è scritto in un posto solo, e le due pagine non possono
    chiamarlo in due modi diversi.
    """

    def __init__(self, field, page_key="page", separator="-page-"):
        if not field:
            raise ValueError("a carryover with no field would carry nothing")
        self.field = field
        self.page_key = page_key
        self.separator = separator

    def __repr__(self):
        return "PageCarryover({!r}, page_key={!r})".format(self.field, self.page_key)

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
