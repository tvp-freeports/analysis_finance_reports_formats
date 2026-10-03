"""I sette rami di `A5`, l'assegnatore dei gestori — un test per regola.

`A5` non legge nessuna pagina: riceve le coppie *nome → fondi* che il `text_filter` ha già letto e
decide di chi è il residuo. Le sette righe di `R6`+`R15`+`R21`+`R22` sono quindi sette casi di una
funzione pura, ed è la parte del piano che le revisioni hanno già cambiato tre volte — `R15` ha
corretto `R6`, `R21` e `R22` hanno corretto `R15`. È il pezzo che più di ogni altro ha bisogno di
test che dicano *che cosa deve fare*.

Ogni caso viene da una pagina misurata, con il formato e la pagina scritti accanto: i nomi non sono
inventati, sono quelli che l'assegnatore incontrerà davvero.
"""

import pytest

import inv_managers
from inv_managers import Declared, assign, assigned_funds, fund_set
from inv_managers import assignment as assign_module


class Recorder:
    """Un registro finto, per leggere gli avvisi che l'assegnazione emette.

    In una corsa vera questi eventi vanno dove vanno tutti gli altri — `.log.csv` per `warn` ed
    `error`, il log strutturato per il `debug` — e il test d'integrazione li legge da lì. Qui serve
    solo sapere *che* sono stati emessi, e con quale contenuto.
    """

    def __init__(self):
        self.warnings = []
        self.errors = []
        self.debugs = []
        self.imposed = []

    def warn(self, message, **_):
        self.warnings.append(message)

    def error(self, message, **_):
        self.errors.append(message)

    def debug(self, message, **_):
        self.debugs.append(message)

    def warn_imposed(self, *, field, value, reason):
        self.imposed.append((field, value, reason))


@pytest.fixture
def recorder(monkeypatch):
    """Sostituisce il registro del modulo per la durata di un test."""
    recorder = Recorder()
    monkeypatch.setattr(assign_module, "log", recorder)
    return recorder


def names(assignment):
    """I nomi assegnati, nell'ordine in cui escono."""
    return [manager.name for manager in assignment.managers]


def funds_of(assignment, name):
    """I nomi dei fondi assegnati a `name`, ordinati, come si leggeranno nell'uscita."""
    for manager in assignment.managers:
        if manager.name == name:
            return sorted(fund.name for fund in manager.funds)
    raise AssertionError("{!r} is not among {}".format(name, names(assignment)))


