"""UBS-EN23: la società di gestione, i gestori delegati, e l'articolo SFDR.

`IM-6`, che è la ricetta in cui i **comparti si elencano prima** del gestore:

```
Portfolio Managers
BPER International SICAV                 (tondo)
– Open Selection Defence                 (corsivo)
– Open Selection Growth
…
Banca Cesare Ponti, Milano, Italy        (tondo: è il gestore)
The Management Company delegated to Banca Cesare Ponti S.p.A. …
```

La sezione comincia in fondo alla **colonna di sinistra** di p4, prosegue per tutta la colonna di
destra e finisce a metà della colonna di sinistra di p5: l'ordine di lettura è **per colonne**, e
leggerla per ordinata mescolerebbe due discorsi diversi.

Sulla stessa pagina la sezione scrive i gestori in **due modi**, e per `R27` sono due letture:
l'elenco appena mostrato, e il paragrafo di prosa *«The Management Company delegated to Nordea
Investment Management AB the day to day portfolio management of BPER International SICAV – Low
Duration European Covered Bond.»*, che è l'unico posto in cui tre delegati sono nominati. Senza il
secondo, due comparti finirebbero nel residuo della società di gestione — cioè attribuiti a chi il
documento dice esplicitamente che non li gestisce.

La `manco` sta su p4 come i primi gestori, e quindi nella **stessa pipeline**: due dati sulla
stessa pagina si uniscono nel `text_filter`, che riceve i blocchi di tutt'e tre i `pdf_extract`.
"""

import re

import inv_managers
import sfdr

from freeports.core import Pipeline, PdfBlock
from freeports.interfaces.pdf_blks import OnePdfBlockType, ResultStandardExtraction
from freeports.standard_funcs.pdf_extract import PdfExtractManagmentCompanyStandard
from freeports.standard_funcs.deserialize import (
    DeserializerFundStandard,
    DeserializerInvestmentsManagerStandard,
    DeserializerManagmentCompanyStandard,
)
from freeports.utils.pdf_extract import (
    PdfLineSelection,
    get_groups,
    pdflines_from_pagedict,
)
from freeports.utils.text_filter import investment_fund_filter_data

# Il corpo della sezione è tutto da 10: il tondo per i nomi e la prosa, il corsivo per i comparti.
# Il grassetto è delle sole intestazioni, e serve solo a trovare dove la sezione comincia.
_BODY = (
    PdfLineSelection(font="frutiger45light", font_size=(9.5, 10.5))
    | PdfLineSelection(font="frutiger45lightitalic", font_size=(9.5, 10.5))
)
_HEADING = PdfLineSelection(
    font="frutiger45lightbold", font_size=(9.5, 10.5), text="^Portfolio Managers"
)

# Le due colonne, misurate: la sinistra comincia a 84 e finisce a 314, la destra comincia a 325.
# La riga di avvertenza in fondo a p5 le attraversa tutt'e due, e l'ascissa la lascia fuori da sola.
_COLUMNS = (("L", (0.0, 0.0, 320.0, 755.0)), ("R", (320.0, 0.0, 600.0, 755.0)))

_PARAGRAPH = 15.0
"""Lo stacco che separa un paragrafo dal successivo.

Le righe di un paragrafo distano 12 punti, i paragrafi fra 18 e 24: il valore sta in mezzo, e
non può salire. A 20 i due paragrafi di p5 che distano 18,5 si fondono, e il nome del comparto si
porta appresso la frase che lo segue."""


def _columns(lines, top):
    """I blocchi della sezione, **per colonne**, con il paragrafo di ciascuno nei metadati.

    `top` è l'ordinata sotto la quale la colonna di sinistra entra nella sezione; la colonna di
    destra ci entra tutta, perché il discorso della pagina passa di lì dopo aver finito a sinistra.
    La chiave di gruppo porta la colonna, o i paragrafi delle due si confonderebbero: `get_groups`
    conta da zero ogni volta che la si chiama.
    """
    blocks = []
    for tag, area in _COLUMNS:
        column = [
            line
            for line in (_BODY & PdfLineSelection.area(*area)).select(lines)
            if tag == "R" or line.bbox[1] >= top
        ]
        for group, line in zip(get_groups(column, _PARAGRAPH), column):
            blocks.append(
                PdfBlock(
                    OnePdfBlockType.RELEVANT_BLOCK.name,
                    {"group": "{}{}".format(tag, group)},
                    line.text,
                )
            )
    return blocks


def pdf_extract_inv_managers_begin(page):
    """p4: la sezione comincia sotto `Portfolio Managers` e prende anche la colonna di destra."""
    lines = pdflines_from_pagedict(page)
    heading = _HEADING.select(lines)
    top = heading[0].bbox[1] if heading else 0.0
    return _columns(lines, top)


def pdf_extract_inv_managers_end(page):
    """p5: la sezione è già aperta, e finisce dove finisce la colonna di sinistra."""
    lines = pdflines_from_pagedict(page)
    return [block for block in _columns(lines, 0.0) if block.metadata["group"].startswith("L")]


