"""I lettori di `inv_managers`: come una pagina lega un gestore ai suoi comparti.

`assignment.py` assegna e non legge; questi sono i lettori che gli costruiscono le coppie, uno per
forma in cui i bilanci scrivono la cosa. Ogni test porta il formato e la pagina da cui viene: le
righe non sono inventate, sono quelle misurate con `inspect-page --mode lines --order x`, accorciate
solo dove l'indirizzo non aggiunge niente.

Le forme misurate sono sei, i lettori tre: `Adjacent` ne copre quattro cambiando due parametri.
"""

import pytest

from freeports.core import PdfBlock

import inv_managers
from inv_managers import (
    Adjacent,
    ConnectorLine,
    Listing,
    Parenthetical,
    Table,
    Take,
    Where,
    assign,
)
from inv_managers import reading as reading_module
from freeports.utils.text_filter import MatchFund


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

    def warn_imposed(self, **_):
        pass


@pytest.fixture
def recorder(monkeypatch):
    """Sostituisce il registro del modulo di lettura per la durata di un test."""
    recorder = Recorder()
    monkeypatch.setattr(reading_module, "log", recorder)
    return recorder


def grouped(*entries, type_block="INV_MAN"):
    """I blocchi di una pagina che porta i gruppi: un'entrata per argomento."""
    return [
        PdfBlock(type_block, {"group": number}, line)
        for number, entry in enumerate(entries)
        for line in entry
    ]


def typed(*pairs):
    """I blocchi di una pagina senza gruppi, dove il tipo separa nome e specificazione."""
    return [PdfBlock(type_block, {}, line) for type_block, line in pairs]


def typed_groups(*entries):
    """I blocchi di una pagina che porta i gruppi **e** distingue i tipi: `(tipo, riga)` a entrata."""
    return [
        PdfBlock(type_block, {"group": number}, line)
        for number, entry in enumerate(entries)
        for type_block, line in entry
    ]


def read(reader, blocks):
    """Le dichiarazioni in una forma comoda da confrontare: nome, comparti ordinati, parzialità."""
    return [
        (
            declaration.name,
            None if declaration.funds is None else sorted(f.name for f in declaration.funds),
            declaration.partial,
        )
        for declaration in reader(blocks)
    ]


class TestNamed:
    """Il blocco è la dichiarazione, e la pagina non dice quali comparti tocchino a chi."""

    def test_the_block_alone_is_a_manager_without_funds(self):
        """ASTERIA-EN23 p3: sotto `Investment Manager and Global Distributor:` c'è un nome solo."""
        blocks = [PdfBlock("INV_MAN", {}, "Asteria Obviam SA")]

        assert read(inv_managers.Named(), blocks) == [("Asteria Obviam SA", None, False)]

    def test_the_note_mark_does_not_stay_in_the_name(self):
        """Un richiamo di nota sul nome del gestore si toglie come su quello di un comparto."""
        blocks = [PdfBlock("INV_MAN", {}, "Asteria Obviam SA*")]

        assert read(inv_managers.Named(), blocks) == [("Asteria Obviam SA", None, False)]

    def test_a_line_that_names_two_becomes_two_declarations(self):
        """`separators` c'è perché una riga sola può nominarne due, e `R22` le vuole distinte."""
        blocks = [PdfBlock("INV_MAN", {}, "Alpha Capital SA and Beta Advisers Ltd")]

        assert read(inv_managers.Named(separators=(" and ",)), blocks) == [
            ("Alpha Capital SA", None, False),
            ("Beta Advisers Ltd", None, False),
        ]

    def test_the_block_it_keeps_is_the_one_the_line_comes_from(self):
        """La riga d'uscita deve sapere da che pagina viene, e il blocco è l'unico a saperlo."""
        block = PdfBlock("INV_MAN", {"page": 3}, "Asteria Obviam SA")

        kept = inv_managers.Named()([block])[0]

        assert kept.block.metadata == {"page": 3}
        assert str(kept.block.content) == "Asteria Obviam SA"


