"""`A6` — gli indicatori ESG: un indicatore senza numero non esiste.

Le righe vengono da due pagine misurate: FINECO-EN23@IR D1 p894, che risponde con sei frasi
numerate, e ANIMA_SGR-IT24 D1 p1726, che risponde con sola prosa. È la stessa configurazione a
leggerle tutt'e due, e questo insieme di test è il posto dove si vede.
"""

from freeports.core import PdfBlock

import esg
from esg import LeadingNumber


def lines(*texts):
    """I blocchi di una sezione: una riga per blocco, come `A2` li consegna."""
    return [PdfBlock("RELEVANT_BLOCK", {}, text) for text in texts]


def read(reader, blocks):
    """Gli indicatori in una forma comoda da confrontare: valore, nome."""
    return [(i.value, i.name) for i in reader(blocks)]


FINECO = lines(
    "1.",
    "93.07% of the Fund was invested in securities of issuers with favourable ESG characteristics ",
    "in accordance with Fidelity’s Sustainable Investing Framework.",
    "2.",
    "in respect of its direct investments in corporate issuers, 0% of the Fund invested in ",
    "securities of issuers with exposure to the Exclusions.",
    "3.",
    "38.42% of the Fund was invested in sustainable investments.",
)


class TestLeadingNumber:
    """La frase comincia col numero, e il nome è il resto — FINECO-EN23@IR p894."""

    def test_each_numbered_item_is_one_indicator(self):
        assert read(LeadingNumber(), FINECO) == [
            ("93.07%",
             "of the Fund was invested in securities of issuers with favourable ESG "
             "characteristics in accordance with Fidelity’s Sustainable Investing Framework"),
            ("38.42%", "of the Fund was invested in sustainable investments"),
        ]

    def test_an_item_that_does_not_begin_with_a_number_is_not_an_indicator(self):
        """La seconda voce di p894 comincia con una premessa: il numero c'è ma non apre la frase.

        `R11` è una regola sul **valore**, non sul testo: tenere quella voce vorrebbe dire scrivere
        come nome dell'indicatore la premessa, e come valore un numero che sta in mezzo alla frase.
        """
        second = FINECO[4:6]

        assert read(LeadingNumber(), second) == []

    def test_a_section_of_prose_alone_produces_nothing(self):
        """ANIMA_SGR-IT24 p1726: quattro righe di discorso e nessuna misura (`R11`)."""
        prose = lines(
            "Gli indicatori di sostenibilità usati da questo prodotto finanziario sono "
            "rappresentati ",
            "dall’esclusione dei Paesi sanzionati dalle Nazioni Unite a livello di governo "
            "centrale per ",
            "sistematiche violazioni dei diritti umani. ",
        )

        assert read(LeadingNumber(), prose) == []

    def test_a_plain_number_is_a_value_as_much_as_a_percentage(self):
        """KAIROS-EN23 p114 misura `1.42` e `127.38`, che percentuali non sono."""
        assert read(LeadingNumber(marker=None), lines("1.42 tonnes of GHG emissions")) == [
            ("1.42", "tonnes of GHG emissions")
        ]

    def test_the_percentage_sign_stays_with_the_value_and_not_with_the_name(self):
        """È la stessa misura scritta in due unità diverse: il segno appartiene al valore."""
        value, name = read(LeadingNumber(marker=None), lines("93.07% of the Fund"))[0]

        assert value == "93.07%"
        assert not name.startswith("%")

    def test_without_the_marker_the_group_is_what_separates_two_items(self):
        blocks = [
            PdfBlock("RELEVANT_BLOCK", {"group": 0}, "10% of the first thing"),
            PdfBlock("RELEVANT_BLOCK", {"group": 1}, "20% of the second thing"),
        ]

        assert read(LeadingNumber(marker=None), blocks) == [
            ("10%", "of the first thing"),
            ("20%", "of the second thing"),
        ]

    def test_a_name_can_be_cut_where_the_precisions_begin(self):
        cut = LeadingNumber(max_name=30)

        _, name = read(cut, FINECO)[0]

        assert len(name) <= 30