class TestTheSevenBranches:
    """Le sette righe della tabella di `R6`+`R15`+`R21`+`R22`, una per test."""

    def test_no_manager_at_all_sends_every_fund_to_the_management_company(self, recorder):
        """Ramo 1 — `R6`+`R3`. ARCA-IT24 e gli altri nove formati che non nominano nessun gestore."""
        assignment = assign([], ["Arca Azioni Italia", "Arca Bond Paesi Emergenti"],
                            manco="Arca Fondi SGR S.p.A.")

        assert names(assignment) == ["Arca Fondi SGR S.p.A."]
        assert funds_of(assignment, "Arca Fondi SGR S.p.A.") == [
            "Arca Azioni Italia",
            "Arca Bond Paesi Emergenti",
        ]
        assert assignment.to_manco

    def test_one_manager_without_funds_takes_them_all(self, recorder):
        """Ramo 2 — `R15`. ASTERIA-EN23 p3: `Asteria Obviam SA`, e nessuna eccezione nel documento.

        La società di gestione non compare fra i gestori: resta solo società di gestione.
        """
        assignment = assign(
            [Declared("Asteria Obviam SA")],
            ["Asteria Sustainable European Equities", "Asteria Obviam Global Leaders"],
            manco="Waystone Management Company (Lux) S.A.",
        )

        assert names(assignment) == ["Asteria Obviam SA"]
        assert funds_of(assignment, "Asteria Obviam SA") == [
            "Asteria Obviam Global Leaders",
            "Asteria Sustainable European Equities",
        ]
        assert not assignment.to_manco

    def test_the_one_without_funds_takes_what_the_others_left(self, recorder):
        """Ramo 3 — `R15`. CARNE-EN23 p4: il default è scritto per primo, senza specificazione."""
        assignment = assign(
            [
                Declared("ARCA Fondi SGR S.p.A."),
                Declared("Goldman Sachs Asset Management International Ltd.",
                         ["Sidera Funds SICAV - Global High Yield"]),
            ],
            ["Sidera Funds SICAV - Global High Yield", "Sidera Funds SICAV - Equity Global"],
            manco="ARCA Fondi SGR S.p.A.",
        )

        assert funds_of(assignment, "ARCA Fondi SGR S.p.A.") == ["Sidera Funds SICAV - Equity Global"]
        assert funds_of(assignment, "Goldman Sachs Asset Management International Ltd.") == [
            "Sidera Funds SICAV - Global High Yield"
        ]

    def test_more_than_one_without_funds_gives_the_residual_to_every_one_of_them(self, recorder):
        """Ramo 4 — `R21`. AMUNDI-EN24 p8–9: tre elenchi, nessuna voce dice per quali comparti.

        La decisione dell'utente: in un caso così ambiguo si assegnano tutti i fondi a tutti i
        gestori — la mappa è molti a molti — e si paga la perdita di precisione con un avviso.
        """
        assignment = assign(
            [
                Declared("Amundi Asset Management S.A.S."),
                Declared("Montpensier Finance"),
                Declared("Polen Capital Management LLC"),
            ],
            ["Amundi Funds - Global Equity", "Amundi Funds - Euro Corporate Bond"],
            manco="Amundi Luxembourg S.A.",
        )

        assert names(assignment) == [
            "Amundi Asset Management S.A.S.",
            "Montpensier Finance",
            "Polen Capital Management LLC",
        ]
        for manager in assignment.managers:
            assert manager.funds == fund_set(
                ["Amundi Funds - Global Equity", "Amundi Funds - Euro Corporate Bond"]
            )
        assert not assignment.to_manco

    def test_a_manager_of_part_of_a_fund_does_not_take_the_fund_from_the_default(self, recorder):
        """Ramo 5 — `R21`. CARNE-EN23 p4: *«in charge for the USD nominated securities in the
        subfund Sidera Funds SICAV – Global High Yield»*.

        La specificazione non assegna un comparto, assegna **una parte** del suo portafoglio: il
        gestore parziale entra per quel comparto, e il default continua a rispondere del resto.
        """
        assignment = assign(
            [
                Declared("ARCA Fondi SGR S.p.A."),
                Declared("Goldman Sachs Asset Management International Ltd.",
                         ["Sidera Funds SICAV - Global High Yield"], partial=True),
            ],
            ["Sidera Funds SICAV - Global High Yield", "Sidera Funds SICAV - Equity Global"],
        )

        assert funds_of(assignment, "ARCA Fondi SGR S.p.A.") == [
            "Sidera Funds SICAV - Equity Global",
            "Sidera Funds SICAV - Global High Yield",
        ]
        assert funds_of(assignment, "Goldman Sachs Asset Management International Ltd.") == [
            "Sidera Funds SICAV - Global High Yield"
        ]

    def test_several_companies_under_one_specification_all_enter(self, recorder):
        """Ramo 6 — `R21`. FINECO-EN23@LUX p6: `(Only in respect of the Sub-Fund MFS Prudent
        Capital FAM Fund)` e sotto **tre** società MFS. Entrano tutte, con lo stesso comparto."""
        one_specification = ["MFS Prudent Capital FAM Fund"]
        assignment = assign(
            [
                Declared("MFS Investment Management Company (Lux) S.à r.l.", one_specification),
                Declared("Massachusetts Financial Services Company", one_specification),
                Declared("MFS International (U.K.) Limited", one_specification),
            ],
            ["MFS Prudent Capital FAM Fund", "Fidelity Global Dividend FAM Fund"],
            manco="Fineco Asset Management DAC",
        )

        assert len(assignment.managers) == 4
        assert names(assignment)[:3] == [
            "MFS Investment Management Company (Lux) S.à r.l.",
            "Massachusetts Financial Services Company",
            "MFS International (U.K.) Limited",
        ]
        assert funds_of(assignment, "Fineco Asset Management DAC") == [
            "Fidelity Global Dividend FAM Fund"
        ]

    def test_the_same_company_under_two_labels_is_one_manager(self, recorder):
        """Ramo 7 — `R22`. DANSKEINVEST-EN24 p5–6: `INVESTMENT MANAGER`, poi `SUB-INVESTMENT
        MANAGERS`, poi `SUB SUB-` e `SUB-SUB-SUB-`.

        I livelli si appiattiscono: il `text_filter` toglie la gerarchia, e qui la stessa società
        letta sotto due etichette diventa **una** voce con l'unione dei suoi comparti — altrimenti
        `assets_managers.csv` la anagrafa due volte.
        """
        assignment = assign(
            [
                Declared("Danske Bank A/S", ["Danish Bond"]),
                Declared("Allianz Global Investors Asia Pacific Ltd.", ["China"]),
                Declared("Danske Bank A/S", ["China"]),
            ],
            ["Danish Bond", "China"],
        )

        assert names(assignment) == ["Danske Bank A/S", "Allianz Global Investors Asia Pacific Ltd."]
        assert funds_of(assignment, "Danske Bank A/S") == ["China", "Danish Bond"]