class TestAdjacentBelow:
    """La specificazione sotto il nome — la forma più diffusa, sei formati su sedici."""

    def test_the_parenthesis_under_the_address_gives_the_manager_its_fund(self):
        """MEDIOLANUM-IT24.A p5: nome, indirizzo, comparti fra parentesi."""
        blocks = grouped([
            "Advent Capital Management LLC",
            "888 Seventh Avenue, 31st Floor, New York, NY 10019, Stati Uniti.",
            "(Convertible Strategy Collection)",
        ])

        assert read(Adjacent(Parenthetical()), blocks) == [
            ("Advent Capital Management LLC", ["Convertible Strategy Collection"], False),
        ]

    def test_several_funds_in_one_parenthesis_split_on_the_comma(self):
        """MEDIOLANUM-IT24.A p5, Axiom Investors: due comparti in una parentesi sola."""
        blocks = grouped([
            "Axiom Investors LLC",
            "33 Benedict Place, Greenwich, Connecticut, CT 06830, Stati Uniti.",
            "(Mediolanum Innovative Thematic Opportunities, "
            "Mediolanum Global Equity Style Selection)",
        ])

        assert read(Adjacent(Parenthetical()), blocks) == [
            (
                "Axiom Investors LLC",
                [
                    "Mediolanum Global Equity Style Selection",
                    "Mediolanum Innovative Thematic Opportunities",
                ],
                False,
            ),
        ]

    def test_the_address_is_not_a_manager(self):
        """Di un'entrata si prende **la prima** riga che non è specificazione, non tutte."""
        blocks = grouped([
            "Algebris (UK) Limited",
            "1 St James' Market, St. James's, London, SW1Y 4AH, Regno Unito.",
            "(Financial Income Strategy)",
        ])

        assert [name for name, _, _ in read(Adjacent(Parenthetical()), blocks)] == [
            "Algebris (UK) Limited",
        ]

    def test_an_entry_without_a_specification_is_a_manager_without_funds(self):
        """CARNE-EN23 p4: `ARCA Fondi SGR S.p.A.` non porta comparti, quindi prende il residuo."""
        blocks = grouped(
            ["ARCA Fondi SGR S.p.A.", "Via Disciplini 3", "I-20123 Milan"],
            ["Goldman Sachs Asset Management International Ltd.",
             "(in charge for the USD nominated securities in the",
             "subfund Sidera Funds SICAV – Global High Yield)",
             "Plumtree Court, 25 Shoe Lane"],
        )
        reader = Adjacent(Parenthetical(markers=("subfund",),
                                        partial_markers=("in charge for",)))

        assert read(reader, blocks) == [
            ("ARCA Fondi SGR S.p.A.", None, False),
            ("Goldman Sachs Asset Management International Ltd.",
             ["Sidera Funds SICAV – Global High Yield"], True),
        ]

    def test_a_parenthesis_never_closed_is_read_to_the_end_of_its_entry(self, recorder):
        """MEDIOLANUM-IT24.A p5: `(Mediolanum Global Impact` non ha la parentesi chiusa.

        È la ragione per cui un confine di gruppo chiude una specificazione rimasta aperta: senza,
        l'assegnazione di Blackrock si perderebbe, e si perderebbe **in silenzio**.
        """
        blocks = grouped(
            ["Blackrock Investment Management (UK) Limited",
             "12 Throgmorton Avenue, London EC2N 2DL, Regno Unito.",
             "(Mediolanum Global Impact"],
            ["Brigade Capital Management, LP",
             "399 Park Avenue, Suite 1600, New York, NY 10022, Stati Uniti.",
             "(Global High Yield)"],
        )

        assert read(Adjacent(Parenthetical()), blocks) == [
            ("Blackrock Investment Management (UK) Limited", ["Mediolanum Global Impact"], False),
            ("Brigade Capital Management, LP", ["Global High Yield"], False),
        ]
        assert any("never closed" in message for message in recorder.debugs)

    def test_without_groups_every_block_is_an_entry_and_the_type_tells_them_apart(self):
        """EURIZON-EN23 p9: nome in frutiger-black, specificazione in frutiger-lightitalic.

        Quando il `pdf_extract` ha già separato per tipo, i gruppi non servono: ogni blocco di
        testo è un nome, e i blocchi di specificazione si attaccano a quello che li precede.
        """
        blocks = typed(
            ("INV", "Eurizon Capital SGR S.p.A."),
            ("SUB", "(this function has been delegated by Eurizon Capital S.A. to Eurizon Capital"),
            ("SUB", "SGR S.p.A. for the Sub-Funds Eurizon Fund - Bond Inflation Linked and Eurizon"),
            ("SUB", "Fund - Global Bond)"),
            ("INV", "Eurizon SLJ Capital LTD"),
            ("SUB", "(this function has been delegated by Eurizon Capital S.A. to Eurizon SLJ"),
            ("SUB", "Capital LTD for the Sub-Funds Eurizon Fund - Bond Flexible)"),
        )
        reader = Adjacent(Parenthetical(markers=("for the Sub-Funds",), block_type="SUB"))

        assert read(reader, blocks) == [
            ("Eurizon Capital SGR S.p.A.",
             ["Eurizon Fund - Bond Inflation Linked", "Eurizon Fund - Global Bond"], False),
            ("Eurizon SLJ Capital LTD", ["Eurizon Fund - Bond Flexible"], False),
        ]

    def test_a_specification_before_any_name_is_reported_and_dropped(self, recorder):
        """Una sezione che si apre con una specificazione non ha a chi attaccarla."""
        blocks = typed(("SUB", "(for the Sub-Funds Alpha Fund)"))
        reader = Adjacent(Parenthetical(markers=("for the Sub-Funds",), block_type="SUB"))

        assert reader(blocks) == []
        assert any("before any manager" in message for message in recorder.debugs)


