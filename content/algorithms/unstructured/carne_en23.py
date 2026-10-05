"""Modulo d'autore di CARNE-EN23: gli investimenti, la societa' di gestione e i gestori di p4.

# I gestori di pagina 4 (`C16`)

Il prospetto `Management and Administration` dichiara i gestori in fondo alla **colonna di
sinistra**, sotto `Investment Managers`, e non c'e' nessuna tipografia che distingua un nome dal
suo indirizzo: nome, specificazione e indirizzo sono tutti arialmt 8.04. A separare un'entrata
dalla prossima c'e' solo lo **stacco verticale** — 9.2 punti fra due righe della stessa entrata,
18.4 fra l'ultima riga di una e il nome della prossima — ed e' geometria, quindi la numerazione
delle entrate la fa il `pdf_extract` (`entry_gap`) e al `text_filter` resta il solo lavoro di dire
quale riga di un'entrata sia il nome.

Le due entrate dicono due cose diverse:

- `ARCA Fondi SGR S.p.A.` **non nomina comparti**, quindi si prende il residuo: e' il gestore di
  tutti e dieci (`R15`);
- `Goldman Sachs Asset Management International Ltd.` porta *«(in charge for the USD nominated
  securities in the subfund Sidera Funds SICAV - Global High Yield)»*, cioe' una parte sola del
  comparto. Entra per quel comparto, e il comparto **resta** nel residuo, perche' del resto
  risponde ancora ARCA: e' il ramo `partial` di `R21`, e questa pagina e' il caso misurato per cui
  `Parenthetical.partial_markers` esiste.

La specificazione nomina il comparto dopo `in the subfund`, e quel marcatore e' obbligatorio: senza
di lui il comparto sarebbe la frase intera.
"""


from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.standard_funcs.pdf_extract import (
    PdfExtractInvestmentsStandard,
    PdfExtractCurrencyStandard,
    PdfExtractFundStandard,
    PdfExtractManagmentCompanyStandard,
    PdfExtractSectionStandard,
)
from freeports.utils.pdf_extract import (
    pdfline_selection_from_str,
    PdfLineSelection,
)
from freeports.standard_funcs.text_filter import (
    TextFilterManagmentCompanyStandard,
)
from freeports.standard_funcs.deserialize import (
    DeserializerManagmentCompanyStandard,
)
from freeports.core import Pipeline


subfund_set = PdfLineSelection(
    font="ArialMT", font_size=(6.95, 6.97)
) & PdfLineSelection.area_from_movewindow(
    target=pdfline_selection_from_str('ArialMT[6.96] "^Annual report including"'),
    vec=(0.1, 0.8),
    width_mult=2.0,
    height_mult=1.4,
)

currency_set = pdfline_selection_from_str('Arial-BoldMT "Valuation in"')
body_set = pdfline_selection_from_str("ArialMT[6.96](160:786)")

# Il prospetto e' a due colonne: a sinistra fino a 249.8, a destra da 291.6. Duecentonovanta sta in
# mezzo, e serve perche' la sezione dei gestori e' l'ultima della sua colonna e senza il confine si
# porterebbe dietro quello che le capita accanto.
#
# Il pavimento a 700 toglie il piede di pagina — l'ultima riga del prospetto chiude a 693.1, il
# numero di pagina sta a 787.6 — che altrimenti sarebbe un'entrata in piu', con `2` per nome e il
# residuo in mano. Le righe di un solo spazio sono le code degli oggetti di testo spezzati e non
# portano niente: entrano in un'entrata e, prima delle righe vere, ne diventerebbero il nome.
_INV_MANAGERS_BODY = PdfLineSelection.area(0.0, 0.0, 290.0, 700.0) / PdfLineSelection.text("^ $")

pdf_extract_inv_managers = PdfExtractSectionStandard(
    PdfLineSelection(font="arial-boldmt", font_size=(7.9, 8.1))
    & PdfLineSelection.text("^Investment Managers"),
    ResultStandardExtraction.INVESTMENTS_MANAGER.name,
    "investments managers",
    body=_INV_MANAGERS_BODY,
    # Quindici sta fra i 9.2 di una stessa entrata e i 18.4 fra due entrate.
    entry_gap=15.0,
)

# Il `text_filter` dei gestori sta nel livello `semistructured`: la specificazione e' la frase fra
# parentesi sotto il nome, `in the subfund ` nomina i comparti e `in charge for ` dice che il
# gestore ne ha **una parte** sola, cioe' `R21`.
pipelines = {
    "investments": Pipeline(
        pdf_extract=(
            PdfExtractInvestmentsStandard(currency_set=currency_set, body_set=body_set),
            # `C29`: a pagina 65 e 69 il titolo del comparto e' spezzato in **due** oggetti di testo
            # sulla stessa ordinata (`Sidera Funds SICAV - ` e `Euro ESG Credit`), e il tubo
            # standard porta giu' la prima riga sola -- cioe' mezzo nome, che fa nascere un fondo
            # `SIDERA FUNDS SICAV` a cui restano appesi sette titoli che sono di
            # `SIDERA FUNDS SICAV EURO ESG CREDIT`.
            PdfExtractFundStandard(subfund_set, join=" "),
            PdfExtractCurrencyStandard(currency_set),
        )
    ),
    "manco": Pipeline(
        pdf_extract=PdfExtractManagmentCompanyStandard(
            PdfLineSelection.area_from_movewindow(
                PdfLineSelection(
                    font="arial-boldmt", font_size=(7.9, 8.1), text="Management Company"
                ),
                (-0.1, 0.8),
                100,
                2.5,
            )
            & PdfLineSelection.area_from_bounds(
                x1=PdfLineSelection(
                    font="arial-boldmt", font_size=(7.9, 8.1), text="Legal adviser"
                ),
                x0=0,
                y0=0.0,
                y1=1e6,
            )
        ),
        text_filter=TextFilterManagmentCompanyStandard(),
        deserialize=DeserializerManagmentCompanyStandard(),
    ),
    # `C16`: i gestori stanno sulla stessa pagina della societa' di gestione, quindi la pipeline e'
    # un'altra ma la classe di pagina e' la sua — il legame lo fa `mapping.csv`.
    "inv_managers": Pipeline(
        pdf_extract=pdf_extract_inv_managers,
    ),
}