class TestTheWarnings:
    """I due punti in cui l'uscita **non** sta scritta nel documento, e `R3` chiede di dirlo."""

    def test_the_residual_to_the_management_company_is_an_imposed_value(self, recorder):
        """`R3`. Il valore esce come gli altri, e solo il `.log.csv` dice che nessuno l'ha scritto."""
        assign([], ["Arca Azioni Italia"], manco="Arca Fondi SGR S.p.A.")

        assert recorder.imposed == [
            (
                "investments_manager",
                "Arca Fondi SGR S.p.A.",
                "the residual of a report that names no manager for these funds",
            )
        ]

    def test_a_declared_manager_taking_the_residual_imposes_nothing(self, recorder):
        """Quando il residuo va a un gestore che la pagina dichiara, non c'è niente di imposto."""
        assign([Declared("Asteria Obviam SA")], ["Asteria Obviam Global Leaders"],
               manco="Waystone Management Company (Lux) S.A.")

        assert recorder.imposed == []
        assert recorder.warnings == []

    def test_the_ambiguity_of_several_default_managers_is_warned_about(self, recorder):
        """`R21`. Un avviso per pagina, non uno per gestore: dice quanti sono e quanti fondi."""
        assign(
            [Declared("Amundi Asset Management S.A.S."), Declared("Montpensier Finance")],
            ["Amundi Funds - Global Equity", "Amundi Funds - Euro Corporate Bond"],
        )

        assert len(recorder.warnings) == 1
        assert "2 managers" in recorder.warnings[0]
        assert "2 residual funds" in recorder.warnings[0]

    def test_funds_with_nobody_to_take_them_are_an_error(self, recorder):
        """Un formato che non legge la società di gestione e non dichiara gestori perde i fondi.

        Non è un avviso: è una riga che non si può scrivere, e `R32` vuole che lo si dica forte.
        """
        assignment = assign([], ["Arca Azioni Italia"])

        assert assignment.managers == ()
        assert len(recorder.errors) == 1
        assert "1 funds" in recorder.errors[0]

    def test_a_manager_of_funds_this_job_never_saw_is_dropped_and_said_so(self, recorder):
        """Il filtro sui fondi d'interesse è una difesa dal rumore, e non deve essere muto (`R12`)."""
        assignment = assign(
            [Declared("Somebody Else Asset Management", ["A Fund Of Another Umbrella"])],
            ["Arca Azioni Italia"],
            manco="Arca Fondi SGR S.p.A.",
        )

        assert names(assignment) == ["Arca Fondi SGR S.p.A."]
        assert len(recorder.debugs) == 1
        assert "Somebody Else Asset Management" in recorder.debugs[0]