class TestAdjacentAbove:
    """La specificazione sopra il nome, e lo scopo che apre."""

    def test_one_specification_covers_every_company_that_follows(self):
        """FINECO-EN23@LUX p6: sotto `(Only in respect of …)` stanno **tre** società MFS."""
        blocks = grouped(
            ["(Only in respect of the Sub-Fund MFS Prudent", "Capital FAM Fund)"],
            ["MFS Investment Management Company (Lux) S.à r.l.", "4, Rue Albert Borschette"],
            ["MFS International (U.K.) Limited", "One Carter Lane"],
            ["MFS Institutional Advisors Inc.", "111 Huntington Avenue"],
        )
        reader = Adjacent(
            Parenthetical(markers=("Only in respect of the Sub-Fund", "Only in respect of")),
            where=Where.ABOVE,
        )

        assert read(reader, blocks) == [
            ("MFS Investment Management Company (Lux) S.à r.l.", ["MFS Prudent Capital FAM Fund"],
             False),
            ("MFS International (U.K.) Limited", ["MFS Prudent Capital FAM Fund"], False),
            ("MFS Institutional Advisors Inc.", ["MFS Prudent Capital FAM Fund"], False),
        ]

    def test_the_next_specification_opens_a_new_scope(self):
        """FINECO-EN23@LUX p6: la specificazione dopo chiude quella prima."""
        blocks = grouped(
            ["(Only in respect of the Sub-Fund Global Macro", "Credit FAM Fund)"],
            ["Algebris (UK) Limited", "4th Floor, 1 St James's Market"],
            ["(Only in respect of Bond 6M Fineco AM Fund,",
             "Enhanced Bond 6M Fineco AM Fund and",
             "Sustainable Enhanced Bond 12M Fineco AM Fund)"],
            ["BNP Paribas Asset Management France", "1 Boulevard Haussmann"],
        )
        reader = Adjacent(
            Parenthetical(markers=("Only in respect of the Sub-Fund", "Only in respect of")),
            where=Where.ABOVE,
        )

        assert read(reader, blocks) == [
            ("Algebris (UK) Limited", ["Global Macro Credit FAM Fund"], False),
            ("BNP Paribas Asset Management France",
             ["Bond 6M Fineco AM Fund", "Enhanced Bond 6M Fineco AM Fund",
              "Sustainable Enhanced Bond 12M Fineco AM Fund"], False),
        ]

    def test_take_first_stops_at_the_prose_that_follows_the_name(self):
        """UBS-EN23 p5: dopo il gestore c'è un paragrafo nello stesso carattere del nome.

        È la sola differenza fra questa pagina e FINECO-EN23@LUX, e sta in un parametro: là ogni
        entrata dopo la specificazione è una società, qui solo la prima.
        """
        blocks = typed_groups(
            [("SUB", "BPER International SICAV"), ("SUB", "– Global Balanced Risk Control")],
            [("INV", "Morgan Stanley Investment Management Limited")],
            [("INV", "The Management Company delegated to Morgan"),
             ("INV", "Stanley Investment Management Limited the day"),
             ("INV", "to day portfolio management of BPER International"),
             ("INV", "SICAV – Global Balanced Risk Control.")],
        )
        reader = Adjacent(Listing(block_type="SUB", item_prefix="–"),
                          where=Where.ABOVE, take=Take.FIRST)

        assert read(reader, blocks) == [
            ("Morgan Stanley Investment Management Limited",
             ["BPER International SICAV Global Balanced Risk Control"], False),
        ]

    def test_a_listing_inside_a_named_entry_still_gives_its_manager(self):
        """UBS-EN23 p4, colonna di destra: ombrello, elenco e gestore in **un solo** paragrafo.

        La riga dell'ombrello non apre nessun elenco — non porta il trattino — quindi consuma il
        posto del nome; se la specificazione che si chiude non lo riaprisse, `UBS Asset Management
        Switzerland AG` non uscirebbe affatto. Lo scopo lo apre la specificazione, non lo stacco.
        """
        blocks = grouped([
            "BPER International SICAV",
            "– Emerging Markets - Multi Asset Dividend",
            "– Equity North America",
            "UBS Asset Management Switzerland AG",
        ])
        reader = Adjacent(Listing(umbrella="BPER International SICAV"),
                          where=Where.ABOVE, take=Take.FIRST)

        assert read(reader, blocks) == [
            ("UBS Asset Management Switzerland AG",
             ["BPER International SICAV Emerging Markets - Multi Asset Dividend",
              "BPER International SICAV Equity North America"], False),
        ]

    def test_the_city_inside_the_company_name_is_stripped(self):
        """UBS-EN23 p4: `Banca Cesare Ponti, Milano, Italy` è la sede dentro la ragione sociale.

        L'anagrafica vuole `Banca Cesare Ponti`, e questo formato lo dichiara togliendo tutto ciò
        che segue la prima virgola. È un parametro del formato: la stessa espressione su
        FIDEURAM-EN23 mutilerebbe `Vontobel Asset Management S.A., Milan Branch`.
        """
        blocks = grouped([
            "BPER International SICAV",
            "– Open Selection Defence",
            "Banca Cesare Ponti, Milano, Italy",
        ])
        reader = Adjacent(Listing(umbrella="BPER International SICAV"),
                          where=Where.ABOVE, take=Take.FIRST, strip=(r",.*$",))

        assert read(reader, blocks) == [
            ("Banca Cesare Ponti", ["BPER International SICAV Open Selection Defence"], False),
        ]

    def test_the_block_that_travels_to_the_output_carries_the_stripped_name(self):
        """Il nome della riga d'uscita è il **contenuto del blocco**, non il testo letto."""
        blocks = grouped([
            "BPER International SICAV",
            "– Open Selection Defence",
            "Banca Cesare Ponti, Milano, Italy",
        ])
        reader = Adjacent(Listing(umbrella="BPER International SICAV"),
                          where=Where.ABOVE, take=Take.FIRST, strip=(r",.*$",))

        declaration = reader(blocks)[0]
        assert str(declaration.block.content) == "Banca Cesare Ponti"
        assert declaration.block.metadata == {"group": 0}

    def test_without_strip_the_name_stays_as_the_page_writes_it(self):
        """Il difetto è che il parametro non c'è: senza, la città resta nel nome."""
        blocks = grouped([
            "BPER International SICAV",
            "– Open Selection Defence",
            "Banca Cesare Ponti, Milano, Italy",
        ])
        reader = Adjacent(Listing(umbrella="BPER International SICAV"),
                          where=Where.ABOVE, take=Take.FIRST)

        assert read(reader, blocks)[0][0] == "Banca Cesare Ponti, Milano, Italy"

    def test_a_name_before_any_specification_is_reported_and_dropped(self, recorder):
        """UBS-EN23 p5 comincia con la coda della prosa della pagina prima."""
        blocks = typed_groups(
            [("INV", "The portfolio management units of UBS Asset")],
            [("SUB", "BPER International SICAV"), ("SUB", "– Global Balanced Risk Control")],
            [("INV", "Morgan Stanley Investment Management Limited")],
        )
        reader = Adjacent(Listing(block_type="SUB", item_prefix="–"),
                          where=Where.ABOVE, take=Take.FIRST)

        assert [name for name, _, _ in read(reader, blocks)] == [
            "Morgan Stanley Investment Management Limited",
        ]
        assert any("before any specification" in message for message in recorder.debugs)