class TestTheOutputRows:
    """Che cosa il `text_filter` e il `deserialize` scrivono."""

    def test_the_fund_is_the_one_the_caller_names(self):
        blocks = esg.text_filter(LeadingNumber(), "ALPHA FUND")(FINECO, [])
        row = esg.deserialize(blocks[0])

        assert row.fund == "ALPHA FUND"
        assert row.value == "93.07%"

    def test_the_fund_can_be_looked_up_when_the_page_does_not_name_it(self):
        def owner(pdf_blks, filter_data):
            return filter_data[0]

        blocks = esg.text_filter(LeadingNumber(), owner)(FINECO, ["BETA FUND"])

        assert esg.deserialize(blocks[0]).fund == "BETA FUND"

    def test_a_page_without_indicators_never_asks_who_it_belongs_to(self):
        """La domanda costa una ricerca, e su una pagina di sola prosa non ha risposta né serve."""
        asked = []

        def owner(pdf_blks, filter_data):
            asked.append(True)
            return "ALPHA FUND"

        assert esg.text_filter(LeadingNumber(), owner)(lines("solo prosa"), []) == []
        assert not asked


class TestThePublicSurface:
    """Che cosa il pacchetto offre a chi lo importa."""

    def test_everything_a_pipeline_needs_is_reachable_from_the_package(self):
        for name in ("LeadingNumber", "Indicator", "text_filter", "deserialize", "BLOCK"):
            assert hasattr(esg, name)


class TestDatedRows:
    """AMUNDI-EN24 p778: il nome sopra, una riga per serie, una colonna per esercizio.

    I metadati sono quelli che il `pdf_extract` del formato scrive, e i valori vengono dalla
    pagina: `Weighted Average Carbon Intensity` vale 71 per il prodotto nell'esercizio in corso,
    72 nel precedente, e 83 / 101 per l'indice `Stoxx 600`.
    """

    def blocks(self):
        rows = [
            ("Weighted Average Carbon Intensity", 0, 0, "71"),
            ("Weighted Average Carbon Intensity", 0, 1, "72"),
            ("Weighted Average Carbon Intensity", 1, 0, "83"),
            ("Weighted Average Carbon Intensity", 1, 1, "101"),
            ("Carbon Footprint", 0, 0, "12"),
            ("Carbon Footprint", 0, 1, "16"),
            ("Coverage (% invested)", 0, 0, "96.51%"),
            ("Coverage (% invested)", 0, 1, "100.00%"),
        ]
        return [
            PdfBlock("REL", {"indicator": name, "series": series, "column": column}, value)
            for name, series, column, value in rows
        ]

    def test_only_the_product_and_only_the_year_in_course(self):
        read = esg.DatedRows()

        assert [(i.name, i.value) for i in read(self.blocks())] == [
            ("Weighted Average Carbon Intensity", "71"),
            ("Carbon Footprint", "12"),
            ("Coverage (% invested)", "96.51%"),
        ]

    def test_the_benchmark_row_is_reachable_by_asking_for_it(self):
        """Non si estrae, ma il parametro c'è: è una scelta del formato, non una regola del lettore."""
        read = esg.DatedRows(series=1)

        assert [(i.name, i.value) for i in read(self.blocks())] == [
            ("Weighted Average Carbon Intensity", "83"),
        ]

    def test_a_cell_that_is_not_a_number_is_not_an_indicator(self):
        """`R11`: l'ultima riga di ogni blocco della pagina è una nota di fonte, non una misura."""
        blocks = [
            PdfBlock("REL", {"indicator": "Carbon Footprint", "series": 0, "column": 0},
                     "Source Montpensier Finance / MSCI"),
        ]

        assert esg.DatedRows()(blocks) == []

    def test_a_cell_without_its_indicator_is_dropped(self):
        blocks = [PdfBlock("REL", {"series": 0, "column": 0}, "71")]

        assert esg.DatedRows()(blocks) == []
