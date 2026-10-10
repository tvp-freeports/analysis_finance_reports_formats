"""Modulo d'autore di DANSKEINVEST-EN24: il modulo SFDR, le fusioni, e il prospetto di p5-6.

Trentanove moduli, di cui una parte porta il segno come immagine e una parte come glifo di uno
strato OCR (`hiddenhorzocr`): e' il solo formato della raccolta in cui il quarto riconoscitore ha
qualcosa da leggere, e per `R20` l'OCR non e' un motivo per saltare.

Da p351 arriva anche `FC-3`, la ricetta in cui **ogni evento e' una frase** con dentro il verbo e
la data — `… was renamed European Corporate Green Bond effective 22 November 2024.` — e una delle
due frasi **va a capo**. La sezione e' `NOTE 12 - EVENTS DURING THE YEAR` e si **ferma** alla nota
che segue, `NOTE 13 - POST BALANCE SHEET EVENTS`: il bilancio chiude il 31 dicembre 2024 e la
fusione che quella nota riporta e' del 21 febbraio 2025, quindi appartiene all'esercizio dopo ed e'
il bilancio dopo a doverla scrivere.

# La societa' di gestione e i gestori, su due pagine e quattro livelli (`C05` e `C17`)

Il prospetto `Management and Administration` occupa p5 e p6, **a due colonne**, e le intestazioni
di sezione sono le sole righe in `calibri-bold` da 9 mentre tutto il resto — nomi di societa' e
indirizzi — e' in `calibri` da 9. Non c'e' nessuna tipografia che distingua un nome dal suo
indirizzo: quello che li distingue e' lo **stacco verticale**, 21,6 punti fra due entrate contro
10,8 fra due righe della stessa entrata. E' geometria, quindi sta nel `pdf_extract`, che numera le
entrate e lascia al `text_filter` il solo lavoro di dire quale riga di un'entrata sia il nome.

La societa' di gestione e' dichiarata **due volte**, con due periodi:

```
MANAGEMENT COMPANY
Danske Invest Management A/S
(until 11 June 2024)
...
Danske Invest Management A/S
(from 12 June 2024)
```

Le due entrate nominano **la stessa societa'**: a cambiare e' solo l'indirizzo, da Kgs. Lyngby a
Copenhagen. Quindi qui la regola `U6` non ha nulla da scegliere e si prende la prima riga sotto
l'etichetta, che e' il nome.

I gestori invece sono quattro sezioni — `INVESTMENT MANAGER`, `SUB-INVESTMENT MANAGERS`,
`SUB SUB-INVESTMENT MANAGERS`, `SUB-SUB-SUB-INVESTMENT MANAGERS` — e `R22` le vuole **appiattite**:
la gerarchia delle deleghe non e' un dato d'uscita, il legame gestore-comparto lo e'. Nessuna delle
entrate dice per quali comparti, quindi siamo nel ramo di `R21`: il residuo va a tutti quanti, e il
motore lo dichiara con un avviso perche' e' una deduzione presa per eccesso.

Due cose dell'elenco non si leggono da sole:

- `Fidelity Institutional Asset Management LLC` porta `(until 26 April 2024)` e
  `Goldman Sachs Asset Management International` porta `(from 26 April 2024)`: e' un avvicendamento
  dentro l'esercizio, e si estrae **solo chi e' in carica alla chiusura** (`Declared(retired=True)`
  per l'altro, che non diventa una riga ma restituisce al residuo i comparti che rivendicava);
- `Sumitomo Mitsui DS Asset Management Company, / Limited` ha il **nome su due righe**. A dire che
  la seconda riga continua la prima e' la virgola in fondo alla prima: senza quella regola il nome
  esce mutilato, che e' peggio di un nome che manca. La virgola si tiene, perche' la ragione
  sociale e' quella.
"""


from freeports.core import PdfBlock, Pipeline
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict

_HEADING = PdfLineSelection(font="calibri-bold", font_size=(8.5, 9.5))

# La sezione degli eventi (`FC-3`) e' configurazione: `section` nel `pdf_extract`, e la cella
# `family` e' quella che la chiude sulla nota dopo — `NOTE 13 - POST BALANCE SHEET EVENTS` — perche'
# cio' che sta sotto non e' di quest'esercizio (`C36`).

# Le due frasi si cercano su tutto il testo della sezione, riunito: una delle due va a capo, e
# `finditer` trova anche la seconda occorrenza quando un anno ne porta piu' d'una. Il nome vecchio
# e quello nuovo non possono contenere un punto, o il nome si prenderebbe le frasi precedenti: il
# punto e' cio' che separa un evento dall'altro in un testo che e' stato riunito apposta.
# Il `text_filter` e il `deserialize` sono del motore: `renaming` legge i cambi nella forma
# che questa sezione usa, tiene quelli che riguardano un comparto del job (`R24`) e converte
# la data. Gli schemi stanno in `content/algorithms/semistructured/args/text_filter.yaml`.

_BODY = PdfLineSelection(font="calibri", font_size=(8.5, 9.5))

_COLUMN_EDGE = 300.0
"""L'ascissa che divide le due colonne del prospetto: a sinistra 63,6, a destra 308,4.

Serve perche' una sezione si chiude sulla **prossima intestazione della sua colonna**, e non su
quella che le capita accanto: `INVESTMENT MANAGER` sta in cima alla colonna di destra di p5 mentre
`BOARD OF DIRECTORS OF THE MANAGEMENT COMPANY` sta sotto, a sinistra.
"""