class TestTheSpecification:
    """Che cosa una frase fra parentesi dice, e che cosa non dice."""

    def test_the_markers_are_tried_in_order_so_the_longest_goes_first(self):
        """FINECO-EN23@LUX p6 scrive le due forme sulla stessa pagina.

        Cercare `Only in respect of` per primo lascerebbe `the Sub-Fund Invesco …` come nome di
        comparto, che nessun fondo del job riconosce: la riga sparirebbe senza dirlo.
        """
        spec = Parenthetical(markers=("Only in respect of the Sub-Fund", "Only in respect of"))

        assert spec.read(["(Only in respect of the Sub-Fund Invesco Pan",
                          "European High Income FAM Fund)"]) == (
            ("Invesco Pan European High Income FAM Fund",), False,
        )

    def test_a_specification_that_names_no_fund_leaves_the_manager_on_the_residual(self, recorder):
        """EURIZON-EN23 p9, prima voce: la parentesi dice *da quando*, non *che cosa*.

        `(the Sub-Funds … are managed by Eurizon Capital S.A. as from 10 May 2023)` non contiene il
        marcatore, quindi non è un'assegnazione: Eurizon Capital S.A. resta il gestore del residuo,
        che è quello che `R15` chiede e che il formato scritto a mano ottiene per un'altra via.
        """
        spec = Parenthetical(markers=("for the Sub-Funds",))

        funds, partial = spec.read([
            "(the Sub-Funds Eurizon Fund - Equity China A and Eurizon Fund - Asian Equity",
            "Opportunities are managed by Eurizon Capital S.A. as from 10 May 2023)",
        ])

        assert funds is None and partial is False
        assert any("names no sub-fund" in message for message in recorder.debugs)

    def test_a_partial_marker_marks_the_declaration_without_changing_its_funds(self):
        """CARNE-EN23 p4: il gestore entra per una **parte** del comparto (`R21`)."""
        spec = Parenthetical(markers=("subfund",), partial_markers=("in charge for",))

        assert spec.read(["(in charge for the USD nominated securities in the",
                          "subfund Sidera Funds SICAV – Global High Yield)"]) == (
            ("Sidera Funds SICAV – Global High Yield",), True,
        )

    def test_the_note_mark_is_stripped_from_the_fund_name(self):
        """`R16`: la normalizzazione profonda non toglie un asterisco, e il comparto non si trova."""
        assert Parenthetical().read(["(Christian Equity*, European Long Only*)"]) == (
            ("Christian Equity", "European Long Only"), False,
        )

    def test_an_empty_parenthesis_names_nothing(self):
        """Una parentesi vuota non è un comparto senza nome: non è niente."""
        assert Parenthetical().read(["()"]) == ((), False)


