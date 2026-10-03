"""MEDIOLANUM-ES24.B — il rapporto spagnolo, che arriva in **due file**.

Il documento principale nomina il comparto in copertina ed elenca i suoi investimenti; l'**annesso**
porta il modulo periodico SFDR e sta in `annex.py`. I due si passano **nello stesso job**, perché è
un rapporto solo:

```console
$ freeports -f MEDIOLANUM-ES24.B -i rapporto.pdf -i annesso.pdf …
```

Fino al 2026-09-26 l'annesso era un formato a parte, `MEDIOLANUM-ES24.Bax`, e in quella forma non
poteva funzionare: un job ha **un** formato, quindi l'annesso e il documento a cui appartiene non
potevano nemmeno stare nella stessa corsa, e il confronto fra i loro comparti non aveva dove
avvenire. `R30` è la fusione, e il commento sul prezzo che ha sta in `annex.py`.

# La società di gestione, che la copertina dichiara accanto al comparto (`C08`)

La prima pagina mette le etichette in grassetto da 7,85 e i valori in tondo **sulla stessa riga**:

```
Gestora:        MEDIOLANUM GESTION, S.G.I.I.C., S.A.
Grupo Gestora:  MEDIOLANUM
Auditor:        PRICE WATERHOUSE COOPERS AUDITORES S.L.
```

L'ancora è `^Gestora:` e non `Gestora:`, perché `Grupo Gestora:` contiene la stessa parola e la
riga che apre è un'altra.

**Si legge nella pipeline della copertina, non in una classe sua**, e la ragione è doppia. La
geometrica: `cover` è la classe di pagina 1 — la sua intestazione la riconosce da `Grupo Gestora:`
e `Registro CNMV:` — e una pagina che corrispondesse a due classi non verrebbe assegnata a nessuna
delle due, perdendo tutt'e due le letture. E quella dello scadenzario: il blocco della società di
gestione porta i comparti che il job ha visto (`R26`), e `cover` corre **prima** degli
investimenti, quindi di comparti visti non ce ne sarebbero. Non serve spostare niente, perché è la
copertina stessa a dichiarare il comparto: la società di gestione esce con quello, letto sulla sua
stessa pagina.
"""

from typing import List, Optional, Any
from enum import auto, Enum

import sfdr
from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractCurrencyConstant,
    PdfExtractLabelledValueStandard,
)
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.interfaces.text_blks import ResultStandardFiltering
from freeports.utils.pdf_extract import (
    LabelledValueWhere,
    PdfLineSelection,
    pdflines_from_pagedict,
)
from freeports.standard_funcs.deserialize import (
    DeserializerInvestmentStandard,
    DeserializerInvestmentsManagerFromManco,
    DeserializerManagmentCompanyStandard,
)
from freeports.interfaces.text_blks import StandardManagmentCompanyTextBlock
from freeports.utils.text_filter import MatchFund
from freeports.utils.deserialize import deserialize_block_types
from freeports.consts import Currency
from freeports.output import Fund
from freeports.core import PdfBlock, TextBlock,Promise,Pipeline

from . import annex


class PdfBlockType(Enum):
    """Types of PDF blocks for MEDIOLANUM_ES24_B format."""

    RELEVANT_BLOCK = auto()


class TextBlockType(Enum):
    """Types of text blocks for MEDIOLANUM_ES24_B format."""

    BOND_TARGET = auto()
    EQUITY_TARGET = auto()


class FirstPageTextBlockType(Enum):
    """Types of text blocks for MEDIOLANUM_ES24_B format."""

    SUBFUND = auto()


def pdf_extract_first_page(dict_root) -> List[PdfBlock]:
    lines = pdflines_from_pagedict(dict_root)
    sl = PdfLineSelection.area(0, 88, 1e6, 102).select(lines)[0]
    subfund = sl.text.strip().upper()
    return [PdfBlock(PdfBlockType.RELEVANT_BLOCK.name, {"subfund": subfund}, sl.text)]


# `C08`. L'etichetta e il valore stanno sulla stessa riga, quindi `RIGHT`: fra la fine
# dell'etichetta (112,8) e l'inizio del nome (140,7) ci sono ventott'otto punti di spazio.
pdf_extract_manco = PdfExtractLabelledValueStandard(
    PdfLineSelection(font="helvetica-bold", font_size=(7.5, 8.2), text="^Gestora:"),
    ResultStandardExtraction.MANAGEMENT_COMPANY.name,
    "managment company",
    where=LabelledValueWhere.RIGHT,
)


