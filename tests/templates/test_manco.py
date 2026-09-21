"""La società di gestione letta dentro la riga che la dichiara.

Ogni riga di questi test è misurata con `inspect-page --mode lines` sul formato citato: nessuna è
inventata, e dove è accorciata lo è solo nell'indirizzo, che non partecipa alla lettura.

Le quattro forme del §4.1 di `RECIPES-format-data-coverage.md` — `MC-3`, `MC-4`, `MC-5` e la riga
che EURIZON-IT24 scriveva a mano — sono lo stesso lettore con due parametri diversi; `U6` è la
regola in più che serve a una sola di loro.
"""

import datetime

import pytest

from freeports.core import PdfBlock

import manco
from manco import Between, first, most_recent
from manco import reading as reading_module


class Recorder:
    """Un registro finto, per leggere ciò che la lettura dice mentre legge."""

    def __init__(self):
        self.warnings = []
        self.errors = []
        self.infos = []
        self.debugs = []

    def warn(self, message, **_):
        self.warnings.append(message)

    def error(self, message, **_):
        self.errors.append(message)

    def info(self, message, **_):
        self.infos.append(message)

    def debug(self, message, **_):
        self.debugs.append(message)

    def warn_imposed(self, **_):
        pass


@pytest.fixture
def recorder(monkeypatch):
    """Sostituisce il registro del modulo di lettura per la durata di un test."""
    recorder = Recorder()
    monkeypatch.setattr(reading_module, "log", recorder)
    return recorder


def manco_blocks(*texts):
    """I blocchi che `A1` consegna al `text_filter` della `manco`."""
    return [PdfBlock("MANAGEMENT_COMPANY", {}, text) for text in texts]


class TestBetween:
    """`Between`: il nome è il pezzo di riga fra due espressioni fisse."""

    def test_the_label_opens_the_line_and_the_name_is_the_rest(self):
        """`MC-3` — ANIMA_SGR-IT24 D1 p3, la testata che ogni pagina ripete."""
        read = Between(after="Società di Gestione del Risparmio")
        line = "Società di Gestione del Risparmio ANIMA SGR S.p.A. "
        assert read(line) == "ANIMA SGR S.p.A."

    def test_a_parenthesis_closes_the_name(self):
        """`MC-4` — EURIZON-EN21 p7, dove la parentesi porta il periodo."""
        read = Between(before=r"\(")
        assert read("Eurizon Capital S.A. (since July 1, 2021)") == "Eurizon Capital S.A."

    def test_the_name_sits_inside_a_sentence(self):
        """`MC-5` — FIDEURAM-EN23 p67, la nota 1 del bilancio."""
        read = Between(after="it is managed by", before=r"\(the")
        line = (
            "The Fund has been created for an indefinite period and it is managed by "
            "Fideuram Asset Management (Ireland) dac (the “Management Company”)."
        )
        assert read(line) == "Fideuram Asset Management (Ireland) dac"

    def test_a_comma_closes_the_name(self):
        """EURIZON-IT24 D1 p7, la riga che il formato leggeva con una regex sua."""
        read = Between(after="gestione", before=",")
        line = (
            "La società di gestione Eurizon Capital SGR S.p.A., con sede in Milano, "
            "gestisce il fondo."
        )
        assert read(line) == "Eurizon Capital SGR S.p.A."

    def test_with_neither_marker_the_whole_line_is_the_name(self):
        """Il lettore senza parametri non è un errore: è la riga intera, ripulita."""
        assert Between()("  Kairos Partners SGR S.p.A.  ") == "Kairos Partners SGR S.p.A."

    def test_a_line_without_the_opening_marker_is_not_read(self):
        """Un indirizzo sotto il nome non ha la forma attesa, e chi chiama lo salta."""
        assert Between(after="it is managed by")("37/A, Avenue J.F. Kennedy") is None

    def test_a_line_without_the_closing_marker_is_not_read(self):
        assert Between(before=r"\(the")("L-1855 Luxembourg") is None

    def test_the_markers_are_regular_expressions(self):
        """`R28` vale per l'ancora del `pdf_extract`; qui il motivo è la parentesi da proteggere."""
        assert Between(after=r"Manager:?\s*")("Manager: Acme AM S.A.") == "Acme AM S.A."

    def test_the_first_closing_marker_wins(self):
        """Non greedy: il nome finisce alla **prima** occorrenza, non all'ultima."""
        assert Between(before=",")("Acme AM S.A., Milano, Italia") == "Acme AM S.A."


class TestFirst:
    """`first`: il caso normale, una società sola sulla pagina."""

    def test_it_takes_the_first_line(self):
        assert first(["Acme AM S.A.", "Beta AM S.A."]) == "Acme AM S.A."

    def test_no_line_is_no_answer(self):
        assert first([]) is None


