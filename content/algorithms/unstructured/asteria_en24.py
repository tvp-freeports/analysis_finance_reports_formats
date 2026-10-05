"""Modulo d'autore di ASTERIA-EN24: il modulo periodico SFDR, e il prospetto di pagina 3.

Gli investimenti stanno al livello strutturato e non si toccano. La ragione per cui il formato
merita un modulo e' che **sette moduli usano due riconoscitori**: tre scrivono il segno come una
`X` di testo (Arial o Calibri), tre come il glifo `U+F0FE` di Wingdings, uno come un'immagine. Nessuno dei tre e' dichiarato: i riconoscitori sono tutti attivi per difetto,
ed e' esattamente il caso per cui `A3` e' un algoritmo solo con cinque riconoscitori.

Il nome del prodotto porta l'**ombrello** (`ASTERIA FUNDS – …`), il richiamo di nota (`…1`) e la
qualificazione fra parentesi (`(the "Sub-Fund")`), e su una pagina i due punti sono **doppi**
(`Product name: : ASTERIA …`).

La seconda pipeline e' il prospetto `Management and Administration of the SICAV` di pagina 3, che
questo bilancio scrive **identico** a quello di ASTERIA-EN23: le due etichette in grassetto da 9.98
in due colonne — `Management Company:` a sinistra con `Waystone Management Company (Lux) S.A.`,
`Investment Manager and Global Distributor:` a destra con `ASTERIA Investment Managers S.A.` — e
sotto ciascuna il nome, poi l'indirizzo. Per questo la ricetta non e' qui ma in
l'algoritmo `inv_managers` del livello `semistructured`, e il modulo porta solo le ancore.

Il corpo di 9.98 nelle etichette non e' un dettaglio: il titolo della pagina e' 13.97 e i nomi sono
in tondo, quindi il grassetto da 9.98 e' **esattamente** l'insieme delle etichette. `BELOW` col
collocamento per difetto prende la prima riga sotto, che e' il nome: la seconda e' l'indirizzo.
"""


from freeports.core import Pipeline
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.standard_funcs.pdf_extract import PdfExtractLabelledValueStandard
from freeports.utils.pdf_extract import LabelledValueWhere, PdfLineSelection

_LABEL = PdfLineSelection(font="centurygothic-bold", font_size=(9.5, 10.5))

pdf_extract_manco = PdfExtractLabelledValueStandard(
    _LABEL & PdfLineSelection.text("^Management Company:"),
    ResultStandardExtraction.MANAGEMENT_COMPANY.name,
    "managment company",
    where=LabelledValueWhere.BELOW,
)

pdf_extract_inv_managers = PdfExtractLabelledValueStandard(
    _LABEL & PdfLineSelection.text("^Investment Manager and Global Distributor:"),
    ResultStandardExtraction.INVESTMENTS_MANAGER.name,
    "investments managers",
    where=LabelledValueWhere.BELOW,
)

pipelines = {
    # `C04` e `C15`: la societa' di gestione e il gestore, che pagina 3 dichiara insieme.
    "inv_managers": Pipeline((pdf_extract_manco, pdf_extract_inv_managers)),
}
