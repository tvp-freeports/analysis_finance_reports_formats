"""ARCA-IT24: gli attivi a cavallo di due pagine, e la sezione degli eventi che li nega.

`FC-5`. `Eventi rilevanti` di p6 è una sezione che c'è, si apre, e **dichiara l'assenza**:
*«Non si segnalano eventi rilevanti.»* Non è un buco da riempire — è il dato, e leggerlo è la
prova che la sezione è stata trovata. La pipeline è quella di tutti gli altri, e il risultato
vuoto viene da sé: nessuna frase della sezione porta un evento, quindi nessuna riga esce.

L'intestazione **è un parametro** e non una costante (`R13`): ARCA scrive `Eventi rilevanti`,
AMUNDI-IT24 scrive `Eventi che hanno interessato il fondo`.
"""


from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractFundStandard,
    PdfExtractCurrencyConstant,
)
from freeports.consts import Currency
from freeports.utils.pdf_extract import PdfLineSelection
from freeports.core import Pipeline


subfund_set = PdfLineSelection.area(0.0, 0.0, 1e6, 60.0) & (
    PdfLineSelection.font("Calibri") | PdfLineSelection.font("Lato-Regular")
)


body_set = PdfLineSelection(
    font="TrebuchetMS", font_size=(6.95, 6.97)
) & PdfLineSelection.area_from_bounds(
    x0=0.0,
    y0=PdfLineSelection(
        font="Lato-Regular",
        text="Elenco analitico dei principali strumenti finanziari detenuti dal Fondo",
        font_size=(11.9, 12.1),
    ),
    x1=1e6,
    y1=1e6,
)


# I due prospetti patrimoniali (`FA-2` e `FA-3`) sono **tutti configurazione**: `fund` +
# `currency_constant` + `labelled_value` nel `pdf_extract`, con le ascisse delle colonne e la
# sottrazione delle classi di quote nello `args/pdf_extract.yaml`; `labelled_assets` nel
# `text_filter`, `carryover_deposit` e `assets` nel `deserialize`. Le due pagine sono due classi e
# due pipeline perche' portano dati diversi (`R27`), e nello `algorithms_schedule.csv` quella
# dell'attivo viene prima, con `Filter next iteration = TRUE`.


# La sezione degli eventi (`FC-5`) e' configurazione: `section` nel `pdf_extract`, `renaming` nei
# due segmenti dopo. L'intestazione e il corpo stanno in `args/pdf_extract.yaml`.

# Il `text_filter` e il `deserialize` sono del motore: `renaming` legge i cambi nella forma
# che questa sezione usa, tiene quelli che riguardano un comparto del job (`R24`) e converte
# la data. Gli schemi stanno in `content/algorithms/semistructured/args/text_filter.yaml`.

pipelines = {
    "investments": Pipeline(
        pdf_extract=(
            PdfExtractInvestmentsStandard(body_set=body_set),
            PdfExtractFundStandard(subfund_set),
            PdfExtractCurrencyConstant(Currency.EUR),
        )
    ),
    # L'articolo si legge dalla casella spuntata, non dal titolo: il titolo resta come verifica
    # (`R34`). Su questo formato il segno è un'immagine, e una sola nella banda -- la casella vuota
    # e' disegnata, non fotografata.
}