class TestMostRecent:
    """`U6`: di due società dichiarate col loro periodo, quella in carica alla chiusura."""

    EURIZON_EN21 = [
        "Pramerica Management Company S.A. (until June 30, 2021)",
        "37/A, Avenue J.F. Kennedy",
        "L-1855 Luxembourg",
        "Eurizon Capital S.A. (since July 1, 2021)",
        "8, avenue de la Liberté",
        "L-1930 Luxembourg",
    ]

    def test_the_company_in_charge_at_closing_is_kept(self, recorder):
        """EURIZON-EN21 p7: entra il 1º luglio 2021, e alla chiusura c'è ancora."""
        assert most_recent(self.EURIZON_EN21) == "Eurizon Capital S.A. (since July 1, 2021)"

    def test_the_addresses_never_compete(self, recorder):
        """Un indirizzo sta sotto il suo nome come ci sta il nome successivo: filtra la parentesi."""
        most_recent(self.EURIZON_EN21)
        assert recorder.warnings == []

    def test_it_says_that_it_chose(self, recorder):
        """Due società nominate e una estratta: il registro lo dice, e non è un avviso."""
        most_recent(self.EURIZON_EN21)
        assert len(recorder.infos) == 1
        assert "2" in recorder.infos[0]

    def test_a_single_qualified_company_says_nothing(self, recorder):
        most_recent(["Acme AM S.A. (since July 1, 2021)"])
        assert recorder.infos == []

    def test_without_any_qualification_it_falls_back_to_the_first(self, recorder):
        """Il caso dei venticinque formati che la società non l'hanno cambiata."""
        assert most_recent(["Acme AM S.A.", "Beta AM S.A."]) == "Acme AM S.A."
        assert recorder.infos == []

    def test_an_open_period_beats_a_closed_one_on_the_same_day(self, recorder):
        """Chi entra il 30 giugno c'è alla chiusura; chi esce il 30 giugno no."""
        texts = ["Acme AM S.A. (until June 30, 2021)", "Beta AM S.A. (since June 30, 2021)"]
        assert most_recent(texts) == "Beta AM S.A. (since June 30, 2021)"

    def test_only_outgoing_companies_keeps_the_last_to_leave(self, recorder):
        """Non estrarre niente sarebbe peggio: si tiene la più vicina alla chiusura."""
        texts = ["Acme AM S.A. (until March 31, 2021)", "Beta AM S.A. (until October 1, 2021)"]
        assert most_recent(texts) == "Beta AM S.A. (until October 1, 2021)"

    def test_the_verbs_are_read_regardless_of_case(self, recorder):
        """`Until` maiuscolo è quello che EURIZON-EN21 scrive nella colonna dei consiglieri."""
        texts = ["Acme AM S.A. (Until June 21, 2021)", "Beta AM S.A. (Since June 22, 2021)"]
        assert most_recent(texts) == "Beta AM S.A. (Since June 22, 2021)"

    def test_a_day_first_date_is_read_too(self, recorder):
        texts = ["Acme AM S.A. (since 1 July 2021)", "Beta AM S.A. (since 30 June 2021)"]
        assert most_recent(texts) == "Acme AM S.A. (since 1 July 2021)"

    def test_a_parenthesis_that_is_not_a_period_is_not_a_qualification(self, recorder):
        """`(Ireland)` non porta nessuno dei verbi, quindi non entra nel confronto e non avvisa."""
        assert most_recent(["Fideuram Asset Management (Ireland) dac"]) == (
            "Fideuram Asset Management (Ireland) dac"
        )
        assert recorder.warnings == []

    def test_a_qualification_without_a_readable_date_warns(self, recorder):
        """`R25`: ciò che si vede e non si sa leggere si dichiara, non si scarta in silenzio."""
        assert most_recent(["Acme AM S.A. (since the merger)"]) == "Acme AM S.A. (since the merger)"
        assert len(recorder.warnings) == 1


class TestTextFilter:
    """Il `text_filter` completo, dalla riga al blocco."""

    def test_it_declares_the_name_on_the_funds_of_the_document(self):
        """`R26`: la società di gestione è uno a molti su tutto il documento."""
        filter_manco = manco.text_filter(Between(after="Società di Gestione del Risparmio"))
        blocks = filter_manco(
            manco_blocks("Società di Gestione del Risparmio ANIMA SGR S.p.A. "),
            [],
        )
        assert len(blocks) == 1
        assert blocks[0].content == "ANIMA SGR S.p.A."

    def test_it_picks_the_line_before_reading_it(self):
        """`U6` sceglie **quale** riga, `Between` che cosa dentro quella riga: in quest'ordine."""
        filter_manco = manco.text_filter(Between(before=r"\("), among=most_recent)
        blocks = filter_manco(manco_blocks(*TestMostRecent.EURIZON_EN21), [])
        assert blocks[0].content == "Eurizon Capital S.A."

    def test_a_page_without_the_block_fails_that_page(self):
        from freeports.core import PageParseFail

        filter_manco = manco.text_filter(Between())
        with pytest.raises(PageParseFail):
            filter_manco([], [])

    def test_a_line_of_the_wrong_shape_fails_that_page(self):
        """Meglio la pagina saltata e detta che una società di gestione inventata."""
        from freeports.core import PageParseFail

        filter_manco = manco.text_filter(Between(after="it is managed by"))
        with pytest.raises(PageParseFail):
            filter_manco(manco_blocks("Notes to the financial statements"), [])

    def test_blocks_of_other_types_are_ignored(self):
        """Il `text_filter` riceve i blocchi di **tutti** i tubi della sua pipeline."""
        filter_manco = manco.text_filter(Between())
        blocks = filter_manco(
            [PdfBlock("FUND_NAME", {}, "Acme Growth Fund"), *manco_blocks("Acme AM S.A.")],
            [],
        )
        assert blocks[0].content == "Acme AM S.A."


def test_the_date_helper_is_the_engine_s(recorder):
    """`U6` ordina delle date, e le date le converte il motore: qui non se ne riscrive una."""
    assert reading_module._when("(since July 1, 2021)") == (
        "since",
        datetime.date(2021, 7, 1),
    )
