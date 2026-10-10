"""MEDIOLANUM-IT24.B: gli investimenti, la situazione patrimoniale, il modulo SFDR, la `manco`.

# La societa' di gestione, che sta nella prosa del revisore (`C09` e `C14`)

Questo bilancio non ha un prospetto di gestione e amministrazione: il nome della societa' di
gestione compare **in una frase**, a p38, nella relazione della societa' di revisione:

```
presente relazione. Siamo indipendenti rispetto al Fondo e a Mediolanum Gestione Fondi SGR p.A.,
Societa' di Gestione del Fondo, in conformita' alle norme e ai principi in materia di etica e di
```

E' una dichiarazione vera — l'apposizione dice **che cos'e'** quel nome — e si legge dalla riga
stessa: il nome sta fra `rispetto al Fondo e a` e la virgola, che e' la forma `MC-5` del template
`manco`. L'alternativa era imporre il valore dalla configurazione, che l'utente aveva messo come
seconda possibilita'; leggere e' meglio, perche' un nome imposto resta giusto solo finche' il
formato lo riguarda.

**L'ancora e' verificata su un documento solo**, perche' di questo formato il corpus ne ha uno. La
formula pero' non e' di questo bilancio: e' la dicitura dei principi di revisione ISA Italia, che
ogni relazione di revisione italiana porta con le stesse parole. Vale la regola generale: chi
scrive un'ancora dice su quanti documenti l'ha vista, e questo e' uno.

Nessun gestore delegato e' dichiarato, quindi `R15` fa della societa' di gestione anche il gestore
degli investimenti, col secondo deserializzatore e l'avviso del motore.
"""



from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractFundStandard,
    PdfExtractCurrencyConstant,
)
from freeports.utils.pdf_extract import (
    PdfLineSelection,
    pdflines_from_pagedict,
)
from freeports.core import Pipeline
from freeports.consts import Currency


def pdf_extract(dict_root):
    """This pdf filter calculate dynamically the sixe of the table using some bound text"""
    lines = pdflines_from_pagedict(dict_root)
    prev_headers = PdfLineSelection(
        font="Helvetica-Bold", text="Elenco degli strumenti finanziari in portafoglio"
    ).select(lines)
    next_table = PdfLineSelection(
        font="Helvetica-Bold", text="Strumenti finanziari quotati"
    ).select(lines)

    if len(next_table) == 0:
        next_table = PdfLineSelection(
            font="Helvetica-Bold", text="STRUMENTI FINANZIARI QUOTATI"
        ).select(lines)
    if len(prev_headers) == 0:
        prev_headers = PdfLineSelection(
            font="Helvetica-Bold",
            text="ELENCO DEGLI STRUMENTI FINANZIARI IN PORTAFOGLIO",
        ).select(lines)

    body_low_limit = 700 if len(next_table) == 0 else next_table[0].bbox[3]
    body_top_limit = 100 if len(prev_headers) == 0 else prev_headers[0].bbox[1]
    std = PdfExtractInvestmentsStandard(
        body_set=PdfLineSelection(
            font="Helvetica",
            area=(0.0, body_top_limit, 1e6, body_low_limit),
        ),
        deselection_list=[PdfLineSelection.text("^ ")],
    )

    return std(dict_root)



# ----------------------------------------------------------------------------------------------
# La situazione patrimoniale, che sta su due pagine (`FA-2` e `FA-3`)
# ----------------------------------------------------------------------------------------------
# Nove comparti in un documento solo, e nove coppie di pagine: dalla p12->13 alla p285->286. Qui
# l'appaiamento per nome non e' una cautela, e' il meccanismo — la promessa che la p12 deposita
# dev'essere ritrovata dalla p13 e da nessun'altra delle otto. Il nome sta nella testatina di
# tutt'e due le pagine, che e' la stessa riga che gli investimenti gia' leggono.

# I due prospetti patrimoniali (`FA-2` e `FA-3`) e la `manco` sono **tutti configurazione**: la
# testatina, le ascisse delle colonne e il netto senza ancore stanno nei commenti di
# `args/pdf_extract.yaml`; `C09` e `C14` — il nome fra la formula e la virgola, e il residuo dei
# gestori che gli ricade addosso perche' nessun delegato e' dichiarato — sono l'`after` di `manco`
# e il `investments_manager_from_manco` del `deserialize`.
#
# Resta la testatina del `fund_heading_set`, che la pipeline degli investimenti usa ancora.
fund_heading_set = PdfLineSelection(font="Helvetica", area=(150, 67, 1e6, 76))

pipelines = {
    "investments": Pipeline(
        pdf_extract=(
            pdf_extract,
            PdfExtractFundStandard(fund_heading_set),
            PdfExtractCurrencyConstant(Currency.EUR),
        )
    ),
}
