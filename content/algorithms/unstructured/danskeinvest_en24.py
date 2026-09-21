"""Modulo d'autore di DANSKEINVEST-EN24: solo il modulo periodico SFDR.

Trentanove moduli, di cui una parte porta il segno come immagine e una parte come glifo di uno
strato OCR (`hiddenhorzocr`): e' il solo formato della raccolta in cui il quarto riconoscitore ha
qualcosa da leggere, e per `R20` l'OCR non e' un motivo per saltare.

Da p351 arriva anche `FC-3`, la ricetta in cui **ogni evento e' una frase** con dentro il verbo e
la data — `… was renamed European Corporate Green Bond effective 22 November 2024.` — e una delle
due frasi **va a capo**. La sezione e' `NOTE 12 - EVENTS DURING THE YEAR` e si **ferma** alla nota
che segue, `NOTE 13 - POST BALANCE SHEET EVENTS`: il bilancio chiude il 31 dicembre 2024 e la
fusione che quella nota riporta e' del 21 febbraio 2025, quindi appartiene all'esercizio dopo ed e'
il bilancio dopo a doverla scrivere.
"""

import re

import renaming
import sfdr
from freeports.core import Pipeline
from freeports.interfaces.pdf_blks import OnePdfBlockType
from freeports.standard_funcs.pdf_extract import PdfExtractSectionStandard
from freeports.utils.pdf_extract import PdfLineSelection

_HEADING = PdfLineSelection(font="calibri-bold", font_size=(8.5, 9.5))

# La sezione si chiude sulla prossima intestazione in grassetto, e quella degli eventi successivi
# alla chiusura e' la prima che incontra: cio' che sta sotto non e' di quest'esercizio.
pdf_extract_merges = PdfExtractSectionStandard(
    _HEADING & PdfLineSelection.text("EVENTS DURING THE YEAR"),
    OnePdfBlockType.RELEVANT_BLOCK.name,
    "merges",
    family=_HEADING,
    body=PdfLineSelection(font="calibri", font_size=(8.5, 9.5)),
)

# Le due frasi si cercano su tutto il testo della sezione, riunito: una delle due va a capo, e
# `finditer` trova anche la seconda occorrenza quando un anno ne porta piu' d'una. Il nome vecchio
# e quello nuovo non possono contenere un punto, o il nome si prenderebbe le frasi precedenti: il
# punto e' cio' che separa un evento dall'altro in un testo che e' stato riunito apposta.
read_merges = renaming.Sentence(
    renamed=(
        r"(?P<old>Danske Invest SICAV\s*[-–]\s*[^.]+?) was renamed (?P<current>[^.]+?)"
        r" effective (?P<when>\d{1,2} \w+ \d{4})",
    ),
    merged=(
        r"(?P<old>Danske Invest SICAV\s*[-–]\s*[^.]+?) merged into (?P<current>[^.]+?)"
        r" on (?P<when>\d{1,2} \w+ \d{4})",
    ),
    # L'ombrello lo scrive la nota e non lo scrivono gli investimenti, come nel modulo SFDR.
    strip=(r"^Danske Invest SICAV\s*[-–]\s*",),
)

pipelines = {
    "sfdr_classification": sfdr.ENGLISH.pipeline(
        # Il nome sta sulla riga dell'etichetta, quindi i due tubi predefiniti bastano;
        # l'ombrello davanti invece va tolto, che gli investimenti non lo scrivono.
        product_prefix=(
            re.compile(r"Product name\s*:\s*"),
            re.compile(r"^Danske Invest SICAV\s+"),
        )
    ),
    "merges": Pipeline(
        pdf_extract=pdf_extract_merges,
        text_filter=renaming.text_filter(read_merges),
        deserialize=renaming.deserialize(),
    ),
}
