"""`EI-3` — gli indicatori di sostenibilità, e il comparto che sta sulla pagina prima.

La sezione è la risposta alla domanda *«How did the sustainability indicators perform?»*, e ogni
voce comincia col suo numero:

```
1.   93.07% of the Fund was invested in securities of issuers with favourable ESG
     characteristics in accordance with Fidelity's Sustainable Investing Framework.
```

Due cose sono decise qui e vale la pena dirle.

**La sezione si ferma alla domanda dopo.** Sotto, `…and compared to previous periods?` ripete gli
stessi sei indicatori con i valori dell'**esercizio precedente**: leggerli vorrebbe dire scrivere
due valori per lo stesso indicatore dello stesso comparto, senza niente che li distingua. Chiudere
sulla prossima intestazione in corsivo grassetto è ciò che li lascia fuori.

**Il comparto lo dice la pagina prima.** p893 porta `Product name: Fidelity EURO Bond FAM Fund`,
p894 gli indicatori e il nome del comparto non lo nomina. Le due pagine si legano col **numero di
pagina stampato in fondo**, che è la scelta dell'utente del 2026-09-21: la pipeline del nome
deposita una promessa `esg-fund-page-893`, quella degli indicatori chiede `esg-fund-page-894 - 1`.
Vive tutta nel formato e non tocca il motore; si rompe se fra le due pagine se ne infila una terza.

**La classe di pagina è ristretta al quarto alto del foglio**, e questo è il limite noto. Su una
parte degli allegati la domanda cade **in fondo** alla pagina che apre l'allegato, e l'elenco
comincia su quella dopo: lì le due classi si contenderebbero la stessa pagina, e due classi che si
contendono una pagina non ne scelgono una — il motore la lascia *non classificata*, e con lei si
perde anche l'articolo SFDR che quella pagina porta (`page classified both as
"sfdr_classification" and as "esg_indicators" - page left unclassified`).

La restrizione `(1:400)` tiene le due classi disgiunte: si legge dove la domanda apre la pagina, e
dove cade in fondo non si legge niente — nessuna riga sbagliata, e nessuna riga giusta persa
altrove. L'ordinata minima **non può essere `0`**: il motore rifiuta la tabella con `y_min must be
positive, found 0`.

Misurato: **diciannove indicatori su quattro comparti**, zero righe di errore nel registro della
corsa, e i quarantasei articoli SFDR del documento tutti al loro posto.
"""

import carryover
import esg
from freeports.core import PdfBlock
from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.interfaces.text_blks import OneTextBlockType
from freeports.core import TextBlock
from freeports.standard_funcs.pdf_extract import PdfExtractSectionStandard
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict
from freeports.utils.text_filter import MatchFund, investment_fund_filter_data

carry = carryover.PageCarryover("esg-fund")
"""Il veicolo, costruito una volta: le due pipeline non possono più chiamare la chiave in due modi."""

FOOT = PdfLineSelection.area(0.0, 795.0, 1e6, 1e6)
"""Il piede, dove il numero di pagina sta **centrato**: le due strisce laterali per difetto non lo
prenderebbero."""

_HEADING = PdfLineSelection(font="calibri-bolditalic", font_size=(10.5, 11.5))

# La colonna di glossario del modello europeo sta a `x≈2` e in ordine di sola ordinata si intreccia
# col corpo: si taglia per ascissa qui, che è dove `R23` mette la geometria.
_BODY = PdfLineSelection(font="calibri", font_size=(8.5, 9.5)) & PdfLineSelection.area(
    150.0, 0.0, 1e6, 1e6
)

_section = PdfExtractSectionStandard(
    _HEADING & PdfLineSelection.text("How did the sustainability indicators perform"),
    OnePdfBlockType.RELEVANT_BLOCK.name,
    "esg_indicators",
    family=_HEADING,
    body=_BODY,
)


def pdf_extract_indicators(page):
    """La sezione, con il numero di pagina nei metadati di ogni blocco."""
    lines = pdflines_from_pagedict(page)
    number = carryover.page_number(lines, FOOT)
    return [
        PdfBlock(block.type_block, dict(block.metadata, page=number), block.content)
        for block in _section(page)
    ]


def pdf_extract_fund(page):
    """Il nome del prodotto della pagina del modulo, con il numero di pagina.

    Il tubo del nome è quello che il modulo SFDR usa già: su questo formato il nome **va a capo** e
    `A1` non riunisce le righe, quindi il formato se lo scrive. Qui serve la stessa lettura con in
    più il numero di pagina, che è ciò che la pagina dopo userà per ritrovarlo.
    """
    from . import product_set

    lines = pdflines_from_pagedict(page)
    number = carryover.page_number(lines, FOOT)
    selected = sorted(product_set.select(lines), key=lambda line: line.bbox[1])
    name = "".join(line.text for line in selected).strip()
    if not name or number is None:
        return []
    return [PdfBlock(OnePdfBlockType.RELEVANT_BLOCK.name, {"page": number}, name)]


@investment_fund_filter_data
def text_filter_fund(pdf_blks, investment_funds):
    """Il nome ripulito, e solo se è un comparto d'interesse.

    Il filtro sta qui e non sulla pagina degli indicatori: di là il comparto è una promessa, e una
    promessa non si confronta con niente. È l'unico punto in cui si può dire che quel modulo parla
    di un comparto che al job interessa.
    """
    if not pdf_blks:
        return []
    block = next(iter(pdf_blks))
    name = str(block.content).split(":", 1)[-1].strip()
    if not name or MatchFund(name=name) not in investment_funds:
        return []
    return [TextBlock.from_content(OneTextBlockType.RELEVANT_BLOCK.name, block.metadata, name)]


read = esg.LeadingNumber()
"""Il valore in testa alla frase, il nome nel resto (`R11`: senza numero non c'è indicatore).

La seconda voce dei sei — *«in respect of its direct investments in corporate issuers, 0% of the
Fund invested in…»* — comincia con la precisazione e non col numero, quindi cade. È la regola
applicata, non un difetto da correggere qui: correggerla vorrebbe dire cercare il primo numero
**dentro** la frase, e allora `in accordance with Fidelity's Sustainable Investing Framework`
diventerebbe il nome di un indicatore su ogni voce che porta una cifra per caso.
"""

text_filter_indicators = esg.text_filter(read, carry.owner())