class TestTheFundNames:
    """`R24`: il nome del fondo che esce dev'essere quello delle fasi precedenti."""

    def test_a_declared_fund_is_respelled_as_the_investments_wrote_it(self, recorder):
        """La pagina dei gestori e quella degli investimenti non scrivono allo stesso modo.

        Le identità si confrontano normalizzate, quindi il comparto è lo stesso elemento comunque
        sia scritto; ma il nome che finisce in `funds.csv` è quello che il job già conosce.
        """
        assignment = assign(
            [Declared("Goldman Sachs Asset Management International Ltd.",
                      ["SIDERA FUNDS SICAV  -  GLOBAL HIGH YIELD"])],
            ["Sidera Funds SICAV - Global High Yield", "Sidera Funds SICAV - Equity Global"],
            manco="ARCA Fondi SGR S.p.A.",
        )

        assert funds_of(assignment, "Goldman Sachs Asset Management International Ltd.") == [
            "Sidera Funds SICAV - Global High Yield"
        ]
        assert assignment.new_funds == frozenset()

    def test_a_fund_the_job_had_not_seen_comes_out_to_be_declared(self, recorder):
        """Un comparto che solo la pagina dei gestori nomina va dichiarato, o l'assegnazione cade."""
        assignment = assign(
            [Declared("Banor Capital Limited", ["Banor Club Fineco AM Fund", "Banor Sicav Mistral"])],
            ["Banor Club Fineco AM Fund"],
            manco="Fineco Asset Management DAC",
        )

        assert sorted(fund.name for fund in assignment.new_funds) == ["Banor Sicav Mistral"]
        assert sorted(fund.name for fund in assignment.funds) == [
            "Banor Club Fineco AM Fund",
            "Banor Sicav Mistral",
        ]


class TestWhatTheManagementCompanyGets:
    """`R26`: uno a molti su tutto il documento, e i due ruoli non sono un doppione."""

    def test_the_management_company_covers_every_fund_even_when_it_manages_none(self, recorder):
        assignment = assign(
            [Declared("Asteria Obviam SA")],
            ["Asteria Obviam Global Leaders", "Asteria Sustainable European Equities"],
            manco="Waystone Management Company (Lux) S.A.",
        )

        assert assignment.funds == fund_set(
            ["Asteria Obviam Global Leaders", "Asteria Sustainable European Equities"]
        )
        assert not assignment.to_manco

    def test_it_enters_as_a_manager_only_for_what_is_left_over(self, recorder):
        assignment = assign(
            [Declared("Goldman Sachs Asset Management International Ltd.",
                      ["Sidera Funds SICAV - Global High Yield"])],
            ["Sidera Funds SICAV - Global High Yield", "Sidera Funds SICAV - Equity Global"],
            manco="ARCA Fondi SGR S.p.A.",
        )

        assert funds_of(assignment, "ARCA Fondi SGR S.p.A.") == ["Sidera Funds SICAV - Equity Global"]
        assert assignment.to_manco

    def test_nothing_left_over_means_no_manager_row_for_it(self, recorder):
        assignment = assign(
            [Declared("Goldman Sachs Asset Management International Ltd.",
                      ["Sidera Funds SICAV - Global High Yield"])],
            ["Sidera Funds SICAV - Global High Yield"],
            manco="ARCA Fondi SGR S.p.A.",
        )

        assert names(assignment) == ["Goldman Sachs Asset Management International Ltd."]
        assert not assignment.to_manco


