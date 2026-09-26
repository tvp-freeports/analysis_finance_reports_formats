"""`U7`: il prospetto letto a etichette, e il valore che attraversa il confine fra due pagine.

I dati dei test vengono da ARCA-IT24 D1 p8→p9, misurate con
`inspect-page --mode lines --order y`: `TOTALE ATTIVITA' 21.970.695` sulla prima,
`TOTALE PASSIVITA' 274.045` e `VALORE COMPLESSIVO NETTO DEL FONDO 21.696.650` sulla seconda —
e l'equazione torna, che è il motivo per cui le due pagine devono parlarsi.
"""

import pytest

from freeports.core import PdfBlock, TextBlock
from freeports.utils.text_filter import MatchFund

import carryover
from carryover import Carryover, Record
from carryover import promise as promise_module
from carryover import page as page_module
from carryover import record as record_module

FUND = "ARCA OPPORTUNITÀ GREEN 2027 VIII"


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

    def warn_imposed(self, **_):
        pass


@pytest.fixture
def recorder(monkeypatch):
    """Sostituisce il registro dei due moduli per la durata di un test."""
    recorder = Recorder()
    monkeypatch.setattr(promise_module, "log", recorder)
    monkeypatch.setattr(record_module, "log", recorder)
    monkeypatch.setattr(page_module, "log", recorder)
    return recorder


def bare(*pairs):
    """I blocchi nudi che gli `A1` di una pagina lasciano: un tipo e un testo."""
    return [PdfBlock(type_block, {}, text) for type_block, text in pairs]


def statement(**metadata):
    """Il blocco del prospetto come il `text_filter` standard degli attivi lo restituisce."""
    return TextBlock.from_content("RELEVANT_BLOCK", metadata, "")


class TestTheRecord:
    """`Record`: i blocchi nudi di più `A1` riuniti in un prospetto solo."""

    def test_each_block_type_fills_its_own_key(self):
        record = Record(fund="FUND_NAME", tot_assets="TOT_ASSETS")
        blocks = record(bare(("FUND_NAME", FUND), ("TOT_ASSETS", "21.970.695")))
        assert len(blocks) == 1
        assert blocks[0].metadata == {"fund": FUND, "tot_assets": "21.970.695"}

    def test_the_block_that_comes_out_is_of_the_declared_type(self):
        record = Record(block_type="STATEMENT", fund="FUND_NAME")
        blocks = record(bare(("FUND_NAME", FUND)))
        assert blocks[0].type_block == "STATEMENT"

    def test_by_default_the_block_is_the_one_the_standard_filters_expect(self):
        blocks = Record(fund="FUND_NAME")(bare(("FUND_NAME", FUND)))
        assert blocks[0].type_block == carryover.RELEVANT_BLOCK

    def test_blocks_of_no_declared_type_are_left_where_they_are(self):
        record = Record(fund="FUND_NAME")
        blocks = record(bare(("FUND_NAME", FUND), ("PAGE_CLASS", "fund_assets_begin")))
        assert blocks[0].metadata == {"fund": FUND}

    def test_a_missing_block_type_says_so_and_leaves_the_key_out(self, recorder):
        record = Record(fund="FUND_NAME", currency="CURRENCY_STATEMENT")
        blocks = record(bare(("FUND_NAME", FUND)))
        assert blocks[0].metadata == {"fund": FUND}
        assert any("currency" in message for message in recorder.warnings)

    def test_two_blocks_of_one_type_take_the_first_and_say_so(self, recorder):
        record = Record(net_assets="NET_ASSETS")
        blocks = record(bare(("NET_ASSETS", "21.696.650"), ("NET_ASSETS", "1.702.020")))
        assert blocks[0].metadata == {"net_assets": "21.696.650"}
        assert any("one statement" in message for message in recorder.warnings)

    def test_a_page_with_nothing_expected_on_it_yields_no_statement(self, recorder):
        blocks = Record(fund="FUND_NAME")(bare(("SOMETHING_ELSE", "x")))
        assert blocks == []
        assert recorder.warnings

    def test_a_record_with_no_field_is_refused_when_it_is_built(self):
        with pytest.raises(ValueError):
            Record()

    def test_the_repr_names_the_fields(self):
        assert "tot_assets" in repr(Record(tot_assets="TOT_ASSETS"))


