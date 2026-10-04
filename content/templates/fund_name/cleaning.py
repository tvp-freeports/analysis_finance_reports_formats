"""Che cosa si toglie dal nome, e dove si toglie.

Due funzioni: `strip` lavora su una stringa e non sa niente di blocchi, `cleaned` la applica dove il
nome del comparto compare davvero.
"""

from freeports.interfaces.text_blks import ResultStandardFiltering

#: La chiave con cui il motore porta il nome del comparto nei metadati di un titolo.
FUND_KEY = "fund"


def strip(name, *, drop=(), substrings=()):
    """Il nome senza i pezzi che non ne fanno parte, e con gli spazi di contorno tolti.

    `drop` sono espressioni regolari già compilate — la coda fra parentesi, un richiamo di nota —
    e `substrings` sono pezzi letterali. Si applicano in quest'ordine, perché un letterale può
    restare in piedi dopo che un'espressione ha portato via il resto della riga.

    Lo spazio si toglie **alla fine e non durante**: una parentesi in mezzo al nome lascia due
    spazi dove ce n'era uno, e un nome con due spazi è un nome diverso da quello buono esattamente
    come lo era con la parentesi.
    """
    for expression in drop:
        name = expression.sub("", name)
    for substring in substrings:
        name = name.replace(substring, "")
    return " ".join(name.split())


def cleaned(text_filter, *, drop=(), substrings=()):
    """Il `text_filter` dato, con il nome del comparto ripulito in uscita.

    Si avvolge il tubo standard invece di sostituirlo: tutto quello che il motore legge dalla
    tabella continua a leggerlo, e il nome arriva pulito a chi lo userà come chiave.
    """

    def filter_and_clean(pdf_blks, filter_data):
        txt_blks = text_filter(pdf_blks, filter_data)
        for txt_blk in txt_blks:
            if txt_blk.type_block == ResultStandardFiltering.FUND.name:
                txt_blk.content = strip(txt_blk.content, drop=drop, substrings=substrings)
            if txt_blk.metadata.get(FUND_KEY):
                txt_blk.metadata[FUND_KEY] = strip(
                    txt_blk.metadata[FUND_KEY], drop=drop, substrings=substrings
                )
        return txt_blks

    return filter_and_clean
