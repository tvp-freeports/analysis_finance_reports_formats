"""Dall'[`Assignment`][inv_managers.assignment.Assignment] ai blocchi che il `text_filter` restituisce.

Sono due funzioni e nessuna decisione: la decisione è tutta in `assignment.py`, e questo modulo la
traduce nei tre blocchi standard del motore. Sta a parte perché i sette rami dell'assegnazione si
provano su dati, senza costruire un blocco, ed è quello che li rende sette test brevi.
"""

from freeports.core import PdfBlock
from freeports.interfaces.text_blks import (
    StandardFundTextBlock,
    StandardInvestmentsMangerTextBlock,
    StandardManagmentCompanyTextBlock,
)


def text_blocks(assignment):
    """I blocchi dei gestori, più uno per ogni comparto che il job non aveva ancora visto.

    Un gestore letto da un blocco lo conserva, così la riga d'uscita sa da che pagina viene; uno
    costruito da un nome — la società di gestione passata come stringa, per esempio — no.

    I fondi nuovi vanno dichiarati qui, o le assegnazioni che li citano cadono nel nulla: il `Fund`
    non esiste ancora, e una riga di `investments_managers_to_funds.csv` senza il suo fondo non si
    può scrivere.
    """
    blocks = [
        StandardInvestmentsMangerTextBlock(manager.block, manager.funds)
        if manager.block is not None
        else StandardInvestmentsMangerTextBlock.from_name(manager.name, manager.funds)
        for manager in assignment.managers
    ]
    # In ordine di nome, e non quello in cui l'insieme li restituisce: gli identificativi
    # d'uscita si assegnano nell'ordine in cui le righe arrivano, e un insieme di stringhe in
    # Python non ha lo stesso ordine da una corsa all'altra. Senza questo, una fixture congelata
    # oggi fallirebbe domani per il solo seme della tabella di hash.
    blocks.extend(
        _fund_block(fund, assignment)
        for fund in sorted(assignment.new_funds, key=lambda fund: str(fund.name))
    )
    return blocks


def _fund_block(fund, assignment):
    """Il comparto nuovo, con la pagina da cui viene quando c'è un blocco che gliela dia.

    Un `funds.csv` con la colonna `Report page` vuota non esiste in nessuna delle trentuno corse di
    riferimento, e non deve cominciare a esistere qui: il comparto lo nomina la sezione dei gestori,
    quindi la sua provenienza è quella pagina. Il blocco si prende dal primo gestore che ne abbia
    uno — sono tutti della stessa pagina — e se non ce n'è nessuno si ricade sul nome nudo.
    """
    page_block = next((m.block for m in assignment.managers if m.block is not None), None)
    if page_block is None:
        return StandardFundTextBlock.from_matched_fund(fund)
    return StandardFundTextBlock(PdfBlock(page_block.type_block, {}, fund.name))


def management_company_block(assignment, manco):
    """Il blocco della società di gestione, con **tutti** i fondi del documento.

    `R26`: la società di gestione è uno a molti su tutto il documento — l'identificativo sta in
    `funds.csv` — mentre `inv_managers` è molti a molti in una tabella a parte. Che la stessa
    società compaia nei due ruoli non è un doppione: è il caso normale dei formati che nessun
    gestore delegato lo nominano.

    Si chiama solo dove la stessa pipeline legge anche la società di gestione; dove la `manco` ha
    una pipeline sua, questo blocco lo scrive quella.
    """
    if isinstance(manco, str):
        return StandardManagmentCompanyTextBlock.from_name(manco, assignment.funds)
    return StandardManagmentCompanyTextBlock(manco, assignment.funds)
