"""Dai cambi letti ai blocchi di testo, e da quelli alle due righe d'uscita.

Il `text_filter` fa una cosa sola oltre a chiamare il lettore: **tiene i cambi che riguardano un
comparto del job**. È `R24` applicato qui — il nome che finisce nell'uscita dev'essere quello che
gli investimenti scrivono — e insieme il filtro contro il rumore, perché una sezione di prosa
nomina anche comparti di altri documenti e società che non c'entrano.

Il `deserialize` converte la data e basta, che è tutto ciò che `R23` gli lascia fare.
"""

from freeports.core import TextBlock
from freeports.interfaces.text_blks import OneTextBlockType
from freeports.output import FundMerge, FundRename
from freeports.utils.deserialize import to_date_with_en_month
from freeports.utils.text_filter import MatchFund, fund_filter_data

BLOCK = OneTextBlockType.RELEVANT_BLOCK.name
"""Il tipo di blocco che questo template scrive, e che il suo `deserialize` si aspetta."""


def text_filter(read, *, of_interest="current"):
    """Il `text_filter` di una pipeline di ridenominazioni: legge, filtra, e scrive i blocchi.

    `of_interest` dice **quale dei due nomi** deve essere un comparto del job perché il cambio si
    tenga: `"current"` dove il documento è quello dell'anno dopo il cambio — il caso comune, ed è
    col nome nuovo che gli investimenti parlano — `"old"` dove a essere ancora in elenco è il nome
    vecchio, `"any"` dove basta uno dei due.
    """

    @fund_filter_data
    def filter_blocks(pdf_blks, funds):
        return [
            _block(change)
            for change in read(pdf_blks)
            if _is_of_interest(change, funds, of_interest)
        ]

    return filter_blocks


def _is_of_interest(change, funds, which):
    """Se il cambio riguarda un comparto che il job ha visto."""
    old = MatchFund(change.old_name) in funds
    current = MatchFund(change.current_name) in funds
    if which == "old":
        return old
    if which == "any":
        return old or current
    return current


def _block(change):
    """Il blocco di testo che porta il cambio fino al `deserialize`."""
    return TextBlock(
        BLOCK,
        {
            "old_name": change.old_name,
            "current_name": change.current_name,
            "when": change.when,
            "merge": change.merge,
        },
        change.block,
    )


def deserialize(to_date=to_date_with_en_month):
    """Il `deserialize` della pipeline: una riga per blocco, e la data è il solo casting.

    `to_date` è il convertitore della lingua in cui il documento scrive i mesi — l'inglese per
    difetto, `to_date_with_it_month` per i bilanci italiani.
    """

    def deserialize_block(txt_blk):
        metadata = txt_blk.metadata
        row = FundMerge if metadata["merge"] else FundRename
        return row(
            old_name=metadata["old_name"],
            current_name=metadata["current_name"],
            date=to_date(metadata["when"]),
        )

    return deserialize_block
