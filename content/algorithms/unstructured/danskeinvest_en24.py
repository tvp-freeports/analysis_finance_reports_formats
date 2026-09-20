"""Modulo d'autore di DANSKEINVEST-EN24: solo il modulo periodico SFDR.

Trentanove moduli, di cui una parte porta il segno come immagine e una parte come glifo di uno
strato OCR (`hiddenhorzocr`): e' il solo formato della raccolta in cui il quarto riconoscitore ha
qualcosa da leggere, e per `R20` l'OCR non e' un motivo per saltare.
"""

import re

import sfdr

pipelines = {
    "sfdr_classification": sfdr.ENGLISH.pipeline(
        # Il nome sta sulla riga dell'etichetta, quindi i due tubi predefiniti bastano;
        # l'ombrello davanti invece va tolto, che gli investimenti non lo scrivono.
        product_prefix=(
            re.compile(r"Product name\s*:\s*"),
            re.compile(r"^Danske Invest SICAV\s+"),
        )
    ),
}
