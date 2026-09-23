"""Modulo d'autore di AMUNDI-EN24: solo il modulo periodico SFDR.

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

E da p8→9 arriva `IM-2`, che è la ricetta in cui **l'elenco non dice per quali comparti**: sotto
`INVESTMENT MANAGERS` e `SUB-INVESTMENT MANAGERS` stanno una ventina di società, ciascuna col suo
indirizzo e nessuna con una specificazione. È il ramo 4 di `A5` (`R21`): il residuo va **a tutti
quanti**, e il motore lo dichiara con un avviso, perché non è un dato letto ma una deduzione
presa per eccesso. I due gruppi si leggono insieme, che `R22` vuole i sub-gestori appiattiti.
"""

import re

import inv_managers
import renaming
import sfdr
from freeports.core import PdfBlock, Pipeline
from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.standard_funcs.deserialize import (
    DeserializerFundStandard,
    DeserializerInvestmentsManagerStandard,
)
from freeports.standard_funcs.pdf_extract import PdfExtractSectionStandard
from freeports.utils.pdf_extract import PdfLineSelection, pdflines_from_pagedict
from freeports.utils.text_filter import investment_fund_filter_data

# La sezione è tutta la nota: si apre sull'intestazione in grassetto e si chiude sulla prossima
# intestazione dello stesso carattere, che è il comportamento per difetto di `family`.
pdf_extract_renaming = PdfExtractSectionStandard(
    PdfLineSelection(font="arial-boldmt", font_size=(9.0, 10.0), text="INTRODUCTION"),
    OnePdfBlockType.RELEVANT_BLOCK.name,
    "renaming",
    body=PdfLineSelection(font="arialmt", font_size=(6.5, 7.5)),
)

# `on 15 March 2024` sta nell'intestazione, e vale per tutte le righe che seguono. Le due sezioni
# sorelle non portano il connettore ` into `, quindi chiudono lo scopo invece di aprirne uno.
read_renaming = renaming.Listed(
    renamed=(r"have been renamed",),
    merged=(r"have been merged", r"have been absorbed"),
    # Lo stesso prefisso che il modulo SFDR si toglie, e per la stessa ragione: gli investimenti
    # scrivono `European Equity ESG Improvers`, la nota `Amundi Funds European Equity ESG
    # Improvers`, e `R24` vuole che finiscano sullo stesso comparto.
    strip=(r"^Amundi Funds\s+",),
)

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


read_inv_managers = inv_managers.Named()
"""Il blocco **è** la dichiarazione: un nome, e nessun comparto detto."""


@investment_fund_filter_data
def text_filter_inv_managers(pdf_blks, funds):
    """Il residuo a tutti quanti, con l'avviso che `R21` impone.

    Le due pagine si trattano allo stesso modo e **non** si passano il conto: qui il residuo non
    è ciò che resta da dividere, è l'intero insieme dei comparti, e darne una metà a ciascuna
    pagina scriverebbe una divisione che il documento non fa.
    """
    return inv_managers.text_blocks(
        inv_managers.assign(read_inv_managers(pdf_blks), funds)
    )


_inv_managers = Pipeline(
    pdf_extract=pdf_extract_inv_managers_begin,
    text_filter=text_filter_inv_managers,
    deserialize=(DeserializerInvestmentsManagerStandard(), DeserializerFundStandard()),
)

pipelines = {
    "inv_managers_begin": _inv_managers,
    "inv_managers_end": Pipeline(
        pdf_extract=pdf_extract_inv_managers_end,
        text_filter=text_filter_inv_managers,
        deserialize=(DeserializerInvestmentsManagerStandard(), DeserializerFundStandard()),
    ),
    "sfdr_classification": sfdr.ENGLISH.pipeline(
        product_joined=True,
        # Il modulo scrive l'ombrello davanti al comparto, gli investimenti no: `R24`.
        product_prefix=(
            re.compile(r"Product name\s*:\s*"),
            re.compile(r"^AMUNDI FUNDS\s+"),
        ),
    ),
    "renaming": Pipeline(
        pdf_extract=pdf_extract_renaming,
        text_filter=renaming.text_filter(read_renaming),
        deserialize=renaming.deserialize(),
    ),
}
