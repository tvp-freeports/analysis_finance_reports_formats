"""`U7` — il dato che una pagina lascia a quella dopo.

Sei formati italiani scrivono l'attivo su una pagina e il passivo con il netto su quella seguente.
`FundAssets` porta i tre importi insieme e li controlla insieme (`R32`), quindi nessuna delle due
pagine da sola può costruire la riga: il totale delle attività deve **attraversare** il confine.

# Perché una promessa, e non un campo promissibile

La scelta è la **Strada 1** (`CLUSTERS-format-data-coverage.md` §11), e la ragione non è il costo.
Rendere promissibili i tre importi sposterebbe il controllo dell'equazione **dopo** la risoluzione,
in `accumulate.rs::resolve`, che gira fuori dagli span `job`, `document` e `page`: con `R32`
l'equazione che non torna uscirebbe come errore **senza dire in quale documento e a quale pagina**,
cioè il silenzio di oggi con una riga in più. La costruzione dell'entità è l'ultimo punto in cui il
contesto diagnostico esiste ancora, ed è lì che il controllo deve restare.

Quindi la promessa non viene mai risolta dal motore: è solo il **veicolo**. La prima pagina la
deposita restituendo un dizionario dal suo `deserialize`; la seconda la ritrova in `data.previous()`
e ne fa un metadato, e il suo deserializzatore costruisce l'entità con tutt'e tre gli importi già
concreti.

# Perché nel `text_filter`, e non nel `deserialize`

Il `deserialize` riceve **solo il blocco**, non il `filter_data`: non ha modo di vedere che cosa la
pagina prima ha lasciato. Ma anche potendo, non sarebbe il suo lavoro — appaiare due pagine per
nome di comparto è un'interpretazione, e per `R23` le interpretazioni stanno nel `text_filter`.

# L'appaiamento è per nome, e il nome si confronta normalizzato

Le due pagine si appaiano **col nome del fondo**, non con la contiguità dei numeri di pagina: il
prospetto del passivo di un comparto può stare a dieci pagine da quello del suo attivo. Il confronto
passa per `MatchFund`, che normalizza in profondità, così un accento o uno spazio doppio scritto
diversamente sulle due pagine non perde la riga.

# Dove va messo nella catena, e perché l'ordine non è indifferente

`resume` va **per ultimo**, dopo il filtro sui fondi d'interesse:

```python
def text_filter(pdf_blks, filter_data):
    return carry.resume(assets_filter(record(pdf_blks), filter_data), filter_data)
```

Messo lì, ogni blocco che gli arriva parla di un comparto d'interesse, e non trovare la promessa è
davvero un difetto — la pagina dell'attivo non è stata classificata, oppure `R24` è violata e le
due pagine scrivono il nome in due modi. Messo prima, la stessa mancanza sarebbe il caso normale di
un comparto che non interessa, e distinguere i due casi non sarebbe più possibile.
"""

from freeports import log
from freeports.core import TextBlock
from freeports.utils.text_filter import MatchFund


class Carryover:
    """I campi che la prima delle due pagine lascia alla seconda.

    ```python
    carry = Carryover("tot_assets")
    ```

    L'oggetto si costruisce **una volta per formato** e lo usano tutt'e due le pipeline — la prima
    con `deposit`, la seconda con `resume`. È il punto del progetto: l'identificativo della promessa
    è scritto in un posto solo, e le due pagine non possono più chiamarlo in due modi diversi.
    """

    def __init__(self, *fields, fund_key="fund", separator="@"):
        if not fields:
            raise ValueError("a carryover with no field would carry nothing")
        if not separator:
            raise ValueError("an empty separator would make the field and the fund unsplittable")
        self.fields = tuple(fields)
        self.fund_key = fund_key
        self.separator = separator

    def __repr__(self):
        return "Carryover({}, fund_key={!r}, separator={!r})".format(
            ", ".join(repr(f) for f in self.fields), self.fund_key, self.separator
        )

    def promise_id(self, field, fund):
        """L'identificativo, scritto qui e in nessun altro posto.

        Vale **dentro un job** e non oltre: la risoluzione delle promesse è a livello di job, quindi
        `tot_assets@<fondo>` non può collidere con quello di un'altra riga del file di batch.
        """
        return "{}{}{}".format(field, self.separator, fund)

    def deposit(self, block):
        """Il `deserialize` della prima pagina: la promessa che lascia alla seconda.

        Si passa **così com'è** come deserializzatore della pipeline —
        `deserialize=carry.deposit` — perché è ciò che un deserializzatore fa: riceve un blocco e
        restituisce un risultato, e un dizionario è la forma in cui il motore riconosce delle
        promesse.
        """
        metadata = block.metadata
        fund = metadata.get(self.fund_key)
        if not fund:
            log.error(
                "a block with no '{}' cannot leave anything to the next page: it is dropped"
                .format(self.fund_key)
            )
            return {}
        entries = {}
        for field in self.fields:
            value = metadata.get(field)
            if value is None:
                log.warn(
                    "'{}' is not on this page: the next one will have no {} for '{}'"
                    .format(field, field, fund)
                )
                continue
            entries[self.promise_id(field, fund)] = value
        return entries

    def promised(self, filter_data):
        """Ciò che le pagine precedenti di questo job hanno lasciato: `{MatchFund: {campo: valore}}`.

        Le promesse attraversano il confine verso Python **come dizionari**, quindi si riconoscono
        per tipo. Le chiavi che non cominciano con uno dei campi di questo `Carryover` sono di
        qualcun altro — un altro dato a cavallo, sulla stessa corsa — e si lasciano stare.
        """
        out = {}
        for result in filter_data:
            if not isinstance(result, dict):
                continue
            for key, value in result.items():
                field, fund = self._split(str(key))
                if field is None:
                    continue
                out.setdefault(MatchFund(fund), {})[field] = value
        return out

    def _split(self, key):
        """Il campo e il comparto scritti in un identificativo, o `(None, None)` se non è nostro.

        Si divide **per prefisso noto** e non sul separatore, perché il nome di un comparto può
        contenere il separatore e il nome di un campo no.
        """
        for field in self.fields:
            prefix = field + self.separator
            if key.startswith(prefix):
                return field, key[len(prefix):]
        return None, None

    def resume(self, blocks, filter_data):
        """L'ultimo passo del `text_filter` della seconda pagina.

        Ogni blocco riceve nei metadati ciò che la prima pagina aveva promesso per il suo comparto.
        Un blocco per cui la promessa non c'è **non passa**, e lo dice: arrivato fin qui, il suo
        comparto è d'interesse, quindi la pagina dell'attivo o non è stata letta o scrive il nome
        in un altro modo — e in tutt'e due i casi la riga che manca è un dato perso, non un dato che
        non c'era (`R12`).
        """
        available = self.promised(filter_data)
        out = []
        for block in blocks:
            fund = block.metadata.get(self.fund_key)
            carried = available.get(MatchFund(fund)) if fund else None
            missing = [f for f in self.fields if carried is None or f not in carried]
            if missing:
                log.error(
                    "nothing was carried over for '{}': {} of this statement {} on the page that "
                    "was never read, and the row is dropped"
                    .format(
                        fund,
                        ", ".join(missing),
                        "stays" if len(missing) == 1 else "stay",
                    )
                )
                continue
            metadata = dict(block.metadata)
            metadata.update(carried)
            out.append(TextBlock.from_content(block.type_block, metadata, block.content))
        return out
