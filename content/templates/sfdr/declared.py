"""L'annesso che è un **documento a sé**: l'articolo si tiene solo se il fondo è già stato dichiarato.

# Che problema risolve

`MEDIOLANUM-ES24.B` pubblica il rapporto in due file: il documento principale, che nomina il
comparto e ne elenca gli investimenti, e l'**annesso** col modulo periodico SFDR, che del comparto
non ha nient'altro che il nome del prodotto in testa al modulo. Passati insieme sono **un job**
(«Several documents in one run»): le pagine di tutt'e due finiscono in una sola vasca e lo scadenzario
gira una volta sopra l'unione, quindi lo step dell'annesso riceve come `filter_data` ciò che lo step
del documento principale ha estratto. È lì che si legge se il fondo coincide — e `R30` chiede
esattamente questo: **l'articolo dell'annesso si estrae solo se il fondo coincide con quello letto dal
documento principale**.

# Perché non basta `demand_investment_funds_match`

Il parametro del motore c'è già, e guarda i fondi **degli investimenti** dello step precedente —
`resolved_investment_funds`, che di ogni riga prende `fund.resolved()`. Su questo formato quel
controllo non può funzionare: gli investimenti di `MEDIOLANUM-ES24.B` non nominano il comparto, lo
**promettono** (`Promise("title document")`, depositata dalla pagina di copertina), e le promesse le
risolve il genitore *dopo* aver raccolto tutti i job. Durante lo scadenzario quel campo è ancora
pendente, `resolved()` dà `None`, l'insieme dei fondi noti è vuoto e **ogni** articolo dell'annesso
verrebbe scartato.

Qui invece si guarda ciò che nello stesso `filter_data` è già un nome: i `Fund` che una pagina ha
dichiarato — la copertina del documento principale ne dichiara uno — e il campo `fund` di qualunque
risultato che lo porti scritto per esteso. Le due strade non si escludono: un formato il cui
documento principale nomina i comparti dentro le righe degli investimenti è servito da tutt'e due.

# Dove vive, e perché qui

È **interpretazione di testo**, quindi `text_filter` (`R23`): confrontare due modi di scrivere un
nome non è geometria e non è un cast. Il confronto usa `MatchFund`, cioè la stessa identità che il
motore usa per deduplicare i fondi, e non una normalizzazione scritta a mano.

# Il prezzo, dichiarato

Il nome nell'annesso deve **coincidere** col nome nel documento principale a meno di
normalizzazione. Se l'annesso premette l'ombrello dove il principale non lo fa, il confronto
fallisce e l'articolo si perde: è `R24`, ed è la ragione per cui lo scarto si **avvisa** invece di
essere silenzioso. Nessun rapporto `.Bax` esiste — né nei test né nei 905 della raccolta — quindi
questa coincidenza è **da verificare** il giorno in cui un documento arriva.
"""

from freeports import log
from freeports.output import Fund
from freeports.utils.text_filter import MatchFund


def declared_funds(filter_data):
    """I nomi dei fondi che gli step precedenti del job hanno già dichiarato, normalizzati.

    Due sorgenti, e nessuna delle due è una scelta di comodo:

    - i `Fund`, che sono la dichiarazione esplicita «questo comparto esiste» — il nome può però
      essere ancora una promessa, e una promessa non è un nome: si scarta;
    - il campo `fund` di qualunque altro risultato che lo porti già scritto (un investimento, un
      prospetto di attivi), che è la forma in cui la maggior parte dei formati nomina il comparto.
    """
    names = set()
    for result in filter_data:
        candidate = result.name if isinstance(result, Fund) else getattr(result, "fund", None)
        if isinstance(candidate, str) and candidate.strip():
            names.add(MatchFund(candidate).n_name)
    return names


def only_declared_funds(pipe):
    """Il `text_filter` di `pipe`, che tiene un blocco solo se il suo fondo è già stato dichiarato.

    Si avvolge attorno al filtro dell'annesso — che di suo il fondo non lo verifica, perché
    `demand_investment_funds_match` guarda un'altra cosa (v. il docstring del modulo) — e non ne
    cambia né i blocchi né i metadati: decide soltanto quali passano.
    """

    def text_filter(pdf_blks, filter_data):
        blocks = pipe(pdf_blks, filter_data)
        if not blocks:
            return blocks
        declared = declared_funds(filter_data)
        if not declared:
            log.error(
                "no page of this job has declared a fund yet: this annex cannot be matched against "
                "the report it belongs to, and its disclosure is dropped - was the main document "
                "passed in the same job?"
            )
            return []
        kept = []
        for block in blocks:
            name = str(block.content).strip()
            if MatchFund(name).n_name in declared:
                kept.append(block)
            else:
                log.warn(
                    "'{}' is not a fund this report declares: the annex's article is dropped - it "
                    "is either another fund's annex or the same fund written differently".format(
                        name
                    )
                )
        return kept

    return text_filter
