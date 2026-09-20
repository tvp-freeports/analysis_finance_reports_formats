"""`U7` — leggere un prospetto scritto a etichette, anche quando sta su due pagine.

Sei formati italiani — ARCA-IT24, ANIMA_SGR-IT24, EURIZON-IT24, AMUNDI-IT24, FIDEURAM-IT24,
MEDIOLANUM-IT24.B — scrivono la situazione patrimoniale su **due** pagine: l'attivo su una, il
passivo e il netto sulla seguente. `FundAssets` porta i tre importi insieme e li controlla insieme
(`R32`), quindi nessuna delle due pagine da sola costruisce la riga.

Questo pacchetto è il pezzo che manca, e sono due cose indipendenti:

- `Record` riunisce i blocchi nudi che più `A1` lasciano su **una** pagina in un blocco solo, con
  i metadati che i `text_filter` standard si aspettano. Serve anche a chi la seconda pagina non ce
  l'ha;
- `Carryover` porta un valore **dalla prima pagina alla seconda**, depositandolo come promessa e
  ritrovandolo in `data.previous()`;
- `sole_fund` risponde alla domanda *di quale comparto parla questa pagina* quando la pagina non lo
  dice e il documento ne porta uno solo.

# Perché `A1` e non `A4`

Il §5.3 del piano prevedeva `A4` su tutt'e due le pagine. Misurandole non regge, e la ragione è
strutturale: `A4` costruisce una riga da **tre** colonne numeriche e scarta la riga a cui ne manca
una. Una pagina che dichiara il solo `TOTALE ATTIVITA'` non è una tabella di attivi a cui manca
qualcosa — è **un'etichetta con il suo valore**, che è esattamente la forma che `A1` legge. Le due
pagine hanno quindi due, tre, quattro `A1` ciascuna, e `Record` le riunisce.

# Come si mette insieme

```python
import carryover

carry = carryover.Carryover("tot_assets")

record_attivo = carryover.Record(fund="FUND_NAME", currency="CURRENCY_STATEMENT",
                                 tot_assets="TOT_ASSETS")

def text_filter_attivo(pdf_blks, filter_data):
    return assets_filter(record_attivo(pdf_blks), filter_data)

pipelines = {
    "fund_assets_begin": Pipeline(
        pdf_extract=(fondo, totale_attivita, valuta),
        text_filter=text_filter_attivo,
        deserialize=carry.deposit,
    ),
    ...
}
```

Nello `algorithms_schedule.csv` la classe dell'attivo sta **prima**, con `Filter next iteration =
TRUE`, o la seconda pagina non vede niente. Le due classi sono distinte perché portano dati diversi,
che per `R27` è ciò che separa due pipeline.
"""

from .document import sole_fund
from .promise import Carryover
from .record import RELEVANT_BLOCK, Record

__all__ = [
    "RELEVANT_BLOCK",
    "Carryover",
    "Record",
    "sole_fund",
]
