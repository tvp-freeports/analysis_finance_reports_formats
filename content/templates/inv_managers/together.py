"""Il `text_filter` della pagina che dichiara la societa' di gestione **e** i gestori, insieme.

E' la ricetta `IM-1`, la piu' semplice delle otto: una pagina di prospetto mette due etichette, una
per la `manco` e una per il gestore, e sotto ciascuna un nome. Nessun comparto e' nominato, quindi
`R15` da' il residuo al gestore e alla societa' di gestione resta il solo ruolo di `manco` — ed e'
per questo che `assign` riceve la `manco` ma non la mette fra i gestori.

Le due letture stanno sulla **stessa pagina**, quindi non c'e' nessuna promessa da depositare: il
`text_filter` riceve i blocchi di tutt'e due i `pdf_extract` e li unisce li' (e' la regola per cui
due dati sulla stessa pagina non usano il meccanismo delle promesse).

Sta qui, e non copiato in ogni modulo, perche' i formati che scrivono la pagina cosi' sono piu' di
uno: ASTERIA-EN23 e ASTERIA-EN24 la scrivono **identica** a due anni di distanza, con le stesse
etichette e lo stesso corpo. A cambiare da un formato all'altro sono le due `PdfLineSelection` delle
etichette, che stanno nel `pdf_extract` e non qui.

```python
pipelines = {
    "inv_managers": Pipeline(
        (pdf_extract_manco, pdf_extract_inv_managers),
        inv_managers.declared_together(),
        (DeserializerInvestmentsManagerStandard(), DeserializerManagmentCompanyStandard()),
    ),
}
```
"""

from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.utils.text_filter import investment_fund_filter_data

from .assignment import assign
from .blocks import management_company_block, text_blocks
from .reading import Named


def first(blocks):
    """Il caso normale: la pagina dichiara **una** societa' di gestione, e quella si prende."""
    return blocks[0] if blocks else None


def declared_together(read=None, *, among=first):
    """Il gestore unico, i comparti che gli toccano, e la societa' di gestione con tutti.

    - `read` — come la pagina scrive le dichiarazioni dei gestori; per difetto
      [`Named`][inv_managers.reading.Named], cioe' «il blocco **e'** la dichiarazione»;
    - `among` — quale riga, fra quelle che il `pdf_extract` ha trovato sotto l'etichetta della
      societa' di gestione, e' il nome. Per difetto la prima; dove il bilancio ne nomina due col
      loro periodo si passa un selettore che sappia leggere la qualificazione temporale.

    La societa' di gestione puo' mancare senza che la pagina sia sbagliata — e' il gestore che
    questa classe di pagina promette — quindi il blocco della `manco` si aggiunge solo se c'e'.
    """
    read = Named() if read is None else read

    @investment_fund_filter_data
    def text_filter(pdf_blks, funds):
        manco_block = among(
            [
                blk for blk in pdf_blks
                if blk.type_block == ResultStandardExtraction.MANAGEMENT_COMPANY.name
            ]
        )
        assignment = assign(
            read(
                blk for blk in pdf_blks
                if blk.type_block == ResultStandardExtraction.INVESTMENTS_MANAGER.name
            ),
            funds,
            manco=manco_block,
        )
        blocks = list(text_blocks(assignment))
        if manco_block is not None:
            blocks.append(management_company_block(assignment, manco_block))
        return blocks

    return text_filter
