"""Il nome del prodotto quando **va a capo**, o quando non sta sulla riga dell'etichetta.

`PdfExtractLabelledValueStandard` restituisce **un blocco per riga** e non le riunisce, perche'
riunirle e' interpretazione di testo e non geometria. Per i moduli in cui il nome sta tutto su una
riga questo basta, e i due tubi predefiniti di `Annex.product_pipes` lo leggono. Per gli altri no,
e gli altri sono la maggioranza dei formati misurati:

| formato | come il nome e' scritto |
|---|---|
| AMUNDI-EN24 | l'etichetta su una riga, il nome sulle **due o tre** righe sotto, e ogni riga spezzata in cinque frammenti dove cambia il carattere |
| AMUNDI-IT24 | l'etichetta e il primo pezzo sulla stessa riga, il resto sulle **due** righe sotto |
| CARNE-EN23 | l'etichetta sola, il nome sulla riga sotto, la qualificazione `(the "Sub-Fund")` su quella dopo |
| ASTERIA-EN24 | tutto su una riga, ma in **tre** frammenti, e su una pagina i due punti sono doppi |
| UBS-EN23 | tutto su una riga, in due frammenti |

# La regola, che e' una sola

Il nome e' **quello che sta nella colonna dell'etichetta**, dalla riga dell'etichetta fino al primo
appiglio che chiude il blocco. Le righe si raggruppano per **fascia di ordinate** — due frammenti
che si sovrappongono in verticale sono la stessa riga, anche se i loro `y` differiscono di due punti
perche' il carattere cambia — si ordinano per ascissa dentro la fascia, e si uniscono: **senza
spazio** dentro una fascia, perche' li' il PDF spezza le parole a meta' (`G` + `REAT`), e **con uno
spazio** fra una fascia e l'altra, perche' li' spezza fra una parola e l'altra.

# I due appigli, e perche' sono le parole dell'allegato

La colonna finisce dove comincia quella dell'**identificativo della persona giuridica**, e il blocco
finisce dove comincia la **fascia** del modulo — *caratteristiche ambientali e/o sociali* oppure
*obiettivo di investimento sostenibile*. Sono parole del modello europeo, non del formato, quindi
stanno in `Annex` accanto alla domanda e alle etichette: un formato non le dichiara.

Quale dei due chiuda il blocco lo decide la pagina e non il formato, ed e' misurato: dove
l'identificativo sta **sotto** l'etichetta (UBS-EN23, ASTERIA-EN24) chiude lui, e prendere la fascia
si porterebbe dietro l'identificativo stesso; dove sta **accanto** (AMUNDI, CARNE-EN23) non c'e'
niente sotto fino alla fascia, e chiude lei.
"""

from freeports.core import PdfBlock
from freeports.utils.pdf_extract import pdflines_from_pagedict

#: Quanto due frammenti possono discostarsi e restare la stessa riga, e quanto una riga puo'
#: sporgere a sinistra dell'etichetta o a destra della colonna accanto. Un punto tipografico:
#: misurato, il valore di UBS-EN23 comincia **due decimi di punto prima** del bordo destro della sua
#: etichetta, e quello di ASTERIA-EN24 un punto e tre.
SLACK = 1.5


def _rows(lines):
    """Le righe raggruppate per fascia di ordinate, dall'alto in basso e da sinistra a destra.

    Il criterio e' la **mezzeria**, non la sovrapposizione delle scatole, e la fascia **non cresce**
    man mano che i frammenti si aggiungono. Misurato su AMUNDI-EN24 p777, dove la sovrapposizione
    sbaglia: il frammento `G` sporge di due punti sotto la sua riga, la fascia cresciuta arriva a
    toccare quella dopo, e `G`+`REAT` finiscono in coda al nome invece che in mezzo. Le mezzerie
    delle due righe distano un'altezza intera, quindi mezza altezza le separa senza ambiguita'.
    """
    rows = []
    for line in sorted(lines, key=lambda one: (one.bbox[1] + one.bbox[3], one.bbox[0])):
        _, y0, _, y1 = line.bbox
        middle = (y0 + y1) / 2
        for row in rows:
            if abs(middle - row["middle"]) <= row["tolerance"]:
                row["lines"].append(line)
                break
        else:
            rows.append({"middle": middle, "tolerance": max(y1 - y0, 1.0) / 2, "lines": [line]})
    return [sorted(row["lines"], key=lambda one: one.bbox[0]) for row in rows]


def _first(selection, lines):
    """La prima riga che la selezione prende, o `None`."""
    for line in selection.select(lines):
        return line
    return None


def joined_product_pipe(label, column, band, block_type, prepend=""):
    """Il tubo che restituisce il nome del prodotto in **un blocco solo**.

    `label` e' la selezione dell'etichetta, `column` quella dell'identificativo della persona
    giuridica, `band` quella delle due intestazioni di fascia. Il blocco esce con l'etichetta ancora
    attaccata: toglierla e' mestiere del `text_filter`, che per questo ha `product_prefix`.

    `prepend` e' la parola che l'allegato **non scrive** e gli investimenti si': MEDIOLANUM-IT24.B
    intitola i suoi comparti `Fondo Mediolanum ...` sulle pagine del portafoglio e `Mediolanum ...`
    sul modulo, e senza rimetterla davanti `R24` non regge e la riga si perde in silenzio. Va davanti
    al nome e **non** davanti all'etichetta, quindi si applica dopo, quando l'etichetta e' gia' via:
    per questo e' un parametro del tubo e non una stringa in piu' nel `product_prefix`, che toglie
    e non aggiunge.
    """

    def pipe(page):
        lines = pdflines_from_pagedict(page)
        anchor = _first(label, lines)
        if anchor is None:
            return []
        ax0, ay0, _, ay1 = anchor.bbox

        # A destra: la colonna accanto, ma solo se sta **sulla riga** dell'etichetta. Sotto, non
        # restringe niente -- e' un appiglio di fine blocco, non un bordo.
        right = 1e6
        for line in column.select(lines):
            x0, y0, _, y1 = line.bbox
            if y0 < ay1 and y1 > ay0 and x0 > ax0:
                right = min(right, x0)

        # Sotto: il primo appiglio che comincia **dopo** la riga dell'etichetta, fra la colonna
        # accanto e le due intestazioni di fascia.
        bottom = 1e6
        for line in list(column.select(lines)) + list(band.select(lines)):
            y0 = line.bbox[1]
            if y0 >= ay1:
                bottom = min(bottom, y0)

        inside = [
            line
            for line in lines
            if line.bbox[0] >= ax0 - SLACK
            and line.bbox[2] <= right + SLACK
            and line.bbox[1] >= ay0 - SLACK
            and line.bbox[3] <= bottom + SLACK
        ]
        pieces = []
        for row in _rows(inside):
            chunk = ""
            for one in row:
                chunk += one.text
                # Subito **dopo l'etichetta**, cosi' che il `product_prefix` la tolga e la parola
                # resti in testa al nome. Prima dell'etichetta finirebbe nella parte che si toglie.
                # Il confronto e' sulla scatola e non sull'identita': ogni selezione costruisce
                # oggetti nuovi, quindi due letture della stessa riga non sono lo stesso oggetto.
                if prepend and one.bbox == anchor.bbox:
                    chunk += " " + prepend + " "
            pieces.append(chunk)
        name = " ".join(" ".join(pieces).split())
        return [PdfBlock(block_type, {}, name)] if name else []

    return pipe