class TestTheDeposit:
    """`deposit`: la promessa che la prima delle due pagine lascia."""

    def test_the_identifier_joins_the_field_and_the_fund(self):
        carry = Carryover("tot_assets")
        assert carry.promise_id("tot_assets", FUND) == "tot_assets@" + FUND

    def test_the_separator_is_a_parameter(self):
        carry = Carryover("tot_assets", separator="::")
        assert carry.promise_id("tot_assets", FUND) == "tot_assets::" + FUND

    def test_one_entry_per_carried_field(self):
        carry = Carryover("tot_assets", "currency")
        entries = carry.deposit(
            statement(fund=FUND, tot_assets="21.970.695", currency="EUR", extra="ignored")
        )
        assert entries == {
            "tot_assets@" + FUND: "21.970.695",
            "currency@" + FUND: "EUR",
        }

    def test_a_field_the_page_does_not_carry_is_left_out_with_a_warning(self, recorder):
        carry = Carryover("tot_assets", "liabilities")
        entries = carry.deposit(statement(fund=FUND, tot_assets="21.970.695"))
        assert entries == {"tot_assets@" + FUND: "21.970.695"}
        assert any("liabilities" in message for message in recorder.warnings)

    def test_without_a_fund_there_is_nobody_to_promise_to(self, recorder):
        carry = Carryover("tot_assets")
        assert carry.deposit(statement(tot_assets="21.970.695")) == {}
        assert recorder.errors

    def test_the_fund_key_is_a_parameter(self):
        carry = Carryover("tot_assets", fund_key="comparto")
        entries = carry.deposit(statement(comparto=FUND, tot_assets="21.970.695"))
        assert entries == {"tot_assets@" + FUND: "21.970.695"}

    def test_a_carryover_with_no_field_is_refused_when_it_is_built(self):
        with pytest.raises(ValueError):
            Carryover()

    def test_an_empty_separator_is_refused_when_it_is_built(self):
        with pytest.raises(ValueError):
            Carryover("tot_assets", separator="")


class TestWhatWasPromised:
    """`promised`: ciò che le pagine precedenti di questo job hanno lasciato."""

    def test_a_promise_is_found_by_the_fund_it_names(self):
        carry = Carryover("tot_assets")
        available = carry.promised([{"tot_assets@" + FUND: "21.970.695"}])
        assert available == {MatchFund(FUND): {"tot_assets": "21.970.695"}}

    def test_the_two_pages_may_write_the_name_differently(self):
        """Il confronto è per identità di fondo, non per stringa: `MatchFund` normalizza."""
        carry = Carryover("tot_assets")
        available = carry.promised([{"tot_assets@ARCA  opportunità green 2027 VIII": "1"}])
        assert MatchFund(FUND) in available

    def test_a_fund_name_containing_the_separator_survives(self):
        carry = Carryover("tot_assets")
        available = carry.promised([{"tot_assets@Alpha @ Beta": "1"}])
        assert available == {MatchFund("Alpha @ Beta"): {"tot_assets": "1"}}

    def test_promises_of_another_datum_are_left_alone(self):
        carry = Carryover("tot_assets")
        assert carry.promised([{"esg-fund-page-3": "Whatever"}]) == {}

    def test_results_that_are_not_promises_are_skipped(self):
        carry = Carryover("tot_assets")
        assert carry.promised(["not a promise", 17, None]) == {}

    def test_several_fields_of_one_fund_gather_under_one_key(self):
        carry = Carryover("tot_assets", "liabilities")
        available = carry.promised(
            [{"tot_assets@" + FUND: "21.970.695"}, {"liabilities@" + FUND: "274.045"}]
        )
        assert available == {
            MatchFund(FUND): {"tot_assets": "21.970.695", "liabilities": "274.045"}
        }


