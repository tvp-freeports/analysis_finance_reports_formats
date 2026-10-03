"""`A3` dal lato dei formati: il modulo periodico SFDR, una lingua alla volta.

`PdfExtractSfdrSignStandard` legge **il segno nella casella** e lo assegna per posizione. Quello
che il motore non può sapere è **come sono scritte** la domanda e le due etichette, perché sono
parole, e le parole sono dell'allegato europeo e della sua lingua. Questo pacchetto le tiene in un
posto solo.

Le lingue pronte sono quattro, e portano l'una la misura dell'altra:

| | domanda | etichette | riga sotto |
|---|---|---|---|
| `ITALIAN` | *aveva un obiettivo di investimento sostenibile* | `Sì` · `No` | *Ha effettuato…* · *Ha promosso…* |
| `ENGLISH` | *have a sustainable investment objective* | `Yes` · `No` (e `Oui` · `Non`) | *It made…* · *…promoted Environmental…* |
| `SPANISH` | *tenía un objetivo de inversión sostenible* | `Sí` · `No` | *Realizó…* · *…promovía características…* |
| `FRENCH` | *avait-il un objectif d'investissement durable* | `Oui` · `Non` | *Il a réalisé…* · *…a promu des caractéristiques…* |

`ENGLISH` porta anche `Oui`/`Non` fra le etichette, e non è una svista: **un solo rapporto
AMUNDI-EN24 scrive le etichette in francese su due moduli su centotré**, con la domanda in inglese.
È la ragione per cui il piano chiede etichette **misurate** e non dedotte dalla lingua del
documento.

Lo `SPANISH` non ha nessun documento su cui provarlo: serve all'**annesso** di
`MEDIOLANUM-ES24.B` (`R30`), e di quell'annesso non esiste un file né nei test né nei 905 della
raccolta. Sta qui perché il giorno in cui arriva non ci sia da rifare il lavoro, e le sue parole
vengono dal testo dell'allegato, non da una pagina misurata — **che è esattamente ciò che lo rende
da verificare**.

L'annesso ha anche una regola sua, `declared_funds`/`only_declared_funds` in `declared.py`: è un
documento a sé, quindi l'articolo si scrive **solo se il fondo coincide** con quello che il
documento principale dello stesso job ha dichiarato.
"""

from .annex import PRODUCT_BLOCK, Annex
from .declared import declared_funds, only_declared_funds

#: Italiano — misurato su ARCA-IT24 p45 e ANIMA_SGR-IT24.
ITALIAN = Annex(
    question="aveva un obiettivo di investimento sostenibile",
    affirmative=("Sì", "SI"),
    negative=("No", "NO"),
    made="Ha effettuato",
    promoted="Ha promosso",
    title="prodotti finanziari di cui all'articolo",
    product="Nome del prodotto",
    product_prefix="Nome del prodotto: ",
    identifier="dentificativo della persona giuridica",
    band=("Caratteristiche ambientali e/o sociali", "biettivo di investimento sostenibile"),
)

#: Inglese — misurato su UBS-EN23, KAIROS-EN23, FINECO-EN23@IR e @LUX, ASTERIA-EN24,
#: DANSKEINVEST-EN24, CARNE-EN23, ANIMA-EN23, AMUNDI-EN24.
ENGLISH = Annex(
    question="have a sustainable investment objective",
    affirmative=("Yes", "Oui"),
    negative=("No", "Non"),
    # `It made` e non `^It made`: su UBS-EN23 la riga comincia con due spazi. E a destra si ancora
    # su `promoted Environmental` perché lì la riga si spezza — `  It ` da una parte,
    # `promoted Environmental/` dall'altra — e `It promoted` non esiste come riga.
    made="It made",
    promoted="promoted Environmental",
    title=("referred to in Article", "pursuant to Article"),
    product="Product name",
    product_prefix="Product name: ",
    identifier=("Legal entity identifier", "Legal Entity Identifier"),
    band=("Environmental and/or social characteristics", "Sustainable investment objective"),
)

#: Spagnolo — **non misurato su nessun documento**: v. il docstring del pacchetto.
SPANISH = Annex(
    question="un objetivo de inversión sostenible",
    affirmative=("Sí", "SI"),
    negative=("No", "NO"),
    made="Realizó",
    promoted="promovía características",
    title="productos financieros a los que se hace referencia en el artículo",
    product="Nombre del producto",
    product_prefix="Nombre del producto: ",
    identifier="dentificador de entidad jur",
    band=("Características medioambientales o sociales", "bjetivo de inversión sostenible"),
)

#: Francese — le etichette sono misurate (AMUNDI-EN24 p777), il resto no: nessun documento della
#: raccolta porta il modulo **interamente** in francese.
FRENCH = Annex(
    question="un objectif d'investissement durable",
    affirmative="Oui",
    negative="Non",
    made="a réalisé",
    promoted="a promu des caractéristiques",
    title="produits financiers visés à l'article",
    product="Nom du produit",
    product_prefix="Nom du produit: ",
    identifier="dentifiant d’entité juridique",
    band=("Caractéristiques environnementales et/ou sociales", "bjectif d’investissement durable"),
)

__all__ = [
    "PRODUCT_BLOCK",
    "Annex",
    "ENGLISH",
    "FRENCH",
    "ITALIAN",
    "SPANISH",
    "declared_funds",
    "only_declared_funds",
]