class TestListing:
    """L'elenco: un comparto per riga, sotto un ombrello."""

    def test_the_umbrella_line_is_joined_to_every_item(self):
        """UBS-EN23 p5: l'ombrella è in corsivo insieme ai comparti, e si legge da sola."""
        assert Listing(item_prefix="–").read([
            "BPER International SICAV",
            "– Open Selection Defence",
            "– Open Selection Growth",
        ]) == (
            ("BPER International SICAV Open Selection Defence",
             "BPER International SICAV Open Selection Growth"),
            False,
        )

    def test_a_declared_umbrella_replaces_the_line_that_never_arrives(self):
        """UBS-EN23 p4: lì l'ombrella è in tondo, e una selezione sul corsivo la lascia fuori."""
        assert Listing(item_prefix="–", umbrella="BPER International SICAV").read([
            "– Equity North America",
            "– Global Bond",
        ]) == (
            ("BPER International SICAV Equity North America",
             "BPER International SICAV Global Bond"),
            False,
        )

    def test_the_composed_name_is_the_one_the_investments_write(self):
        """`R24`: le due scritture sono lo stesso elemento, ed è ciò che rende la composizione utile."""
        composed, _ = Listing(item_prefix="–", umbrella="BPER International SICAV").read([
            "– Emerging Markets - Multi Asset Dividend",
        ])

        assert inv_managers.fund_set(composed) == inv_managers.fund_set(
            ["BPER INTERNATIONAL SICAV EMERGING MARKETS MULTI ASSET DIVIDEND"]
        )

    def test_an_item_without_an_umbrella_stands_on_its_own(self):
        """Senza ombrella dichiarata né riga che la porti, il comparto è quello che c'è scritto."""
        assert Listing(item_prefix="–").read(["– Optimal Income"]) == (("Optimal Income",), False)


