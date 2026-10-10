"""`U7` per numero di pagina: il valore che una pagina lascia a una di qualche pagina dopo.

Di questo pacchetto **resta solo questo**. Le altre tre parti — riunire in un prospetto solo i
blocchi nudi che piu' `A1` lasciano su una pagina, portare un importo dalla prima pagina alla
seconda appaiandole col nome del comparto, e attribuire il prospetto all'unico comparto del
documento — sono passate al motore il 2026-10-05 e si scrivono adesso in
`content/algorithms/semistructured/args/`:

| cosa faceva | come si scrive adesso |
|---|---|
| `Record(fund="FUND_NAME", ...)` | la cella `gather` di `labelled_assets` (`text_filter`) |
| `Carryover("tot_assets").deposit` | l'algoritmo `carryover_deposit` (`deserialize`) |
| `Carryover("tot_assets").resume` | la cella `resume` di `labelled_assets` |
| `sole_fund(filter_data)` | la cella `fund: {kind: sole_if_absent}` |
| `DeserializerAssetsStandard(...)` | l'algoritmo `assets`, con `amount_cast` e `date_cast` |

`PageCarryover` e `page_number` restano qui perche' li chiama un `pdf_extract` **d'autore**: il
numero di pagina si legge dal piede, e il piede e' geometria che `A1` non copre ancora. Tre formati
li usano — UBS-EN23 (due veicoli), AMUNDI-EN24 e FINECO-EN23@IR — e li usano tutti dalla stessa
parte: il nome del prodotto in testa al modulo periodico europeo, e gli indicatori sulla pagina
dopo.

La forma `nearest` non serve piu' da Python: il `text_filter` degli attivi di UBS-EN23 la chiede
adesso al motore, con la cella `fund: {kind: nearest_page}`.
"""

from .page import PageCarryover, page_number

__all__ = [
    "PageCarryover",
    "page_number",
]