class TestResuming:
    """`resume`: il valore della pagina prima entra nei metadati della pagina dopo."""

    def test_the_carried_value_joins_the_metadata_of_its_own_fund(self):
        carry = Carryover("tot_assets")
        blocks = carry.resume(
            [statement(fund=FUND, liabilities="274.045", net_assets="21.696.650")],
            [{"tot_assets@" + FUND: "21.970.695"}],
        )
        assert len(blocks) == 1
        assert blocks[0].metadata == {
            "fund": FUND,
            "liabilities": "274.045",
            "net_assets": "21.696.650",
            "tot_assets": "21.970.695",
        }

    def test_the_equation_of_the_two_pages_adds_up(self):
        """Non è un test del codice: è la misura che dice che le due pagine sono la stessa riga."""
        carry = Carryover("tot_assets")
        blocks = carry.resume(
            [statement(fund=FUND, liabilities="274.045", net_assets="21.696.650")],
            [{"tot_assets@" + FUND: "21.970.695"}],
        )
        numbers = {
            key: int(blocks[0].metadata[key].replace(".", ""))
            for key in ("tot_assets", "liabilities", "net_assets")
        }
        assert numbers["tot_assets"] - numbers["liabilities"] == numbers["net_assets"]

    def test_the_type_and_the_content_of_the_block_are_kept(self):
        carry = Carryover("tot_assets")
        block = TextBlock.from_content("STATEMENT", {"fund": FUND}, "some content")
        resumed = carry.resume([block], [{"tot_assets@" + FUND: "1"}])[0]
        assert resumed.type_block == "STATEMENT"
        assert resumed.content == "some content"

    def test_each_fund_gets_its_own_and_nobody_else_s(self):
        carry = Carryover("tot_assets")
        blocks = carry.resume(
            [statement(fund="Alpha"), statement(fund="Beta")],
            [{"tot_assets@Alpha": "10", "tot_assets@Beta": "20"}],
        )
        assert [block.metadata["tot_assets"] for block in blocks] == ["10", "20"]

    def test_a_statement_whose_other_page_never_arrived_is_dropped_loudly(self, recorder):
        carry = Carryover("tot_assets")
        assert carry.resume([statement(fund=FUND)], []) == []
        assert any(FUND in message for message in recorder.errors)

    def test_a_half_kept_promise_is_as_bad_as_none(self, recorder):
        """Un campo su due non costruisce la riga: `FundAssets` li vuole tutt'e tre insieme."""
        carry = Carryover("tot_assets", "liabilities")
        assert carry.resume([statement(fund=FUND)], [{"tot_assets@" + FUND: "1"}]) == []
        assert any("liabilities" in message for message in recorder.errors)

    def test_a_block_with_no_fund_cannot_be_paired(self, recorder):
        carry = Carryover("tot_assets")
        assert carry.resume([statement(liabilities="274.045")], [{"tot_assets@" + FUND: "1"}]) == []
        assert recorder.errors

    def test_what_was_already_in_the_metadata_is_not_lost(self):
        carry = Carryover("tot_assets")
        resumed = carry.resume(
            [statement(fund=FUND, currency="EUR", date="30/12/2024")],
            [{"tot_assets@" + FUND: "21.970.695"}],
        )[0]
        assert resumed.metadata["currency"] == "EUR"
        assert resumed.metadata["date"] == "30/12/2024"

    def test_the_repr_names_the_fields(self):
        assert "tot_assets" in repr(Carryover("tot_assets"))


class TestTheTwoPagesTogether:
    """Le due metà, una dietro l'altra, come le due pipeline le mettono."""

    def test_what_the_first_page_deposits_is_what_the_second_finds(self):
        carry = Carryover("tot_assets")
        record_begin = Record(fund="FUND_NAME", tot_assets="TOT_ASSETS")
        record_end = Record(fund="FUND_NAME", liabilities="LIABILITIES", net_assets="NET_ASSETS")

        first = record_begin(bare(("FUND_NAME", FUND), ("TOT_ASSETS", "21.970.695")))
        deposited = carry.deposit(statement(**first[0].metadata))

        second = record_end(
            bare(
                ("FUND_NAME", FUND),
                ("LIABILITIES", "274.045"),
                ("NET_ASSETS", "21.696.650"),
            )
        )
        resumed = carry.resume([statement(**second[0].metadata)], [deposited])

        assert resumed[0].metadata == {
            "fund": FUND,
            "liabilities": "274.045",
            "net_assets": "21.696.650",
            "tot_assets": "21.970.695",
        }

    def test_a_fund_the_first_page_never_kept_produces_no_row_at_all(self, recorder):
        """Il filtro sui fondi d'interesse sta sulla prima pagina: qui la mancanza è un difetto."""
        carry = Carryover("tot_assets")
        assert carry.resume([statement(fund="Un fondo che non interessa")], [{}]) == []
        assert recorder.errors


