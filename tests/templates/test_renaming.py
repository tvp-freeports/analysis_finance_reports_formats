"""`A7` — le ridenominazioni e le fusioni: i due lettori, e che cosa ciascuno lascia fuori.

Ogni caso porta il formato e la pagina da cui viene: le righe non sono inventate, sono quelle
misurate con `inspect-page --mode lines`, accorciate solo dove la prosa non aggiunge niente.
"""

import datetime

import pytest

from freeports.core import PdfBlock

import renaming
from renaming import reading as reading_module


class Recorder:
    """Un registro finto, per leggere ciò che la lettura dice mentre legge."""

    def __init__(self):
        self.warnings = []
        self.errors = []
        self.debugs = []

    def warn(self, message, **_):
        self.warnings.append(message)

    def error(self, message, **_):
        self.errors.append(message)

    def debug(self, message, **_):
        self.debugs.append(message)


@pytest.fixture
def recorder(monkeypatch):
    """Sostituisce il registro del modulo di lettura per la durata di un test."""
    recorder = Recorder()
    monkeypatch.setattr(reading_module, "log", recorder)
    return recorder


def lines(*texts):
    """I blocchi di una sezione: una riga per blocco, come `A2` li consegna."""
    return [PdfBlock("RELEVANT_BLOCK", {}, text) for text in texts]


def read(reader, blocks):
    """I cambi in una forma comoda da confrontare."""
    return [
        (change.old_name, change.current_name, change.when, change.merge)
        for change in reader(blocks)
    ]


AMUNDI = renaming.Listed(
    renamed=(r"have been renamed",),
    merged=(r"have been merged",),
    strip=(r"^Amundi Funds\s+",),
)


class TestListed:
    """Un'intestazione datata apre un elenco — AMUNDI-EN24 p510."""

    def test_the_heading_gives_its_date_to_every_line_below_it(self):
        blocks = lines(
            "The following Sub-Funds have been renamed on 15 March 2024: ",
            "Amundi Funds Pioneer US Bond into Amundi Funds US Bond ",
            "Amundi Funds Pioneer US Corporate Bond into Amundi Funds US Corporate Bond ",
        )

        assert read(AMUNDI, blocks) == [
            ("Pioneer US Bond", "US Bond", "15 March 2024", False),
            ("Pioneer US Corporate Bond", "US Corporate Bond", "15 March 2024", False),
        ]

    def test_a_sibling_section_closes_the_list_instead_of_continuing_it(self):
        """Le tre sezioni di p510 hanno la stessa tipografia, e solo una porta un dato."""
        blocks = lines(
            "The following Sub-Funds have been renamed on 15 March 2024: ",
            "Amundi Funds Pioneer US Bond into Amundi Funds US Bond ",
            "The following Sub-Funds have been liquidated during the year: ",
            "Amundi Funds Global Macro Bonds & Currencies on 12 March 2024 ",
        )

        assert read(AMUNDI, blocks) == [
            ("Pioneer US Bond", "US Bond", "15 March 2024", False),
        ]

    def test_the_date_on_the_line_wins_over_the_one_on_the_heading(self):
        """L'elenco delle fusioni di p510 la data la porta riga per riga, non nell'intestazione."""
        blocks = lines(
            "The following Sub-Funds have been merged during the period: ",
            "Amundi S.F. European Equity Optimal Volatility into Amundi Funds Global Equity "
            "ESG Improvers on 13 October 2023 ",
        )

        assert read(AMUNDI, blocks) == [
            ("Amundi S.F. European Equity Optimal Volatility",
             "Global Equity ESG Improvers", "13 October 2023", True),
        ]

    def test_a_line_with_no_date_anywhere_is_reported_and_dropped(self, recorder):
        blocks = lines(
            "The following Sub-Funds have been merged during the period: ",
            "Amundi Funds Alpha into Amundi Funds Beta ",
        )

        assert read(AMUNDI, blocks) == []
        assert any("no date" in message for message in recorder.warnings)

    def test_a_line_before_any_heading_is_not_a_change(self):
        """L'introduzione della nota nomina vecchi nomi della SICAV, e non sono ridenominazioni."""
        blocks = lines(
            "The name of the Fund was then changed to GIF SICAV into something else ",
            "The following Sub-Funds have been renamed on 15 March 2024: ",
            "Amundi Funds Pioneer US Bond into Amundi Funds US Bond ",
        )

        assert read(AMUNDI, blocks) == [
            ("Pioneer US Bond", "US Bond", "15 March 2024", False),
        ]


