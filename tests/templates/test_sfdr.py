"""`R30`: l'annesso è un documento a sé, e il suo articolo vale solo se il fondo coincide.

Non esiste nessun file dell'annesso di MEDIOLANUM-ES24.B — né fra i documenti di prova né fra i 905
della raccolta — quindi la ricetta `SF-7bis` non si può congelare su una pagina. Quello che **si
può** provare è il meccanismo, con i blocchi costruiti a mano: è lo stesso tubo del motore che gira
in produzione, `TextFilterSfdrSignStandard`, avvolto dal filtro del template, e i due esiti che il
piano chiede sono i due che si leggono qui — il fondo coincide, la riga si scrive; il fondo non
coincide, la riga non si scrive e l'avviso lo dice.
"""

import pytest

from freeports.core import PdfBlock, Promise
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.interfaces.text_blks import ResultStandardFiltering
from freeports.output import Equity, Fund, FundAssets
from freeports.consts import Currency
from freeports.standard_funcs.text_filter import TextFilterSfdrSignStandard

import sfdr
from sfdr import declared as declared_module

#: Come la copertina del documento principale scrive il comparto.
FUND = "MEDIOLANUM ACTIVO S.A. SICAV"


class Recorder:
    """Un registro finto, per leggere ciò che il modulo dice mentre lavora."""

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
    recorder = Recorder()
    monkeypatch.setattr(declared_module, "log", recorder)
    return recorder


def sign_blocks(name, answer="negative"):
    """I blocchi che il `pdf_extract` dell'annesso porta al filtro: il segno e il nome del prodotto."""
    return [
        PdfBlock(ResultStandardExtraction.SFDR_ARTICLE.name, {"answer": answer}, ""),
        PdfBlock(sfdr.PRODUCT_BLOCK, {}, name),
    ]


def equity(fund):
    return Equity(
        company="Apple Inc",
        company_match="Apple Inc",
        fund=fund,
        market_value=100.0,
        currency=Currency.EUR,
    )


@pytest.fixture
def annex_filter():
    """Il `text_filter` dell'annesso, com'è costruito dalla pipeline del formato."""
    return sfdr.only_declared_funds(
        TextFilterSfdrSignStandard([], demand_investment_funds_match=False)
    )


class TestDeclaredFunds:
    """Che cosa conta come «fondo già dichiarato da questo job»."""

    def test_a_fund_declared_by_a_page_counts(self):
        assert sfdr.declared_funds([Fund(name=FUND)])

    def test_the_comparison_is_the_engine_s_own_identity(self):
        declared = sfdr.declared_funds([Fund(name="Mediolanum  Activo, S.A. SICAV")])
        assert sfdr.declared_funds([Fund(name="MEDIOLANUM ACTIVO SA SICAV")]) == declared

    def test_an_investment_names_its_fund_too(self):
        assert sfdr.declared_funds([equity(FUND)]) == sfdr.declared_funds([Fund(name=FUND)])

    def test_any_result_carrying_a_written_fund_counts(self):
        assets = FundAssets(
            fund=FUND, tot_assets=3.0, liabilities=1.0, net_assets=2.0, currency=Currency.EUR
        )
        assert sfdr.declared_funds([assets]) == sfdr.declared_funds([Fund(name=FUND)])

    def test_a_promised_name_is_not_a_name(self):
        assert sfdr.declared_funds([Fund(name=Promise("title document"))]) == set()

    def test_a_promise_deposit_is_not_a_declaration(self):
        assert sfdr.declared_funds([{"title document": FUND}]) == set()

    def test_nothing_extracted_yet_declares_nothing(self):
        assert sfdr.declared_funds([]) == set()


class TestTheAnnexOfTheSameReport:
    """Il fondo coincide: la riga si scrive."""

    def test_the_article_is_read(self, annex_filter, recorder):
        blocks = annex_filter(sign_blocks(FUND), [Fund(name=FUND)])
        assert [block.type_block for block in blocks] == [
            ResultStandardFiltering.SFDR_ARTICLE.name
        ]
        assert blocks[0].content == FUND
        assert not recorder.warnings and not recorder.errors

    def test_the_article_read_is_the_one_the_tick_says(self, annex_filter):
        article = annex_filter(sign_blocks(FUND, "affirmative"), [Fund(name=FUND)])[0].metadata[
            "article"
        ]
        negative = annex_filter(sign_blocks(FUND, "negative"), [Fund(name=FUND)])[0].metadata[
            "article"
        ]
        assert article != negative

    def test_the_two_spellings_of_one_fund_still_coincide(self, annex_filter):
        blocks = annex_filter(sign_blocks("Mediolanum Activo, S.A. SICAV"), [Fund(name=FUND)])
        assert len(blocks) == 1

    def test_the_fund_may_be_declared_by_an_investment(self, annex_filter):
        assert len(annex_filter(sign_blocks(FUND), [equity(FUND)])) == 1


class TestTheAnnexOfAnotherFund:
    """Il fondo non coincide: la riga non si scrive, e si sa perché."""

    def test_the_article_is_dropped(self, annex_filter, recorder):
        assert annex_filter(sign_blocks("MEDIOLANUM PREMIER"), [Fund(name=FUND)]) == []
        assert len(recorder.warnings) == 1
        assert "MEDIOLANUM PREMIER" in recorder.warnings[0]

    def test_the_warning_names_both_readings(self, annex_filter, recorder):
        annex_filter(sign_blocks("MEDIOLANUM PREMIER"), [Fund(name=FUND)])
        assert "written differently" in recorder.warnings[0]

    def test_the_other_funds_of_the_job_do_not_rescue_it(self, annex_filter):
        data = [Fund(name=FUND), equity(FUND), Fund(name="MEDIOLANUM BASE")]
        assert len(annex_filter(sign_blocks("MEDIOLANUM PREMIER"), data)) == 0
        assert len(annex_filter(sign_blocks("MEDIOLANUM BASE"), data)) == 1


class TestTheAnnexPassedAlone:
    """Nessun fondo dichiarato: è un errore d'uso, e va detto."""

    def test_nothing_is_written(self, annex_filter, recorder):
        assert annex_filter(sign_blocks(FUND), []) == []
        assert len(recorder.errors) == 1
        assert "same job" in recorder.errors[0]

    def test_a_promised_name_is_not_enough(self, annex_filter, recorder):
        assert annex_filter(sign_blocks(FUND), [Fund(name=Promise("title document"))]) == []
        assert len(recorder.errors) == 1


class TestWhatTheWrapperDoesNotTouch:
    """Il filtro avvolto decide chi passa, non che cosa dice."""

    def test_a_page_with_no_tick_stays_empty(self, annex_filter, recorder):
        blocks = annex_filter([PdfBlock(sfdr.PRODUCT_BLOCK, {}, FUND)], [Fund(name=FUND)])
        assert blocks == []
        assert not recorder.errors and not recorder.warnings

    def test_the_wrapper_is_off_by_default(self):
        (pipe,) = sfdr.SPANISH.pipeline().text_filter
        assert pipe.name == "TextFilterSfdrSignStandard"

    def test_the_wrapper_is_on_only_when_asked(self):
        (pipe,) = sfdr.SPANISH.pipeline(demand_declared_fund=True).text_filter
        assert pipe.__name__ == "text_filter"