class TestTheShapeOfADeclaration:
    """Che cosa `Declared` accetta, e la differenza che nessuno deve perdere."""

    def test_no_funds_and_no_fund_are_not_the_same_declaration(self, recorder):
        """`None` è il gestore del residuo; l'insieme vuoto è un gestore che non gestisce niente."""
        residual = assign([Declared("Asteria Obviam SA")], ["A Fund"], manco="A Manco")
        nothing = assign([Declared("Asteria Obviam SA", [])], ["A Fund"], manco="A Manco")

        assert funds_of(residual, "Asteria Obviam SA") == ["A Fund"]
        assert names(nothing) == ["A Manco"]

    def test_a_declaration_keeps_the_block_it_was_read_from(self, recorder):
        """Il blocco porta con sé la pagina, che è la colonna `Report page` dell'uscita."""

        class FakeBlock:
            content = "  Asteria Obviam SA  "

        block = FakeBlock()
        assignment = assign([Declared(block)], ["A Fund"], manco="A Manco")

        assert names(assignment) == ["Asteria Obviam SA"]
        assert assignment.managers[0].block is block

    def test_the_declaration_order_of_the_page_is_the_order_of_the_output(self, recorder):
        assignment = assign(
            [Declared("Third", ["C"]), Declared("First", ["A"]), Declared("Second", ["B"])],
            ["A", "B", "C", "D"],
            manco="The Manco",
        )

        assert names(assignment) == ["Third", "First", "Second", "The Manco"]


class TestWhatOtherPagesHaveAlreadyTaken:
    """Una sezione che sta su due pagine: la seconda vede i risultati della prima."""

    def test_funds_another_page_already_assigned_are_out_of_the_residual(self, recorder):
        """MEDIOLANUM-EN24 p3→5 e EURIZON-EN23 p9→10: l'elenco comincia e finisce su pagine diverse.

        Chi calcolasse il residuo su tutti i fondi ridarebbe alla società di gestione i comparti
        che la pagina precedente ha già affidato a qualcuno.
        """
        assignment = assign(
            [],
            ["Alpha Fund", "Beta Fund", "Gamma Fund"],
            manco="The Manco",
            already_assigned=["Alpha Fund", "Beta Fund"],
        )

        assert funds_of(assignment, "The Manco") == ["Gamma Fund"]

    def test_they_produce_no_row_of_their_own(self, recorder):
        """La riga l'ha già scritta la pagina che li ha letti: riscriverla li anagrafa due volte."""
        assignment = assign(
            [], ["Alpha Fund", "Beta Fund"], manco="The Manco", already_assigned=["Alpha Fund"]
        )

        assert names(assignment) == ["The Manco"]

    def test_the_already_assigned_funds_are_read_from_the_filter_data(self):
        """`assigned_funds` è l'aritmetica che oggi ogni `text_filter` di seconda pagina riscrive."""
        from freeports.output import Fund, InvestmentsManager

        filter_data = [
            Fund(name="Gamma Fund"),
            InvestmentsManager(name="Someone", managed_funds={"Alpha Fund", "Beta Fund"}),
        ]

        assert assigned_funds(filter_data) == fund_set(["Alpha Fund", "Beta Fund"])


class TestWhenTheSectionDoesNotEndHere:
    """`settle=False`: la pagina dichiara, ma il conto del residuo lo chiude un'altra."""

    def test_nobody_takes_what_nobody_claimed(self, recorder):
        """UBS-EN23 p4: la sezione continua a p5, dove Morgan Stanley rivendica un comparto.

        Chiudendo il conto qui, quel comparto finirebbe alla società di gestione — cioè attribuito
        a chi la pagina dopo dice esplicitamente che non lo gestisce.
        """
        assignment = assign(
            [Declared("Delegate SA", funds=["Alpha Fund"])],
            ["Alpha Fund", "Beta Fund"],
            manco="The Manco",
            settle=False,
        )

        assert names(assignment) == ["Delegate SA"]
        assert not recorder.imposed

    def test_it_says_nothing_about_the_funds_it_leaves_open(self, recorder):
        """Il residuo non deciso non è un errore: è un conto che un'altra pagina chiuderà."""
        assign([], ["Alpha Fund"], manco=None, settle=False)

        assert not recorder.errors
        assert not recorder.warnings

    def test_the_page_that_does_close_it_sees_what_the_others_took(self, recorder):
        """p5: `already_assigned` porta i comparti di p4, e il residuo è ciò che resta davvero."""
        assignment = assign(
            [Declared("Morgan Stanley", funds=["Beta Fund"])],
            ["Alpha Fund", "Beta Fund", "Gamma Fund"],
            manco="The Manco",
            already_assigned=["Alpha Fund"],
        )

        assert funds_of(assignment, "The Manco") == ["Gamma Fund"]


