"""Dall'[`Assignment`][inv_managers.assignment.Assignment] ai blocchi che il `text_filter` restituisce.

Sono due funzioni e nessuna decisione: la decisione è tutta in `assignment.py`, e questo modulo la
traduce nei tre blocchi standard del motore. Sta a parte perché i sette rami dell'assegnazione si
provano su dati, senza costruire un blocco, ed è quello che li rende sette test brevi.
"""

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
    blocks.extend(
        StandardFundTextBlock.from_matched_fund(fund) for fund in assignment.new_funds
    )
    return blocks


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
