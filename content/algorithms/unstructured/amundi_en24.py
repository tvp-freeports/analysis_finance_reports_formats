"""Modulo d'autore di AMUNDI-EN24: solo il modulo periodico SFDR.

Centotre moduli, il blocco piu' numeroso dei documenti di prova, tutti con una `X` di testo in
Calibri-Bold. Due cose lo distinguono dagli altri nove formati:

- **due moduli su centotre scrivono le etichette in francese** (`X Oui` / `Non`) con la domanda in
  inglese, ed e' la ragione per cui `sfdr.ENGLISH` porta `Oui`/`Non` fra le etichette;
- il **nome del prodotto va a capo**, sempre: l'etichetta e' su una riga e il nome occupa le due
  righe sotto. `PdfExtractLabelledValueStandard` restituisce un blocco per riga e non le riunisce,
  quindi qui i tubi predefiniti non bastano.
"""

import re

import sfdr

pipelines = {
    "sfdr_classification": sfdr.ENGLISH.pipeline(
        product_joined=True,
        # Il modulo scrive l'ombrello davanti al comparto, gli investimenti no: `R24`.
        product_prefix=(
            re.compile(r"Product name\s*:\s*"),
            re.compile(r"^AMUNDI FUNDS\s+"),
        ),
    ),
}