class TestThePublicSurface:
    """Che cosa il pacchetto offre a chi lo importa."""

    def test_everything_a_text_filter_needs_is_reachable_from_the_package(self):
        for name in inv_managers.__all__:
            assert hasattr(inv_managers, name), name


class TestDeclaredTogether:
    """`IM-1`: una pagina sola dichiara la società di gestione **e** il gestore.

    È la ricetta di ASTERIA-EN23 e ASTERIA-EN24 — che scrivono quella pagina identica a due anni di
    distanza — e di MEDIOLANUM-EN23, che la scrive con altre due etichette. Quello che si prova qui
    è **quali blocchi escono**: di chi siano i fondi lo provano i sette rami qui sopra.
    """

    MANCO = "MANAGEMENT_COMPANY"
    MANAGER = "INVESTMENTS_MANAGER"

    def blocks(self, *, manco=("Waystone Management Company (Lux) S.A.",),
               managers=("ASTERIA Investment Managers S.A.",)):
        from freeports.core import PdfBlock

        return [
            *[PdfBlock(self.MANAGER, {}, name) for name in managers],
            *[PdfBlock(self.MANCO, {}, name) for name in manco],
        ]

    def test_the_manager_and_the_management_company_both_come_out(self):
        blocks = inv_managers.declared_together()(self.blocks(), [])
        types = [blk.type_block for blk in blocks]
        assert types == ["INVESTMENTS_MANAGER", "MANAGEMENT_COMPANY"], types
        assert blocks[0].content == "ASTERIA Investment Managers S.A."
        assert blocks[1].content == "Waystone Management Company (Lux) S.A."

    def test_without_a_management_company_line_only_the_manager_comes_out(self):
        """DANSKEINVEST-EN24 p6: la seconda pagina della classe non porta quell'etichetta."""
        blocks = inv_managers.declared_together()(self.blocks(manco=()), [])
        assert [blk.type_block for blk in blocks] == ["INVESTMENTS_MANAGER"]

    def test_a_page_with_neither_produces_nothing(self):
        assert inv_managers.declared_together()(self.blocks(manco=(), managers=()), []) == []

    def test_among_chooses_which_line_is_the_management_company(self):
        """Dove il bilancio ne nomina due, a scegliere è il selettore, non l'ordine della pagina."""
        chosen = inv_managers.declared_together(among=lambda blks: blks[-1])(
            self.blocks(manco=("Prima S.A.", "Seconda S.A.")), []
        )
        assert chosen[-1].content == "Seconda S.A."

    def test_the_reader_is_a_parameter(self):
        """Un formato che scriva le dichiarazioni in un'altra forma passa il suo lettore."""
        read = lambda blks: [Declared("Letto a parte")]  # noqa: E731
        blocks = inv_managers.declared_together(read=read)(self.blocks(), [])
        assert blocks[0].content == "Letto a parte"


class TestRenamed:
    """Il blocco riscritto col nome ricostruito, che è ciò che l'uscita scrive come nome."""

    def test_it_keeps_the_type_and_the_metadata_and_changes_the_content(self):
        from freeports.core import PdfBlock

        block = PdfBlock("INVESTMENTS_MANAGER", {"group": "R11"}, "Sumitomo … Company, ")
        renamed = inv_managers.renamed(block, "Sumitomo Mitsui DS Asset Management Company, Limited")
        assert renamed.type_block == "INVESTMENTS_MANAGER"
        assert renamed.metadata["group"] == "R11"
        assert renamed.content == "Sumitomo Mitsui DS Asset Management Company, Limited"

    def test_the_original_block_is_left_alone(self):
        from freeports.core import PdfBlock

        block = PdfBlock("INVESTMENTS_MANAGER", {"group": "R11"}, "Prima")
        inv_managers.renamed(block, "Dopo")
        assert block.content == "Prima"