_ENTRY_GAP = 15.0
"""Lo stacco oltre il quale due righe sono due entrate diverse.

Misurato su p5 e p6: 10,8 punti fra due righe della stessa entrata (nome, indirizzo, citta'), 19,2
a 21,6 fra l'ultima riga di un'entrata e il nome della prossima. Quindici sta in mezzo con margine
da tutt'e due le parti.
"""

_MANAGERS = "INVESTMENT MANAGER"
"""Il testo che apre una sezione di gestori, e che le prende tutte e quattro.

`INVESTMENT MANAGER`, `SUB-INVESTMENT MANAGERS`, `SUB SUB-INVESTMENT MANAGERS` e
`SUB-SUB-SUB-INVESTMENT MANAGERS` lo contengono tutte; nessun'altra intestazione delle due pagine
lo contiene — ne' `BOARD OF DIRECTORS OF THE MANAGEMENT COMPANY`, ne' `DEPOSITARY BANK`, ne'
`DOMICILIARY AGENT`.
"""


def _in_column(lines, left):
    """Le righe di una delle due colonne, dall'alto in basso."""
    chosen = [
        line for line in lines
        if (line.bbox[0] < _COLUMN_EDGE) == left and line.text.strip()
    ]
    return sorted(chosen, key=lambda line: line.bbox[1])


def pdf_extract_inv_managers(page):
    """Le entrate delle quattro sezioni dei gestori, numerate per entrata.

    Il numero di gruppo porta la colonna, cosi' due entrate che cominciano alla stessa ordinata
    nelle due colonne non si confondono: senza, `Abrdn Asia Limited` a destra e un indirizzo a
    sinistra finirebbero nella stessa entrata.
    """
    lines = pdflines_from_pagedict(page)
    # Le righe si riconoscono per riquadro e non per identita': `select` restituisce oggetti
    # nuovi, quindi `is` e `id()` non dicono niente, mentre un riquadro e' di una riga sola.
    headings = {tuple(line.bbox) for line in _HEADING.select(lines)}
    body = {tuple(line.bbox) for line in _BODY.select(lines)}
    blocks = []
    for left in (True, False):
        side = "L" if left else "R"
        collecting = False
        group = None
        previous = None
        for line in _in_column(lines, left):
            if tuple(line.bbox) in headings:
                collecting = _MANAGERS in line.text
                group = None
                previous = None
                continue
            if not collecting or tuple(line.bbox) not in body:
                continue
            if previous is None or line.bbox[1] - previous > _ENTRY_GAP:
                group = "{}{}".format(side, len(blocks))
            previous = line.bbox[1]
            blocks.append(
                PdfBlock(
                    ResultStandardExtraction.INVESTMENTS_MANAGER.name,
                    {"group": group},
                    line.text,
                )
            )
    return blocks


# Il `text_filter` sta nel livello `semistructured`. Il nome e' la prima riga dell'entrata piu'
# quelle che la virgola finale tiene attaccate — `Sumitomo Mitsui DS Asset Management Company, /
# Limited` e' una ragione sociale su due righe, e la virgola **resta**, che un nome d'uscita e'
# quello scritto — e le altre righe sono l'indirizzo e la qualificazione temporale. `retired` si
# prova su **ogni** riga dell'entrata, perche' li' la qualificazione sta sotto il nome.
def pdf_extract_manco(page):
    """La prima riga sotto `MANAGEMENT COMPANY`, e **niente** dove quell'intestazione non c'e'.

    Non e' `PdfExtractLabelledValueStandard` per una ragione sola: le due pagine del prospetto sono
    **una classe sola**, e quel tubo fa fallire la pagina in cui non trova l'etichetta — cioe' la
    p6, che l'etichetta non la porta. Un tubo d'autore puo' restituire la lista vuota, e il
    `text_filter` del template scrive il blocco della societa' di gestione **solo se c'e'**.

    Le due pagine devono stare nella stessa classe perche' una pagina che corrisponde a due classi
    non viene assegnata a nessuna delle due: tenere `manco` e `inv_managers` separate costava la
    p5 intera, societa' di gestione e quattro gestori compresi.
    """
    lines = pdflines_from_pagedict(page)
    headings = {tuple(line.bbox) for line in _HEADING.select(lines)}
    body = {tuple(line.bbox) for line in _BODY.select(lines)}
    for left in (True, False):
        found = False
        for line in _in_column(lines, left):
            if tuple(line.bbox) in headings:
                found = line.text.strip().startswith("MANAGEMENT COMPANY")
                continue
            if found and tuple(line.bbox) in body:
                return [
                    PdfBlock(
                        ResultStandardExtraction.MANAGEMENT_COMPANY.name,
                        {},
                        line.text.strip(),
                    )
                ]
    return []


pipelines = {
    # `C05` e `C17`, in una classe sola perche' le due pagine sono un prospetto solo: la societa'
    # di gestione (p5) e le quattro sezioni dei gestori (p5 e p6), appiattite come vuole `R22`.
    "inv_managers": Pipeline((pdf_extract_manco, pdf_extract_inv_managers)),
}
