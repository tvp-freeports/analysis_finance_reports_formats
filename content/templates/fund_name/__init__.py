"""Il nome del comparto ripulito di ciò che non ne fa parte.

Un rapporto scrive il nome del comparto sopra la tabella degli investimenti, e sulle pagine di
continuazione gli aggiunge qualcosa che **non è il nome**: `(continued)` in inglese, un richiamo di
nota, un confronto fra parentesi con l'esercizio prima. Il motore non lo sa — per lui quella riga è
il nome — e il nome storpiato non fa perdere *una* riga: fa perdere **tutte** le righe legate a quel
comparto, perché la chiave di unicità di `funds.csv` è il nome e un comparto scritto in due modi
diventa due fondi. È `R24`, e si vede solo guardando i nomi, non i dati che mancano.

Ripulire il nome è **interpretazione di testo**, quindi sta nel `text_filter` (`R23`): il
`pdf_extract` ha già fatto il suo lavoro quando ha trovato la riga giusta.

```python
import fund_name

std = TextFilterInvestmentsStandard(...)
text_filter = fund_name.cleaned(std, drop=(re.compile(r"\\(.*\\)"),), substrings=("*",))
```

Il nome scritto su più righe **non sta più qui**: riunire le righe selezionate è un parametro del
tubo del motore, `PdfExtractFundStandard(selection, join=" ")`, da quando le due varianti si sono
fuse (erano lo stesso algoritmo, e differivano solo in questo). Chi ha un nome spezzato dentro una
parola passa `join=""`.

Il tubo ripulisce **tutt'e due** i posti in cui il nome finisce: il blocco `FUND`, da cui nasce la
riga di `funds.csv`, e la chiave `fund` dei metadati di ogni titolo, da cui nasce il legame
investimento → fondo. Pulirne uno solo è peggio di non pulirne nessuno, perché i titoli finiscono
appesi a un fondo che nel CSV non c'è.
"""

from .cleaning import cleaned, strip

__all__ = ["cleaned", "strip"]
