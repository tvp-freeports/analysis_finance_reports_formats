"""Il nome del comparto ripulito di ciò che non ne fa parte.

I nomi di questi test sono misurati: `Amundi Emerging Markets Bond FAM Fund (continued)` è la riga
di pagina 538 di FINECO-EN23@IR letta con `inspect-page --mode lines`, e
`Kairos International Sicav - Bond (2023: 4.21%)` è la forma che KAIROS-EN23 scriveva a mano prima
che questo pezzo esistesse.

Quello che questi test difendono non è la pulizia in sé ma il suo **ambito**: un nome ripulito nel
blocco `FUND` e lasciato sporco nei metadati dei titoli è peggio che non ripulire niente, perché i
titoli restano appesi a un fondo che in `funds.csv` non c'è più.
"""

import re

from freeports.core import PdfBlock, TextBlock
from freeports.interfaces.text_blks import ResultStandardFiltering

import fund_name
from fund_name import cleaned, strip

PARENTHETICAL = re.compile(r"\(.*\)")


def block(type_block, content, **metadata):
    """Un blocco di testo come lo riceve un `text_filter`, col suo blocco PDF sotto."""
    return TextBlock(type_block, metadata, PdfBlock("TABLE_BODY", {}, content))


def pipe(blocks):
    """Un `text_filter` finto che restituisce i blocchi dati, per avvolgerlo."""

    def text_filter(_pdf_blks, _filter_data):
        return list(blocks)

    return text_filter


class TestStrip:
    """La stringa, senza i pezzi che non sono il nome."""

    def test_a_parenthetical_tail_goes_away(self):
        assert (
            strip("Amundi Emerging Markets Bond FAM Fund (continued)", drop=(PARENTHETICAL,))
            == "Amundi Emerging Markets Bond FAM Fund"
        )

    def test_a_note_mark_goes_away(self):
        assert strip("European Long Only*", substrings=("*",)) == "European Long Only"

    def test_both_kinds_apply_in_order(self):
        assert (
            strip(
                "Kairos International Sicav - Bond* (2023: 4.21%)",
                drop=(PARENTHETICAL,),
                substrings=("*",),
            )
            == "Kairos International Sicav - Bond"
        )

    def test_a_parenthesis_inside_the_name_leaves_one_space_not_two(self):
        """Lo spazio si normalizza alla fine: due spazi sono un nome diverso come la parentesi."""
        assert (
            strip("Challenge (ex Mediolanum) North American Equity", drop=(PARENTHETICAL,))
            == "Challenge North American Equity"
        )

    def test_a_clean_name_comes_back_untouched(self):
        assert strip("Fidelity Focus Equity FAM Fund", drop=(PARENTHETICAL,)) == (
            "Fidelity Focus Equity FAM Fund"
        )

    def test_without_parameters_only_the_spacing_is_normalized(self):
        assert strip("  Euro  Bond FAM Fund ") == "Euro Bond FAM Fund"

    def test_a_name_that_is_nothing_but_the_dropped_part_becomes_empty(self):
        """Non è il lavoro di questo pezzo decidere che fare di un nome vuoto: lo dichiara tale."""
        assert strip("(continued)", drop=(PARENTHETICAL,)) == ""


class TestCleaned:
    """Il tubo avvolto: i due posti in cui il nome finisce, ripuliti insieme."""

    def test_the_fund_block_is_cleaned(self):
        fund = block(
            ResultStandardFiltering.FUND.name,
            "Amundi Emerging Markets Bond FAM Fund (continued)",
        )
        out = cleaned(pipe([fund]), drop=(PARENTHETICAL,))(None, None)
        assert out[0].content == "Amundi Emerging Markets Bond FAM Fund"

    def test_the_fund_metadata_of_a_holding_is_cleaned(self):
        holding = block(
            ResultStandardFiltering.EQUITY_TARGET.name,
            "Alphabet Inc-Class A",
            fund="Fidelity Focus Equity FAM Fund (continued)",
        )
        out = cleaned(pipe([holding]), drop=(PARENTHETICAL,))(None, None)
        assert out[0].metadata["fund"] == "Fidelity Focus Equity FAM Fund"

    def test_the_holding_and_its_fund_come_out_under_the_same_name(self):
        """È la ragione per cui questo pezzo esiste: una chiave sola fra le due tabelle."""
        name = "Fidelity Focus Equity FAM Fund (continued)"
        fund = block(ResultStandardFiltering.FUND.name, name)
        holding = block(ResultStandardFiltering.BOND_TARGET.name, "Intesa Sanpaolo", fund=name)
        out = cleaned(pipe([fund, holding]), drop=(PARENTHETICAL,))(None, None)
        assert out[0].content == out[1].metadata["fund"]

    def test_what_is_not_a_name_is_left_alone(self):
        """Il contenuto di un titolo non è un nome di comparto e non si tocca."""
        holding = block(
            ResultStandardFiltering.EQUITY_TARGET.name,
            "Alphabet Inc-Class A (USD)",
            fund="Fidelity Focus Equity FAM Fund",
        )
        out = cleaned(pipe([holding]), drop=(PARENTHETICAL,))(None, None)
        assert out[0].content == "Alphabet Inc-Class A (USD)"

    def test_other_metadata_survive(self):
        holding = block(
            ResultStandardFiltering.EQUITY_TARGET.name,
            "Alphabet Inc-Class A",
            fund="Focus Equity (continued)",
            quantity="128,684",
        )
        out = cleaned(pipe([holding]), drop=(PARENTHETICAL,))(None, None)
        assert out[0].metadata["quantity"] == "128,684"

    def test_a_block_without_a_fund_key_is_not_given_one(self):
        other = block(ResultStandardFiltering.MANAGEMENT_COMPANY.name, "Fineco Asset Management")
        out = cleaned(pipe([other]), drop=(PARENTHETICAL,))(None, None)
        assert "fund" not in out[0].metadata

    def test_an_empty_fund_key_is_left_as_it_is(self):
        """`None` e la stringa vuota non sono un nome da ripulire, e non diventano `''`."""
        holding = block(ResultStandardFiltering.BOND_TARGET.name, "Intesa Sanpaolo", fund=None)
        out = cleaned(pipe([holding]), drop=(PARENTHETICAL,))(None, None)
        assert out[0].metadata["fund"] is None

    def test_the_wrapped_pipe_receives_what_it_was_given(self):
        seen = []

        def text_filter(pdf_blks, filter_data):
            seen.append((pdf_blks, filter_data))
            return []

        cleaned(text_filter, drop=(PARENTHETICAL,))(["blocks"], "filter data")
        assert seen == [(["blocks"], "filter data")]

    def test_without_parameters_the_name_only_loses_its_spacing(self):
        fund = block(ResultStandardFiltering.FUND.name, " Euro  Bond FAM Fund ")
        out = cleaned(pipe([fund]))(None, None)
        assert out[0].content == "Euro Bond FAM Fund"


def test_the_package_exports_what_a_format_imports():
    assert fund_name.__all__ == ["cleaned", "strip"]