DANSKE = renaming.Sentence(
    renamed=(
        r"(?P<old>Danske Invest SICAV\s*[-–]\s*[^.]+?) was renamed (?P<current>[^.]+?)"
        r" effective (?P<when>\d{1,2} \w+ \d{4})",
    ),
    merged=(
        r"(?P<old>Danske Invest SICAV\s*[-–]\s*[^.]+?) merged into (?P<current>[^.]+?)"
        r" on (?P<when>\d{1,2} \w+ \d{4})",
    ),
    strip=(r"^Danske Invest SICAV\s*[-–]\s*",),
)


class TestSentence:
    """Una frase per evento, con verbo e data dentro — DANSKEINVEST-EN24 p351."""

    def test_a_sentence_that_wraps_is_read_whole(self):
        blocks = lines(
            "Danske Invest SICAV - Global Corporate Sustainable Bond was renamed European "
            "Corporate Green Bond effective 22 November ",
            "2024.",
        )

        assert read(DANSKE, blocks) == [
            ("Global Corporate Sustainable Bond", "European Corporate Green Bond",
             "22 November 2024", False),
        ]

    def test_the_sentences_that_declare_no_change_are_left_out(self):
        """Nella stessa sezione ci sono lanci e liquidazioni, che non sono cambi di nome."""
        blocks = lines(
            "Danske Invest SICAV - Global Fixed Income Solution fund launched on 7 November 2024.",
            "Danske Invest SICAV - Multi Asset Inflation Strategy was liquidated on 7 October 2024.",
            "Danske Invest SICAV – India merged into Danske Invest SICAV – Global "
            "Emerging Markets on 21 February 2025.",
        )

        assert read(DANSKE, blocks) == [
            ("India", "Global Emerging Markets", "21 February 2025", True),
        ]

    def test_a_name_never_crosses_the_full_stop_that_ends_the_previous_event(self):
        """È il difetto che il testo riunito fa emergere: senza il punto il nome se le prende tutte."""
        blocks = lines(
            "Danske Invest SICAV - Something Else fund launched on 7 November 2024.",
            "Danske Invest SICAV – India merged into Danske Invest SICAV – Global "
            "Emerging Markets on 21 February 2025.",
        )

        old, _, _, _ = read(DANSKE, blocks)[0]

        assert old == "India"

    def test_a_section_that_declares_the_absence_produces_nothing(self):
        """ARCA-IT24 p6: `Non si segnalano eventi rilevanti.` è il dato, non un buco."""
        assert read(DANSKE, lines("Non si segnalano eventi rilevanti. ")) == []


class TestTheOutputRows:
    """Che cosa il `deserialize` scrive, e come distingue i due verbi."""

    def test_a_renaming_becomes_a_rename_row(self):
        blocks = lines(
            "The following Sub-Funds have been renamed on 15 March 2024: ",
            "Amundi Funds Pioneer US Bond into Amundi Funds US Bond ",
        )
        from freeports.output import Fund

        txt_blks = renaming.text_filter(AMUNDI)(blocks, [Fund(name="US Bond")])
        row = renaming.deserialize()(txt_blks[0])

        assert row.old_name == "Pioneer US Bond"
        assert row.current_name == "US Bond"
        assert row.date == datetime.date(2024, 3, 15)

    def test_a_change_no_fund_of_the_job_carries_is_left_out(self):
        """`R24`: il nome che esce dev'essere quello che gli investimenti scrivono."""
        from freeports.output import Fund

        blocks = lines(
            "The following Sub-Funds have been renamed on 15 March 2024: ",
            "Amundi Funds Pioneer US Bond into Amundi Funds US Bond ",
        )

        assert renaming.text_filter(AMUNDI)(blocks, [Fund(name="Another Fund")]) == []

    def test_the_old_name_can_be_the_one_that_has_to_match(self):
        from freeports.output import Fund

        blocks = lines(
            "The following Sub-Funds have been renamed on 15 March 2024: ",
            "Amundi Funds Pioneer US Bond into Amundi Funds US Bond ",
        )
        kept = renaming.text_filter(AMUNDI, of_interest="old")(
            blocks, [Fund(name="Pioneer US Bond")]
        )

        assert len(kept) == 1


class TestThePublicSurface:
    """Che cosa il pacchetto offre a chi lo importa."""

    def test_everything_a_pipeline_needs_is_reachable_from_the_package(self):
        for name in ("Listed", "Sentence", "text_filter", "deserialize", "BLOCK", "DATE"):
            assert hasattr(renaming, name)
