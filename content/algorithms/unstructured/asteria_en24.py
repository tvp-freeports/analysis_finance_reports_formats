"""Modulo d'autore di ASTERIA-EN24: solo il modulo periodico SFDR.

Gli investimenti stanno al livello strutturato e non si toccano. Qui c'e' una pipeline sola, e la
ragione per cui il formato merita un modulo e' che **sette moduli usano due riconoscitori**: tre
scrivono il segno come una `X` di testo (Arial o Calibri), tre come il glifo `U+F0FE` di Wingdings,
uno come un'immagine. Nessuno dei tre e' dichiarato: i riconoscitori sono tutti attivi per difetto,
ed e' esattamente il caso per cui `A3` e' un algoritmo solo con cinque riconoscitori.

Il nome del prodotto porta l'**ombrello** (`ASTERIA FUNDS – …`), il richiamo di nota (`…1`) e la
qualificazione fra parentesi (`(the "Sub-Fund")`), e su una pagina i due punti sono **doppi**
(`Product name: : ASTERIA …`).
"""

import re

import sfdr

pipelines = {
    "sfdr_classification": sfdr.ENGLISH.pipeline(
        product_joined=True,
        # I due punti sono doppi su una pagina, e la qualificazione fra parentesi --
        # `(the "Sub-Fund")`, `(the "Portfolio")` -- chiude ogni nome.
        product_prefix=(
            re.compile(r"Product name\s*:[\s:]*"),
            re.compile(r"\s*\((?:the|il|la)\s[^)]*\)\s*$"),
        ),
    ),
}