def text_filter_first_page(
    pdf_blocks: List[PdfBlock], targets: List[str]
) -> List[TextBlock]:
    """Il comparto della copertina, e la società di gestione che la stessa pagina dichiara."""
    subfunds = [
        blk for blk in pdf_blocks
        if blk.type_block == PdfBlockType.RELEVANT_BLOCK.name
    ]
    if not subfunds:
        return []
    subfund = subfunds[0].metadata["subfund"]
    blocks = [
        TextBlock(
            FirstPageTextBlockType.SUBFUND.name,
            {"subfund": subfund},
            subfunds[0],
        )
    ]
    for blk in pdf_blocks:
        if blk.type_block != ResultStandardExtraction.MANAGEMENT_COMPANY.name:
            continue
        name = str(blk.content).strip()
        if name:
            # Il comparto è quello che questa pagina ha appena letto: `R26` vuole la società di
            # gestione su tutti i comparti del documento, e questo rapporto ne ha uno.
            blocks.append(
                StandardManagmentCompanyTextBlock.from_name(name, [MatchFund(subfund)])
            )
    return blocks


# I due deserializzatori della copertina guardano **solo** il blocco del comparto: da quando la
# stessa pipeline legge anche la societa' di gestione, i blocchi che arrivano sono di due tipi, e
# un deserializzatore che li prendesse tutti cercherebbe `subfund` dove non c'e'.
@deserialize_block_types(FirstPageTextBlockType.SUBFUND.name)
def deserialize_first_page(txt_blk: Optional[TextBlock]) -> Optional[Any]:
    return {"title document": txt_blk.metadata["subfund"]}


@deserialize_block_types(FirstPageTextBlockType.SUBFUND.name)
def deserialize_subfund(txt_blk: Optional[TextBlock]) -> Optional[Any]:
    """Il comparto che la copertina dichiara, che e' anche quello degli investimenti."""
    return Fund(name=txt_blk.metadata["subfund"])



@deserialize_block_types(
    ResultStandardFiltering.BOND_TARGET.name,
    ResultStandardFiltering.EQUITY_TARGET.name,
    ResultStandardFiltering.FUND.name
)
def deserialize(txt_blk: Optional[TextBlock]) -> Optional[Any]:
    """Deserialize text blocks into structured data for MEDIOLANUM_ES24_B format.

    Parameters
    ----------
    txt_blk : Optional[TextBlock]
        Text block to deserialize, or None

    Returns
    -------
    Optional[Any]
        Deserialized data object or None if input is None

    Notes
    -----
    Handles subfund context resolution and applies specific scaling
    to market values (multiplies by 1000).
    """
    if txt_blk.type_block==ResultStandardFiltering.FUND.name:
        return None
    std = DeserializerInvestmentStandard()
    blk = std(txt_blk)
    if blk is not None:
        blk.market_value = blk.market_value * 1000
    return blk



pipelines = {
    "investments": Pipeline(
        pdf_extract=(
            PdfExtractInvestmentsStandard(
                body_set=PdfLineSelection.font("Helvetica"),
                deselection_list=[
                    PdfLineSelection.text("Cartera de inversiones financieras a"),
                    PdfLineSelection(text="-$", font="Helvetica"),
                ]
            ),
            PdfExtractCurrencyConstant(Currency.EUR),
            lambda _: [PdfBlock(ResultStandardExtraction.FUND_NAME.name,{},Promise("title document"))]
        ),
        deserialize=deserialize,
    ),
    "subfund": Pipeline(
        pdf_extract=(pdf_extract_first_page, pdf_extract_manco),
        text_filter=text_filter_first_page,
        deserialize=(
            deserialize_first_page,
            deserialize_subfund,
            DeserializerManagmentCompanyStandard(),
            DeserializerInvestmentsManagerFromManco(),
        ),
    ),
    # L'annesso, che nello scadenzario sta in uno step **dopo** la copertina: il fondo lo dichiara
    # lei, e `demand_declared_fund` è ciò che va a leggerlo. `demand_investment_funds_match` resta
    # spento perché su questo formato guarderebbe un campo ancora promesso (v. `sfdr/declared.py`).
    "sfdr_classification": sfdr.SPANISH.pipeline(
        product_pipes=(annex.pdf_extract_product,),
        product_prefix=[],
        demand_investment_funds_match=False,
        demand_declared_fund=True,
    ),
}