class TestConnectorLine:
    """`<gestore> for <comparti>`: la riga dice tutto."""

    def test_one_manager_and_one_fund(self):
        """FIDEURAM-EN23 p71, prima riga."""
        blocks = [PdfBlock("INV_MAN", {}, "Newton Investment Management Limited for "
                                          "Willerfunds - Private Suite - BNY Mellon Global "
                                          "Real Return,")]

        assert read(ConnectorLine(), blocks) == [
            ("Newton Investment Management Limited",
             ["Willerfunds - Private Suite - BNY Mellon Global Real Return"], False),
        ]

    def test_two_funds_separated_by_and(self):
        """FIDEURAM-EN23 p71: un gestore per due comparti."""
        blocks = [PdfBlock("INV_MAN", {}, "FIL Pensions Management for Willerfunds - Private "
                                          "Suite - Fidelity Flexible Short Duration and "
                                          "Willerfunds - Private Suite - Fidelity USD Bond,")]

        assert read(ConnectorLine(), blocks) == [
            ("FIL Pensions Management",
             ["Willerfunds - Private Suite - Fidelity Flexible Short Duration",
              "Willerfunds - Private Suite - Fidelity USD Bond"], False),
        ]

    def test_two_managers_on_one_line_become_two_declarations(self):
        """FIDEURAM-EN23 p71, ultima riga: due società per lo stesso comparto (`R21`)."""
        blocks = [PdfBlock("INV_MAN", {}, "FIL Investments International and FIL (Luxembourg) "
                                          "S.A. for Willerfunds - Private Suite - Fidelity "
                                          "USD Bond.")]

        assert read(ConnectorLine(), blocks) == [
            ("FIL Investments International",
             ["Willerfunds - Private Suite - Fidelity USD Bond"], False),
            ("FIL (Luxembourg) S.A.",
             ["Willerfunds - Private Suite - Fidelity USD Bond"], False),
        ]

    def test_the_comma_inside_a_manager_name_survives(self):
        """FIDEURAM-EN23 p71: `Vontobel Asset Management S.A., Milan Branch` è **un** gestore.

        È la ragione per cui i due lati si dividono diversamente: a sinistra solo su ` and `, a
        destra anche sulla virgola, perché a destra la virgola separa davvero.
        """
        blocks = [PdfBlock("INV_MAN", {}, "Vontobel Asset Management S.A., Milan Branch for "
                                          "Willerfunds - Private Suite - Vontobel Equity "
                                          "Global Impact,")]

        assert [name for name, _, _ in read(ConnectorLine(), blocks)] == [
            "Vontobel Asset Management S.A., Milan Branch",
        ]

    def test_a_line_without_the_connector_is_reported_and_dropped(self, recorder):
        """La frase che introduce l'elenco finisce nella stessa selezione, e non è un'assegnazione."""
        blocks = [PdfBlock("INV_MAN", {},
                           "The Management Company keeps the control and responsibility.")]

        assert ConnectorLine()(blocks) == []
        assert any("carries no" in message for message in recorder.debugs)

    def test_a_wrapped_line_is_joined_by_its_group(self):
        """Dove la riga va a capo, il gruppo la ricompone prima che il connettore la divida."""
        blocks = grouped(["Pictet Asset Management S.A. for Willerfunds - Private",
                          "Suite - Pictet Health Innovation Trends,"])

        assert read(ConnectorLine(), blocks) == [
            ("Pictet Asset Management S.A.",
             ["Willerfunds - Private Suite - Pictet Health Innovation Trends"], False),
        ]


    def test_the_formula_that_opens_the_sentence_is_not_part_of_the_name(self):
        """UBS-EN23 p4: il gestore sta **dentro** la frase, fra due espressioni fisse."""
        blocks = grouped([
            "The Management Company delegated to Nordea ",
            "Investment Management AB the day to day portfolio ",
            "management of BPER International SICAV – Low ",
            "Duration European Covered Bond. ",
        ])
        reader = ConnectorLine(
            connector=" the day to day portfolio management of ",
            after="The Management Company delegated to ",
        )

        assert read(reader, blocks) == [
            ("Nordea Investment Management AB",
             ["BPER International SICAV – Low Duration European Covered Bond"], False),
        ]

    def test_a_paragraph_without_the_opening_formula_is_dropped(self, recorder):
        """UBS-EN23 p4 alterna una dichiarazione e un paragrafo che spiega: il secondo non dichiara."""
        blocks = grouped([
            "The portfolio management units of Nordea Investment ",
            "Management AB may transfer their mandates, ",
        ])
        reader = ConnectorLine(
            connector=" the day to day portfolio management of ",
            after="The Management Company delegated to ",
        )

        assert read(reader, blocks) == []
        assert recorder.debugs

    def test_the_block_it_keeps_carries_the_name_alone(self):
        """La riga d'uscita sa da che pagina viene, e si chiama col nome del gestore.

        `blocks.text_blocks` prende il nome dal **contenuto del blocco** quando il blocco c'è.
        Tenendo la riga intera, FIDEURAM-EN23 p71 avrebbe scritto in `investments_managers.csv`
        `Newton Investment Management Limited for Willerfunds - Private Suite - BNY Mellon Global
        Real Return,` come ragione sociale.
        """
        blocks = [
            PdfBlock(
                "INV_MAN",
                {"group": 0},
                "Newton Investment Management Limited for Willerfunds - Private Suite - "
                "BNY Mellon Global Real Return,",
            )
        ]
        declared = ConnectorLine()(blocks)
        assert len(declared) == 1
        assert declared[0].block.content == "Newton Investment Management Limited"
        assert declared[0].block.metadata == {"group": 0}


