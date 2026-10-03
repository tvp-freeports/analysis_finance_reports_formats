"""Gli ancoraggi del modulo periodico SFDR, una lingua alla volta.

Il modulo è l'**allegato del regolamento europeo**: la domanda, le due etichette, le due opzioni
della riga sotto e il titolo sono le stesse parole in ogni rapporto scritto in quella lingua, e non
una scelta del formato. Tenerle qui, e non in sedici moduli d'autore, è la stessa ragione per cui
`A3` è un algoritmo con cinque riconoscitori e non cinque algoritmi: **stessa logica, stesso
codice, e le differenze diventano parametri**.

Quello che invece **resta del formato** è la tipografia — quale riconoscitore serve, quali glifi
sono un segno — e per quello ci sono i parametri di `PdfExtractSfdrSignStandard`, che questa classe
lascia passare com'è.

# Come si mette insieme

```python
import sfdr

pipelines = {
    "sfdr_classification": sfdr.ITALIAN.pipeline(),
}
```

e quando una pagina si discosta, si passa solo ciò che cambia:

```python
sfdr.ENGLISH.pipeline(title="pursuant to Article", demand_investment_funds_match=False)
```

# Perché due tubi e non uno

Il segno e il nome del prodotto sono **due dati sulla stessa pagina**, non due pezzi dello stesso
dato: il primo è geometria, il secondo è una riga di testo con un'etichetta davanti. Sono quindi
due tubi del segmento `pdf_extract`, e il `text_filter` li riunisce — riceve i blocchi di tutti i
tubi della sua pipeline, quindi non serve nient'altro. In particolare **non serve una promessa**:
una promessa è per il dato che sta su un'altra pagina, e qui non c'è niente che attraversi la
pagina.
"""

from freeports.core import Pipeline
from freeports.standard_funcs.deserialize import DeserializeSfdrArticleStandard
from freeports.standard_funcs.pdf_extract import (
    PdfExtractLabelledValueStandard,
    PdfExtractSfdrSignStandard,
)
from freeports.standard_funcs.text_filter import TextFilterSfdrSignStandard
from freeports.utils.pdf_extract import LabelledValueTake, LabelledValueWhere, PdfLineSelection

from .declared import only_declared_funds
from .product import joined_product_pipe

#: Il tipo di blocco con cui il nome del prodotto arriva al `text_filter`. È il difetto che
#: `TextFilterSfdrSignStandard` si aspetta, quindi non va nominato da nessuna delle due parti.
PRODUCT_BLOCK = "FUND_NAME"

#: Qualunque riga che non sia fatta di soli spazi.
#:
#: Nei moduli europei le righe di soli spazi sono dappertutto, e stanno **fra** l'etichetta e il suo
#: valore: senza questa sottrazione, `Product name:` su FINECO-EN23 prende come nome del prodotto
#: una riga di un carattere, lo spazio. Il predicato testuale del motore è una sottostringa con
#: ancore e non una regex, quindi le lunghezze si scrivono una per una invece di `^ +$`.
NOT_BLANK = PdfLineSelection.area(0.0, 0.0, 1e6, 1e6)
for _spaces in range(1, 7):
    NOT_BLANK = NOT_BLANK / PdfLineSelection.text("^" + " " * _spaces + "$")


def _selection(anchors):
    """Una selezione da un ancoraggio o da un'alternativa di ancoraggi.

    L'alternativa serve più spesso di quanto sembri: un solo rapporto AMUNDI-EN24 scrive `Yes`/`No`
    su cento moduli e `X Oui`/`Non` su due, e le etichette vanno **misurate**, non dedotte dalla
    lingua del documento.
    """
    if isinstance(anchors, str):
        anchors = (anchors,)
    selection = None
    for anchor in anchors:
        one = PdfLineSelection.text(anchor)
        selection = one if selection is None else selection | one
    if selection is None:
        raise ValueError("an anchor with no text would select every line of the page")
    return selection


def _label(words):
    """Le tre forme in cui un'etichetta di risposta si presenta davvero.

    Misurate: `'No'` da sola (UBS-EN23), `'No '` con lo spazio che il PDF si porta dietro
    (ARCA-IT24), e `'X No '` con **il segno fuso nella riga dell'etichetta** (ANIMA_SGR-IT24,
    AMUNDI-EN24). Un'ancora sola non le copre: `^No` perde la terza, `No$` perde la seconda. Da qui
    le tre — prefisso, suffisso, suffisso con spazio — per ogni parola.

    Il predicato testuale del motore è una sottostringa con ancore, non una regex, e non normalizza
    gli spazi: ecco perché la forma va scritta e non dedotta.
    """
    if isinstance(words, str):
        words = (words,)
    anchors = []
    for word in words:
        anchors += ["^" + word, word + "$", word + " $"]
    return _selection(anchors)