class TestTheEquationThatDoesNotAddUp:
    """`FA-10`, `R32`: la riga sbilanciata non si estrae e si dichiara errore.

    La ricetta non ha una pagina che la eserciti. Misurate, **tutte** le coppie del corpus
    tornano: le due di ARCA-IT24 e le nove di MEDIOLANUM-IT24.B, scarto zero. Il caso si prova
    quindi dove nasce davvero — una promessa che non combacia col passivo della pagina dopo — e
    quello che dimostra e' la ragione per cui la Strada 1 e' stata scelta: l'errore esce **dentro**
    la pipeline, dove il documento e la pagina si sanno ancora.
    """

    def test_the_deserializer_refuses_a_pair_that_does_not_balance(self):
        from freeports.consts import Currency
        from freeports.standard_funcs.deserialize import DeserializerAssetsStandard
        from freeports.utils.deserialize import to_int

        carry = Carryover("tot_assets")
        blocks = carry.resume(
            [
                statement(
                    fund=FUND,
                    currency=Currency.EUR,
                    liabilities="274.045",
                    net_assets="21.696.650",
                )
            ],
            [{"tot_assets@" + FUND: "99.999.999"}],
        )
        with pytest.raises(Exception) as refused:
            DeserializerAssetsStandard(to_int)(blocks[0])
        assert "99999999" in str(refused.value).replace(".", "")

    def test_the_same_pair_is_accepted_when_it_balances(self):
        from freeports.consts import Currency
        from freeports.standard_funcs.deserialize import DeserializerAssetsStandard
        from freeports.utils.deserialize import to_int

        carry = Carryover("tot_assets")
        blocks = carry.resume(
            [
                statement(
                    fund=FUND,
                    currency=Currency.EUR,
                    liabilities="274.045",
                    net_assets="21.696.650",
                )
            ],
            [{"tot_assets@" + FUND: "21.970.695"}],
        )
        assets = DeserializerAssetsStandard(to_int)(blocks[0])
        assert assets.tot_assets == 21970695.0


class TestWhatTheOtherPageAlreadySaid:
    """`sole_fund` e `also`: la pagina che non nomina il proprio comparto."""

    def test_the_only_fund_of_the_report_is_the_one(self, recorder):
        """Il nome torna come `Fund` lo scrive — normalizzato — che e' come lo scrive `funds.csv`."""
        from freeports.output import Fund

        declared = Fund(name=FUND)
        assert carryover.sole_fund([declared]) == declared.name

    def test_attributing_it_is_an_imposed_value_and_says_so(self, monkeypatch):
        from freeports.output import Fund
        from carryover import document as document_module

        said = []
        monkeypatch.setattr(
            document_module,
            "log",
            type("L", (), {"error": staticmethod(lambda *a, **k: None),
                           "warn_imposed": staticmethod(lambda **k: said.append(k))})(),
        )
        declared = Fund(name=FUND)
        carryover.sole_fund([declared])
        assert said and said[0]["field"] == "fund" and said[0]["value"] == declared.name

    def test_two_funds_are_not_a_choice_to_make(self, monkeypatch):
        from freeports.output import Fund
        from carryover import document as document_module

        recorder = Recorder()
        monkeypatch.setattr(document_module, "log", recorder)
        assert carryover.sole_fund([Fund(name="Alpha"), Fund(name="Beta")]) is None
        assert recorder.errors

    def test_no_fund_at_all_is_an_error_too(self, monkeypatch):
        from carryover import document as document_module

        recorder = Recorder()
        monkeypatch.setattr(document_module, "log", recorder)
        assert carryover.sole_fund([]) is None
        assert recorder.errors

    def test_also_fills_what_the_page_does_not_declare(self):
        record = Record(tot_assets="TOT_ASSETS")
        blocks = record(bare(("TOT_ASSETS", "31.363.698")), also={"fund": FUND})
        assert blocks[0].metadata == {"tot_assets": "31.363.698", "fund": FUND}

    def test_what_the_page_declares_is_not_overwritten_by_what_it_does_not(self):
        record = Record(fund="FUND_NAME")
        blocks = record(bare(("FUND_NAME", FUND)), also={"currency": "EUR"})
        assert blocks[0].metadata == {"fund": FUND, "currency": "EUR"}

    def test_what_the_page_declares_wins_over_what_it_is_told(self):
        record = Record(fund="FUND_NAME")
        blocks = record(bare(("FUND_NAME", FUND)), also={"fund": "Un altro fondo"})
        assert blocks[0].metadata == {"fund": FUND}

    def test_a_field_that_also_supplies_is_not_reported_as_missing(self, recorder):
        record = Record(fund="FUND_NAME", tot_assets="TOT_ASSETS")
        blocks = record(bare(("TOT_ASSETS", "1")), also={"fund": FUND})
        assert blocks[0].metadata == {"fund": FUND, "tot_assets": "1"}
        assert recorder.warnings == []


