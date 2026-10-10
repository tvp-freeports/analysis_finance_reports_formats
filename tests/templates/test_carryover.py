"""`U7` per **numero di pagina**: il valore che una pagina lascia a una di qualche pagina dopo.

Le altre tre parti di `carryover` — `Record`, `Carryover` e `sole_fund` — sono passate al motore il
2026-10-05 (`labelled_assets`, `carryover_deposit`, `assets`), e con loro le quarantasei prove che
le coprivano: stanno in `formats_utils/text_filter/carryover.rs`, coi numeri di ARCA-IT24 D1 p8→p9
che portavano. Qui resta il solo pezzo che i formati usano ancora da Python, perche' lo chiama un
`pdf_extract` d'autore.

I dati vengono da FINECO-EN23@IR D1 p893→894: `Product name: Fidelity EURO Bond FAM Fund` in testa
all'allegato, gli indicatori sulla pagina dopo, e il numero stampato in fondo a tutt'e due in
`timesnewroman` 10.
"""

import pytest

from freeports.core import PdfBlock, TextBlock

import carryover
from carryover import page as page_module


class Recorder:
    """Un registro finto, per leggere cio' che il modulo dice mentre lavora."""

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
    """Sostituisce il registro del modulo per la durata di un test."""
    recorder = Recorder()
    monkeypatch.setattr(page_module, "log", recorder)
    return recorder


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

    def test_a_field_that_carries_nothing_is_refused(self):
        with pytest.raises(ValueError):
            carryover.PageCarryover("")

    def test_the_deposit_is_the_promise_the_next_page_will_find(self):
        block = TextBlock.from_content("REL", {"page": 893}, "Fidelity EURO Bond FAM Fund ")

        assert self.carry().deposit(block) == {
            "esg-fund-page-893": "Fidelity EURO Bond FAM Fund",
        }

    def test_a_block_without_its_page_leaves_nothing_and_says_so(self, recorder):
        block = TextBlock.from_content("REL", {}, "Fidelity EURO Bond FAM Fund")

        assert self.carry().deposit(block) == {}
        assert any("cannot leave anything" in message for message in recorder.errors)