class TestTable:
    """Una riga per comparto, e lo stesso gestore su molte righe."""

    def rows(self, *cells):
        blocks = []
        for number, (fund, date, manager) in enumerate(cells):
            for column, text in ((0, fund), (1, date), (2, manager)):
                if text is not None:
                    blocks.append(
                        PdfBlock("INV_MAN", {"table-row": number, "table-col": column}, text)
                    )
        return blocks

    def test_the_same_manager_on_several_rows_is_one_declaration(self):
        """FINECO-EN23@IR p155: trentacinque comparti, molti meno gestori."""
        blocks = self.rows(
            ("Fidelity Euro Bond FAM Fund", "3 August 2018", "FIL Pensions Management"),
            ("Fidelity Global Dividend FAM Fund", "5 March 2019", "FIL Pensions Management"),
            ("Amundi Strategic Bond FAM Fund", "9 April 2019", "Amundi Ireland Limited"),
        )

        assert read(Table(fund_col=0, manager_col=2), blocks) == [
            ("FIL Pensions Management",
             ["Fidelity Euro Bond FAM Fund", "Fidelity Global Dividend FAM Fund"], False),
            ("Amundi Ireland Limited", ["Amundi Strategic Bond FAM Fund"], False),
        ]

    def test_the_order_is_the_first_appearance_of_each_manager(self):
        """L'ordine della pagina si conserva, perché è quello in cui l'uscita si legge."""
        blocks = self.rows(
            ("Euro Bond FAM Fund", "1 January 2020", "Amundi Ireland Limited"),
            ("Fidelity Euro Bond FAM Fund", "3 August 2018", "FIL Pensions Management"),
            ("Euro High Yield Bond FAM Fund", "2 July 2021", "Amundi Ireland Limited"),
        )

        assert [name for name, _, _ in read(Table(fund_col=0, manager_col=2), blocks)] == [
            "Amundi Ireland Limited",
            "FIL Pensions Management",
        ]

    def test_a_row_missing_one_of_the_two_cells_is_skipped(self):
        """Una colonna vuota non fa una riga sbilenca: la riga non c'è."""
        blocks = self.rows(
            ("Fidelity Euro Bond FAM Fund", "3 August 2018", "FIL Pensions Management"),
            ("Flexible Income FAM Fund", "4 May 2022", None),
        )

        assert read(Table(fund_col=0, manager_col=2), blocks) == [
            ("FIL Pensions Management", ["Fidelity Euro Bond FAM Fund"], False),
        ]

    def test_blocks_without_the_table_metadata_are_ignored(self):
        """Il titolo della tabella arriva nella stessa selezione e non è una cella."""
        blocks = self.rows(
            ("Fidelity Euro Bond FAM Fund", "3 August 2018", "FIL Pensions Management"),
        )
        blocks.insert(0, PdfBlock("INV_MAN", {}, "The following table provides the date of "
                                                 "commencement of trading"))

        assert [name for name, _, _ in read(Table(fund_col=0, manager_col=2), blocks)] == [
            "FIL Pensions Management",
        ]


class TestReadingAndAssigningTogether:
    """I due pezzi attaccati: la pagina letta, e il residuo assegnato."""

    def test_carne_gives_the_residual_to_the_manager_the_page_does_not_qualify(self):
        """CARNE-EN23 p4 per intero, con i comparti che il job ha visto negli investimenti."""
        blocks = grouped(
            ["ARCA Fondi SGR S.p.A.", "Via Disciplini 3", "I-20123 Milan"],
            ["Goldman Sachs Asset Management International Ltd.",
             "(in charge for the USD nominated securities in the",
             "subfund Sidera Funds SICAV – Global High Yield)",
             "Plumtree Court, 25 Shoe Lane"],
        )
        reader = Adjacent(Parenthetical(markers=("subfund",),
                                        partial_markers=("in charge for",)))

        assignment = assign(
            reader(blocks),
            ["Sidera Funds SICAV – Global High Yield", "Sidera Funds SICAV – Equity Global"],
            manco="Carne Global Fund Managers (Luxembourg) S.A.",
        )

        assert [manager.name for manager in assignment.managers] == [
            "ARCA Fondi SGR S.p.A.",
            "Goldman Sachs Asset Management International Ltd.",
        ]
        assert not assignment.to_manco

    def test_the_partial_fund_stays_with_the_default_manager_too(self):
        """`R21`: una parte di comparto non toglie il comparto a chi risponde del resto."""
        blocks = grouped(
            ["ARCA Fondi SGR S.p.A.", "Via Disciplini 3"],
            ["Goldman Sachs Asset Management International Ltd.",
             "(in charge for the USD nominated securities in the",
             "subfund Sidera Funds SICAV – Global High Yield)"],
        )
        reader = Adjacent(Parenthetical(markers=("subfund",),
                                        partial_markers=("in charge for",)))

        assignment = assign(reader(blocks), ["Sidera Funds SICAV – Global High Yield"])
        residual = next(m for m in assignment.managers if m.name == "ARCA Fondi SGR S.p.A.")

        assert sorted(f.name for f in residual.funds) == ["Sidera Funds SICAV – Global High Yield"]

    def test_the_manager_read_from_a_block_keeps_the_page_it_comes_from(self):
        """Il blocco si conserva fino all'uscita, o la riga perde la pagina da cui è stata letta."""
        blocks = grouped(["Advent Capital Management LLC", "(Convertible Strategy Collection)"])

        declarations = Adjacent(Parenthetical())(blocks)

        assert declarations[0].block is blocks[0]