class TestPageCarryover:
    """Le due pagine legate dal **numero di pagina**, che è la scelta dell'utente del 2026-09-21.

    I dati vengono da FINECO-EN23@IR D1 p893→894: `Product name: Fidelity EURO Bond FAM Fund` in
    testa all'allegato, gli indicatori sulla pagina dopo, e il numero stampato in fondo a tutt'e
    due in `timesnewroman` 10.
    """

    def carry(self, **overrides):
        return carryover.PageCarryover("esg-fund", **overrides)

    def test_the_key_carries_the_page_the_name_was_read_on(self):
        assert self.carry().promise_id(893) == "esg-fund-page-893"

    def test_the_next_page_asks_for_the_page_before_it(self):
        assert self.carry().promise(894).id == "esg-fund-page-893"

    def test_a_format_whose_pages_are_two_apart_says_so(self):
        """UBS-EN23: il titolo del comparto a p14, il prospetto patrimoniale a p16."""
        assert self.carry(offset=2).promise(16).id == "esg-fund-page-14"

    def test_a_field_that_carries_nothing_is_refused(self):
        with pytest.raises(ValueError):
            carryover.PageCarryover("")

    def test_a_page_cannot_leave_anything_to_itself(self):
        with pytest.raises(ValueError):
            carryover.PageCarryover("esg-fund", offset=0)

    def test_the_deposit_is_the_promise_the_next_page_will_find(self):
        block = TextBlock.from_content("REL", {"page": 893}, "Fidelity EURO Bond FAM Fund ")

        assert self.carry().deposit(block) == {
            "esg-fund-page-893": "Fidelity EURO Bond FAM Fund",
        }

    def test_a_block_without_its_page_leaves_nothing_and_says_so(self, recorder):
        block = TextBlock.from_content("REL", {}, "Fidelity EURO Bond FAM Fund")

        assert self.carry().deposit(block) == {}
        assert any("cannot leave anything" in message for message in recorder.errors)

    def test_the_owner_of_a_page_is_the_promise_of_the_page_before(self):
        blocks = [PdfBlock("REL", {"page": 894}, "")]

        owner = self.carry().owner()(blocks, [])

        assert owner.id == "esg-fund-page-893"

    def test_a_page_without_a_number_owns_nothing_and_says_so(self, recorder):
        owner = self.carry().owner()([PdfBlock("REL", {}, "")], [])

        assert owner is None
        assert any("cannot be tied to a fund" in message for message in recorder.errors)


class TestPageCarryoverNearest:
    """La seconda forma: il titolo più vicino che precede, cercato nel `text_filter`.

    I dati vengono da UBS-EN23, dove fra il titolo di un comparto e il suo prospetto patrimoniale
    ci stanno una, due, tre o quattro pagine — i numeri stampati misurati sul documento sono i
    titoli 12, 18, 22, 27 e i prospetti 14, 19, 24, 30.
    """

    def carry(self):
        return carryover.PageCarryover("ubs-fund")

    def left(self):
        return [
            {"ubs-fund-page-12": "BPER International SICAV – Emerging Markets"},
            {"ubs-fund-page-18": "BPER International SICAV – Equity North America"},
            {"ubs-fund-page-22": "BPER International SICAV – Fixed Income Credit Strategies"},
            {"ubs-fund-page-27": "BPER International SICAV – Global Balanced Risk Control"},
        ]

    def test_what_the_pages_before_have_left_is_read_by_page(self):
        assert sorted(self.carry().deposited(self.left())) == [12, 18, 22, 27]

    def test_each_statement_gets_the_title_that_precedes_it(self):
        carry = self.carry()

        assert [carry.nearest(self.left(), page) for page in (14, 19, 24, 30)] == [
            "BPER International SICAV – Emerging Markets",
            "BPER International SICAV – Equity North America",
            "BPER International SICAV – Fixed Income Credit Strategies",
            "BPER International SICAV – Global Balanced Risk Control",
        ]

    def test_a_page_before_the_first_title_owns_nothing_and_says_so(self, recorder):
        """UBS-EN23 p9 e p12 portano prospetti **combinati**, prima di ogni titolo di comparto."""
        assert self.carry().nearest(self.left(), 7) is None
        assert any("no 'ubs-fund' was left" in message for message in recorder.errors)

    def test_the_keys_of_another_carryover_of_the_same_run_are_left_alone(self):
        left = self.left() + [{"esg-fund-page-893": "Fidelity EURO Bond FAM Fund"}]

        assert sorted(self.carry().deposited(left)) == [12, 18, 22, 27]

    def test_what_is_not_a_promise_is_not_read(self):
        """`filter_data` porta anche i risultati delle pagine prima, che non sono dizionari."""
        assert self.carry().deposited(["not a promise", 42, None]) == {}