class Annex:
    """Il modulo periodico in una lingua: che cosa cercare, e dove."""

    def __init__(
        self,
        *,
        question,
        affirmative,
        negative,
        made,
        promoted,
        title,
        product,
        product_prefix,
        identifier,
        band,
    ):
        self.question = question
        self.affirmative = affirmative
        self.negative = negative
        self.made = made
        self.promoted = promoted
        self.title = title
        self.product = product
        self.product_prefix = product_prefix
        self.identifier = identifier
        self.band = band

    def sign(self, **overrides):
        """Il tubo del segno. Ogni parametro di `PdfExtractSfdrSignStandard` si può sovrascrivere.

        Gli ancoraggi si passano come testo — `question="…"`, `title=("…", "…")` — e le selezioni
        le costruisce questa funzione; gli altri parametri (`signs`, `ticked`, `blank`,
        `marks_by_font`) passano al tubo così come sono.
        """
        anchors = {
            "question": overrides.pop("question", self.question),
            "affirmative": overrides.pop("affirmative", self.affirmative),
            "negative": overrides.pop("negative", self.negative),
            "made": overrides.pop("made", self.made),
            "promoted": overrides.pop("promoted", self.promoted),
            "title": overrides.pop("title", self.title),
        }
        return PdfExtractSfdrSignStandard(
            _selection(anchors["question"]),
            (_label(anchors["affirmative"]), _label(anchors["negative"])),
            fallback_labels=(_selection(anchors["made"]), _selection(anchors["promoted"])),
            title=_selection(anchors["title"]),
            **overrides,
        )

    def product_pipes(self, product=None, across=None):
        """I tubi del nome del prodotto (`A1`), e sono **due** perché le impaginazioni sono due.

        Misurate sullo stesso documento, FINECO-EN23@LUX:

        - p223 scrive `Product name : CoRe Series - Bond 6M Fineco AM Fund` su **una riga**, e
          allora il valore è la riga dell'etichetta (`ON_LINE`);
        - p197 scrive `Product name:` in grassetto e il nome **accanto**, come riga a sé, e allora
          il valore sta a destra (`RIGHT`) — saltando le righe di soli spazi, che stanno in mezzo.

        Girano tutt'e due su ogni pagina, in quest'ordine, e il `text_filter` prende **il primo
        blocco che, tolta l'etichetta, non è vuoto**: dove la prima impaginazione non è quella
        giusta il suo tubo porta giù la sola etichetta, che si riduce a niente, e risponde il
        secondo. `take=ALL` e non `FIRST` perché un tubo che non trova niente qui è la normalità,
        non un difetto della pagina.
        """
        label = _selection(product or self.product)
        # Due altezze di riga a destra dell'etichetta, e non oltre: il nome del prodotto comincia
        # dove l'etichetta finisce, mentre l'identificativo della persona giuridica -- che sta sulla
        # stessa banda e ha la stessa forma -- comincia centocinquanta punti piu' in la'.
        window = {"reach": 2.0}
        if across is not None:
            window["across"] = across
        return (
            PdfExtractLabelledValueStandard(
                label,
                PRODUCT_BLOCK,
                "fund",
                where=LabelledValueWhere.ON_LINE,
                take=LabelledValueTake.ALL,
            ),
            PdfExtractLabelledValueStandard(
                label,
                PRODUCT_BLOCK,
                "fund",
                where=LabelledValueWhere.RIGHT,
                value=NOT_BLANK,
                take=LabelledValueTake.ALL,
                **window,
            ),
        )

    def joined_pipes(self, product=None, identifier=None, band=None, prepend=""):
        """Il tubo unico che legge il nome **a capo**, nella colonna dell'etichetta.

        Cinque formati su sette scrivono il nome in piu' righe o in piu' frammenti, e i due tubi di
        `product_pipes` ne portano giu' solo il primo pezzo. Questo li sostituisce con uno solo:
        la colonna dell'etichetta, dalla sua riga fino al primo appiglio che chiude il blocco.
        Il perche' di ogni scelta sta in `product.py`.
        """
        return (
            joined_product_pipe(
                _selection(product or self.product),
                _selection(identifier or self.identifier),
                _selection(band or self.band),
                PRODUCT_BLOCK,
                prepend,
            ),
        )

    def pipeline(
        self,
        *,
        product=None,
        product_across=None,
        product_pipes=None,
        product_prefix=None,
        product_joined=False,
        product_prepend="",
        identifier=None,
        band=None,
        demand_investment_funds_match=True,
        demand_declared_fund=False,
        also_deserialize=(),
        **overrides,
    ):
        """La pipeline intera: i tubi, il filtro che li riunisce, il cast.

        `product_pipes` sostituisce del tutto i due tubi predefiniti, e serve al formato il cui nome
        del prodotto **va a capo**: `A1` restituisce un blocco per riga e non le riunisce, quindi
        quel caso vuole un tubo scritto dal formato. Gli basta emettere blocchi di tipo
        `PRODUCT_BLOCK`.

        `product_joined` sceglie il lettore a colonna di `joined_pipes` al posto dei due tubi
        predefiniti: e' quello che serve dove il nome va a capo, o dove il PDF lo spezza in
        frammenti che nessuno dei due tubi riunisce.

        `demand_declared_fund` tiene l'articolo **solo se il fondo è già stato dichiarato** da una
        pagina di uno step precedente del job, e serve all'annesso che è un documento a sé: è la
        forma in cui `R30` si realizza. Non è un doppione di `demand_investment_funds_match`, che
        guarda i fondi *degli investimenti* e solo quando il loro nome non è una promessa — il
        perché sta in `declared.py`.

        `also_deserialize` aggiunge deserializzatori accanto a quello dell'articolo.
        """
        prefix = self.product_prefix if product_prefix is None else product_prefix
        if product_pipes is None and product_joined:
            product_pipes = self.joined_pipes(product, identifier, band, product_prepend)
        text_filter = TextFilterSfdrSignStandard(
            prefix, demand_investment_funds_match=demand_investment_funds_match
        )
        if demand_declared_fund:
            text_filter = only_declared_funds(text_filter)
        return Pipeline(
            (self.sign(**overrides),)
            + tuple(
                product_pipes
                if product_pipes is not None
                else self.product_pipes(product, product_across)
            ),
            text_filter,
            (DeserializeSfdrArticleStandard(),) + tuple(also_deserialize),
        )
