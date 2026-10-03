"""ANIMA_SICAV-EN24: gli investimenti, e la societa' di gestione di pagina 5.

Il prospetto `Management and Administration` mette l'etichetta sopra il valore e il valore e' tutta
la riga:

```
Management Company
ANIMA SGR S.p.A.
99, Corso Garibaldi
20121 Milan (Italy)
```

Le etichette di quella pagina sono le sole righe in `arialnarrow-bold` da 9 — `Board of Directors of
the SICAV`, `Registered Office`, `Administrative Address`, `Management Company` — e il testo
dell'ancora le distingue fra loro. `BELOW` col collocamento per difetto prende la **prima** riga
sotto, che e' il nome: la seconda e la terza sono l'indirizzo, e non si vogliono.

Nessun gestore delegato e' dichiarato in questo bilancio, quindi `R15` fa della societa' di gestione
anche il gestore degli investimenti: e' il secondo deserializzatore, e il motore lo dice con un
avviso perche' il dato e' dedotto e non letto.
"""

import re

import manco
from freeports.core import Pipeline
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.interfaces.text_blks import ResultStandardFiltering
from freeports.standard_funcs.deserialize import (
    DeserializerInvestmentsManagerFromManco,
    DeserializerManagmentCompanyStandard,
)
from freeports.standard_funcs.pdf_extract import PdfExtractLabelledValueStandard
from freeports.standard_funcs.text_filter import TextFilterInvestmentsStandard
from freeports.utils.pdf_extract import LabelledValueWhere, PdfLineSelection

market_value_regex = re.compile(r"(([0-9]+,)?[0-9]+,?[0-9]+\.[0-9]{2}) ")
# non sono sicuro di come ho riscritto questa regex e a cosa servivano le parentesi

std = TextFilterInvestmentsStandard(
    nominal_quantity_pos=0,
    perc_net_assets_pos=3,
    acquisition_currency_pos=1,
    market_value_pos=2,
)

fund_remove_regex=re.compile(r"\(in .+\)")
def text_filter(pdf_blks, target_companies):
    """
    Text extract that extract quantity from the name of the company (is conained in the same cell)
    """
    txt_blks = std(pdf_blks, target_companies)
    for txt_blk in txt_blks:
        if txt_blk.type_block==ResultStandardFiltering.FUND.name:
            txt_blk.content=fund_remove_regex.sub("",txt_blk.content).replace("*","")
            continue
        c = txt_blk.content
        m = market_value_regex.match(c)
        txt_blk.metadata |= {
            "quantity": m[0],
        }
        txt_blk.metadata["fund"]=fund_remove_regex.sub("",txt_blk.metadata["fund"]).replace("*","")
    return txt_blks


pdf_extract_manco = PdfExtractLabelledValueStandard(
    PdfLineSelection(
        font="arialnarrow-bold", font_size=(8.5, 9.5), text="^Management Company"
    ),
    ResultStandardExtraction.MANAGEMENT_COMPANY.name,
    "managment company",
    where=LabelledValueWhere.BELOW,
)

pipelines = {
    "investments": Pipeline(text_filter=text_filter),
    # `C03` e `C12`: il nome e' tutta la riga, quindi la lettura e' `str.strip` e non un pezzo di
    # riga da ritagliare.
    "manco": Pipeline(
        pdf_extract_manco,
        manco.text_filter(str.strip),
        (
            DeserializerManagmentCompanyStandard(),
            DeserializerInvestmentsManagerFromManco(),
        ),
    ),
}
