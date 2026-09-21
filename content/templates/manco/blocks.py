"""Dalla riga letta al blocco standard della società di gestione.

Una funzione sola, e nessuna decisione oltre a quelle che `reading.py` ha già preso: qui si
costruisce il `text_filter` che il formato mette nella sua pipeline.
"""

from freeports.core import PageParseFail
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.interfaces.text_blks import StandardManagmentCompanyTextBlock
from freeports.output import ManagementCompany
from freeports.utils.text_filter import fund_filter_data

from .reading import first


def declared(filter_data):
    """Il nome della società di gestione che il job ha già letto, o `None`.

    Serve dove la `manco` e i gestori delegati stanno su **pagine diverse** — FIDEURAM-EN23 legge la
    prima a p67 e i secondi a p71 — perché il residuo di `R15` è suo e
    `inv_managers.assign` lo vuole per nome. Perché ci sia, la classe della `manco` deve venire
    **prima** nello `algorithms_schedule.csv`, e il passo che la contiene deve chiudersi
    (`Filter next iteration`).
    """
    for result in filter_data:
        if isinstance(result, ManagementCompany):
            return result.name
    return None


def text_filter(read, *, among=first):
    """Il `text_filter` della `manco`: sceglie la riga, ne estrae il nome, lo dichiara sui fondi.

    `R26`: la società di gestione è **uno a molti** su tutto il documento, quindi il blocco porta
    tutti i fondi che il job ha visto finora — ed è il motivo per cui nello
    `algorithms_schedule.csv` la classe `manco` viene sempre **dopo** gli investimenti.

    Una pagina classificata `manco` che poi il nome non ce l'ha è una pagina classificata male, e
    fallisce **quella pagina** senza fermare il documento: è lo stesso `PageParseFail` che il motore
    solleva da sempre quando un valore atteso una volta sola non c'è.
    """

    @fund_filter_data
    def filter_manco(pdf_blks, funds):
        texts = [
            blk.content
            for blk in pdf_blks
            if blk.type_block == ResultStandardExtraction.MANAGEMENT_COMPANY.name
            and isinstance(blk.content, str)
        ]
        chosen = among(texts)
        if chosen is None:
            raise PageParseFail("no management company line on a page classified for one")
        name = read(chosen)
        if name is None:
            raise PageParseFail(f"the management company line has an unexpected shape: {chosen!r}")
        return [StandardManagmentCompanyTextBlock.from_name(name, funds)]

    return filter_manco


__all__ = ["declared", "text_filter"]
