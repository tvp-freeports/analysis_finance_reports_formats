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
"""

import re

import renaming
import sfdr
from freeports.core import Pipeline
from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.standard_funcs.pdf_extract import PdfExtractSectionStandard
from freeports.utils.pdf_extract import PdfLineSelection

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

pipelines = {
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
