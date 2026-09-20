"""Le etichette di una pagina, riunite in un prospetto solo.

`A1` legge **un** valore accanto alla sua etichetta e ne fa un blocco **nudo**: nessun metadato,
solo il testo della riga. Una pagina che dichiara due totali ha quindi due `A1` nel `pdf_extract`,
distinti dal tipo di blocco, e qualcuno deve riunirli — perché il `text_filter` degli attivi legge
**un** blocco con `fund`, `currency` e gli importi nei metadati, non tre blocchi con un numero
ciascuno.

# Perché non è lavoro del `pdf_extract`

Riunire non è geometria. Il `pdf_extract` ha già detto **dove** stavano le righe, e l'ha detto nel
solo modo che gli compete: le ha marcate con un tipo. Dire che il blocco marcato `TOT_ASSETS` è
*il totale delle attività di questo prospetto* è attribuire un significato, che per `R23` è il
`text_filter`. Il costo di sbagliare segmento è concreto: un `pdf_extract` che riunisse non
saprebbe che cosa fare di una pagina con due prospetti affiancati, e il segmento dopo non potrebbe
più separarli.

# Una pagina, un prospetto

`R7` dice che il dato sono i prospetti **per comparto**, e la famiglia che questo modulo serve —
gli attivi italiani a cavallo di due pagine — pubblica **una relazione per fondo**: la pagina porta
un prospetto e nient'altro. Perciò `Record` produce **un** blocco, e due blocchi dello stesso tipo
sulla stessa pagina sono un avviso, non un secondo prospetto. Il giorno in cui una pagina ne porta
davvero due, il parametro che li separa si misura su quella pagina e si aggiunge qui.
"""

from freeports import log
from freeports.core import PdfBlock

RELEVANT_BLOCK = "RELEVANT_BLOCK"
"""Il tipo del blocco che esce, che è quello che i `text_filter` standard si aspettano."""


class Record:
    """I blocchi nudi lasciati da più `A1` sulla stessa pagina, riuniti in un blocco solo.

    Ogni argomento nominato è **una chiave di metadato e il tipo di blocco che la riempie**, scritti
    nell'ordine in cui si leggono:

    ```python
    record = Record(fund="FUND_NAME", currency="CURRENCY_STATEMENT", tot_assets="TOT_ASSETS")
    ```

    Il tipo di blocco è una stringa e non un `enum` perché è **il** parametro che un formato sceglie:
    è il nome che ha dato al suo `A1`, e due formati della stessa famiglia possono chiamarlo
    diversamente senza che nulla qui cambi.
    """

    def __init__(self, block_type=RELEVANT_BLOCK, **fields):
        if not fields:
            raise ValueError("a record with no field would gather nothing")
        self.block_type = block_type
        self.fields = dict(fields)

    def __repr__(self):
        written = ", ".join("{}={!r}".format(k, v) for k, v in self.fields.items())
        return "Record(block_type={!r}, {})".format(self.block_type, written)

    def __call__(self, blocks, also=None):
        """I blocchi della pagina, piu' `also` — cio' che la pagina non scrive e il job sa gia'.

        `also` serve alle pagine che **non nominano** il proprio comparto: EURIZON-IT24 scrive la
        situazione patrimoniale senza ripetere di quale fondo sia, perche' il documento ne porta
        uno solo, e il nome sta su un'altra pagina.

        E' un **ripiego**, non una sovrascrittura: cio' che la pagina dichiara vince sempre, e un
        campo che `also` porta non viene segnalato come mancante — non manca, e' arrivato da
        un'altra parte.
        """
        blocks = list(blocks)
        metadata = dict(also or {})
        for key, block_type in self.fields.items():
            taken = [blk for blk in blocks if blk.type_block == block_type]
            if not taken:
                if key not in metadata:
                    log.warn(
                        "no '{}' block on this page: the statement is read without its {}"
                        .format(block_type, key)
                    )
                continue
            if len(taken) > 1:
                log.warn(
                    "{} blocks of type '{}' where the page declares one statement: "
                    "the first in page order is read as its {}"
                    .format(len(taken), block_type, key)
                )
            metadata[key] = str(taken[0].content)
        if not metadata:
            log.warn("none of the expected blocks is on this page: no statement is read")
            return []
        return [PdfBlock(self.block_type, metadata, "")]