# `umbrella` va dichiarato perché a p4 la riga dell'ombrello è in **tondo** mentre i comparti sono
# in corsivo: un elenco che si riconosce dal trattino non la prenderebbe, e i comparti uscirebbero
# senza il prefisso con cui `funds.csv` li scrive (`R24`).
#
# `strip` toglie la città: questo formato scrive il gestore come `Banca Cesare Ponti, Milano,
# Italy`, cioè la sede dentro la ragione sociale, e l'anagrafica vuole `Banca Cesare Ponti`. La
# prosa lo scriverebbe per esteso — `Banca Cesare Ponti S.p.A.` — ma leggere il nome dalla prosa
# costa piu' di quanto renda, e qui la riga dell'elenco basta. Vale per questo formato e non è una
# regola: su FIDEURAM-EN23 p71 `Vontobel Asset Management S.A., Milan Branch` è **un** nome solo.
read_listed = inv_managers.Adjacent(
    inv_managers.Listing(umbrella="BPER International SICAV"),
    where=inv_managers.Where.ABOVE,
    take=inv_managers.Take.FIRST,
    strip=(r",.*$",),
)

# `for` non c'entra: qui il connettore è tutta la formula, e il nome sta fra le due espressioni.
read_prose = inv_managers.ConnectorLine(
    connector=" the day to day portfolio management of ",
    after="The Management Company delegated to ",
)


def _text_filter(pdf_blks, funds, already_assigned=(), settle=True, manco=None):
    """Le due letture sugli stessi blocchi, e l'assegnazione che le riunisce.

    Un paragrafo di prosa non apre nessun elenco, quindi il primo lettore lo lascia cadere; una
    riga d'elenco non porta la formula, quindi il secondo lascia cadere lei. I nomi che compaiono
    in tutt'e due le letture `assign` li fonde (`R22`).
    """
    relevant = [
        block
        for block in pdf_blks
        if block.type_block == OnePdfBlockType.RELEVANT_BLOCK.name
    ]
    return inv_managers.assign(
        list(read_listed(relevant)) + list(read_prose(relevant)),
        funds,
        manco=manco,
        already_assigned=already_assigned,
        settle=settle,
    )


@investment_fund_filter_data
def text_filter_begin(pdf_blks, funds):
    """p4: i gestori dell'elenco e della prosa, più la società di gestione con tutti i comparti.

    Il residuo qui **non** si decide (`settle=False`): la sezione continua a p5, e deciderlo con
    mezza sezione letta darebbe alla società di gestione comparti che la pagina dopo attribuisce a
    Morgan Stanley.
    """
    assignment = _text_filter(pdf_blks, funds, settle=False)
    manco = next(
        (b for b in pdf_blks
         if b.type_block == ResultStandardExtraction.MANAGEMENT_COMPANY.name),
        None,
    )
    blocks = list(inv_managers.text_blocks(assignment))
    if manco is not None:
        blocks.append(inv_managers.management_company_block(assignment, manco))
    return blocks


def text_filter_end(pdf_blks, filter_data):
    """p5: la sezione finisce, e il residuo si calcola su ciò che p4 non ha già assegnato."""
    assignment = _text_filter(
        pdf_blks,
        inv_managers.fund_set(_funds_of(filter_data)),
        already_assigned=inv_managers.assigned_funds(filter_data),
        manco=_declared_manco(filter_data),
    )
    return inv_managers.text_blocks(assignment)


def _declared_manco(filter_data):
    """La società di gestione che p4 ha già letto, a cui tocca ciò che nessun delegato rivendica."""
    from freeports.output import ManagementCompany

    return next(
        (result.name for result in filter_data if isinstance(result, ManagementCompany)),
        None,
    )


def _funds_of(filter_data):
    """I comparti che gli investimenti hanno visto, come li scrivono loro (`R24`)."""
    from freeports.output import Investment

    return [
        result.fund
        for result in filter_data
        if isinstance(result, Investment) and result.fund
    ]


pipelines = {
    "manco": Pipeline(
        pdf_extract=(
            PdfExtractManagmentCompanyStandard(
                PdfLineSelection.area_from_movewindow(
                    PdfLineSelection(font="frutiger45lightbold",font_size=(9.9,10.1),text="Management Company and Domiciliation Agent"),
                    (-0.2,1.9),1.1,1.3
                )
            ),
            pdf_extract_inv_managers_begin,
        ),
        text_filter=text_filter_begin,
        deserialize=(
            DeserializerManagmentCompanyStandard(),
            DeserializerInvestmentsManagerStandard(),
            DeserializerFundStandard(),
        ),
    ),
    "inv_managers_end": Pipeline(
        pdf_extract=pdf_extract_inv_managers_end,
        text_filter=text_filter_end,
        deserialize=(
            DeserializerInvestmentsManagerStandard(),
            DeserializerFundStandard(),
        ),
    ),
    # Il segno e' una `X` di testo, salvo p189 dove e' il `3` di Wingdings 2 -- lo stesso modulo,
    # due tipografie, e i riconoscitori sono tutti attivi per difetto.
    "sfdr_classification": sfdr.ENGLISH.pipeline(
        product_joined=True,
        # `(the "subfund")` sta attaccato al nome su otto moduli su nove, e la
        # normalizzazione lo incolla al nome invece di toglierlo: `R24` non reggerebbe.
        product_prefix=(
            re.compile(r"Product name\s*:\s*"),
            re.compile(r"\s*\((?:the|il|la)\s[^)]*\)\s*$"),
        ),
    ),
}