class TestTheManagerWhoLeftDuringTheYear:
    """EURIZON-EN23 p9→10: si estrae chi è in carica alla chiusura, non la storia dell'esercizio.

    p10 scrive `Eurizon Capital Asia Limited`, sotto `(until 10th of May 2023)`, e piu' sotto la
    parentesi che gli attribuisce `Eurizon Fund - Equity China A` e `Eurizon Fund - Asian Equity
    Opportunities`; p9 dice degli stessi due comparti che *are managed by Eurizon Capital S.A. as
    from 10 May 2023*. La regola è quella della società di gestione, che l'utente ha esteso ai
    gestori il 2026-09-21.
    """

    def entries(self):
        """I blocchi di p10 come il `pdf_extract` li porta: nome, tondo chiaro, corsivo."""
        return typed(
            ("INV", "Eurizon Capital Asia Limited"),
            ("NOTE", "(until 10th of May 2023)"),
            ("NOTE", "Unit 7507A2, Level 75, International Commerce Centre"),
            ("SUB", "(this function has been delegated by Eurizon Capital S.A. to Eurizon"),
            ("SUB", "Capital Asia Limited for the Sub-Funds Eurizon Fund - Equity China A and"),
            ("SUB", "Eurizon Fund - Asian Equity Opportunities)"),
            ("INV", "Jennison Associates LLC"),
            ("NOTE", "466 Lexington Avenue"),
            ("SUB", "(this function has been delegated by Eurizon Capital S.A. to Jennison"),
            ("SUB", "Associates LLC for the Sub-Fund Eurizon Fund - Global Equity Infrastructure)"),
        )

    def reader(self, **overrides):
        """Il lettore del formato, con i parametri che la pagina chiede."""
        options = dict(
            where=Where.BELOW,
            note_type="NOTE",
            retired=(r"^\(until\b",),
        )
        options.update(overrides)
        return Adjacent(
            Parenthetical(block_type="SUB",
                          markers=("for the Sub-Funds ", "for the Sub-Fund ")),
            **options
        )

    def test_the_outgoing_manager_is_read_but_marked(self):
        """Il lettore non lo butta: `assign` ha ancora bisogno dei comparti che nomina."""
        declarations = self.reader()(self.entries())

        assert [(d.name, d.retired) for d in declarations] == [
            ("Eurizon Capital Asia Limited", True),
            ("Jennison Associates LLC", False),
        ]

    def test_the_address_is_never_taken_for_a_name(self):
        """Senza `note_type` ogni riga di tondo chiaro diventerebbe un gestore: la pagina non ha
        gruppi, quindi ogni blocco è un'entrata a sé."""
        declarations = self.reader(note_type=None)(self.entries())

        assert "466 Lexington Avenue" in [d.name for d in declarations]

    def test_the_outgoing_manager_writes_no_row(self):
        """L'assegnazione: fuori Asia Limited, e i suoi due comparti nel residuo di chi resta."""
        funds = ["Eurizon Fund - Equity China A",
                 "Eurizon Fund - Asian Equity Opportunities",
                 "Eurizon Fund - Global Equity Infrastructure"]
        declarations = list(self.reader()(self.entries()))
        declarations.append(inv_managers.Declared("Eurizon Capital S.A."))

        assignment = assign(declarations, funds)

        assert [(m.name, sorted(f.name for f in m.funds)) for m in assignment.managers] == [
            ("Jennison Associates LLC", ["Eurizon Fund - Global Equity Infrastructure"]),
            ("Eurizon Capital S.A.", ["Eurizon Fund - Asian Equity Opportunities",
                                      "Eurizon Fund - Equity China A"]),
        ]

    def test_the_funds_of_the_outgoing_manager_stay_funds_of_the_document(self):
        """Il comparto che **solo** il gestore uscente nomina non sparisce dall'uscita."""
        funds = ["Eurizon Fund - Asian Equity Opportunities",
                 "Eurizon Fund - Global Equity Infrastructure"]
        declarations = list(self.reader()(self.entries()))
        declarations.append(inv_managers.Declared("Eurizon Capital S.A."))

        assignment = assign(declarations, funds)

        assert sorted(f.name for f in assignment.new_funds) == ["Eurizon Fund - Equity China A"]
        assert MatchFund("Eurizon Fund - Equity China A") in assignment.funds

    def test_a_name_declared_elsewhere_without_the_qualifier_is_still_in_charge(self):
        """`retired` si fonde in `and`: una sola riga qualificata non basta a mandarlo via."""
        declarations = [
            inv_managers.Declared("Alpha Asset Management", funds=["Beta Fund"], retired=True),
            inv_managers.Declared("Alpha Asset Management", funds=["Gamma Fund"]),
        ]

        assignment = assign(declarations, ["Beta Fund", "Gamma Fund"])

        assert [m.name for m in assignment.managers] == ["Alpha Asset Management"]
