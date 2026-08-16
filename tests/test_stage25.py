"""Stage 25 tests: the domino effect — the full causal loop closes (Step 22).

Hazard strikes -> Wood stock burns -> Campfire dies -> Morale collapses ->
Berserk break -> Ancestor falls -> Grave marked -> Legend carved into the
Monolith -> New tradition forged.
"""

import pytest

import engine
import events
import state

pytestmark = pytest.mark.usefixtures("fresh_world")


@pytest.fixture(autouse=True)
def fresh_world():
    state.reset_world()
    events.LOGGING = False
    yield
    events.LOGGING = True


def test_domino_effect(monkeypatch):
    """One integration test walks the whole chain, asserting every domino falls."""
    biome = state.world_state["biome"]
    pawn_1 = state.world_state["pawns"]["pawn_1"]
    pawn_2 = state.world_state["pawns"]["pawn_2"]

    # The domino starts in a harsh Winter with a weak fire and a cold scout.
    biome["season"] = "Winter"
    biome["weather"] = "Blizzard"
    biome["campfire"] = 12
    pawn_2["pos"] = [1, 3]

    # --- 1. Hazard strikes: a wildfire on the forest edge and at the camp ---
    assert engine._ignite(0, 0)
    assert engine._ignite(2, 2)
    assert state.world_state["grid"][0][0] == engine.BURNING_TILE
    assert state.world_state["colony"]["earned"]["fire"]
    # Step 21 cross-link: the hazard is also a landmark an artisan could carve.
    assert state.world_state["last_milestone"]["title"] == "the Great Fire"

    # --- 2. Wood stock burns ---
    engine._tick_fires()
    assert state.world_state["biome"]["wood_stock"] < 100

    # --- 3. The campfire dies ---
    engine._tick_fires()
    assert state.world_state["biome"]["campfire"] == 0
    engine._tick_fires()  # the fires burn out; the camp tile regrows
    assert state.world_state["grid"][2][2] == engine.BUILD_TILE

    # --- 4. Morale collapses -> berserk break (Lumberjack, aggression 7) ---
    pawn_1["vitals"]["morale"] = 0
    pawn_1["vitals"]["hunger"] = 20
    pawn_1["vitals"]["warmth"] = 20
    pawn_1["inventory"]["food"] = 0
    engine._metabolize(pawn_1, "pawn_1", biome, False, 0, [])
    assert pawn_1["mental_break"] == "berserk"
    assert pawn_1["break_ticks"] == engine.BREAK_TICKS

    # --- 5. The Monolith stands, so a legend can be carved into it ---
    state.world_state["monument"]["done"] = True

    # --- 6. Ancestor falls (freezes once the campfire is gone) -> grave marked ---
    pawn_2["relationships"] = {"pawn_1": 50}
    pawn_2["vitals"]["warmth"] = 0
    cause = engine._death_cause(pawn_2, biome)
    assert cause == "froze in a blizzard"
    engine._kill("pawn_2", pawn_2, cause)
    assert "pawn_2" not in state.world_state["pawns"]
    grave = next(g for g in state.world_state["graveyard"] if g["id"] == "pawn_2")
    assert grave["beloved"] is True
    assert grave["cause"] == "froze in a blizzard"
    assert any(e["type"] == "death" for e in state.world_state["history"])

    # --- 7. Legend carved into the Monolith ---
    runes = state.world_state["monument"]["runes"]
    assert any(r["title"] == f"The Fall of {pawn_2['name']}" for r in runes)
    rune_events = engine._drain_runes()
    assert any(e["type"] == "rune" and "Fall of" in e["description"] for e in rune_events)

    # --- 8. A new tradition is forged at the next season change ---
    state.world_state["traditions"]["rations_shared"] = engine.KINDRED_THRESHOLD + 1
    state.world_state["tick"] = 100
    pawn_1["vitals"]["warmth"] = 80
    pawn_1["vitals"]["hunger"] = 80
    pawn_1["inventory"]["food"] = 5
    monkeypatch.setattr(engine.random, "random", lambda: 0.9)
    engine.tick_environment()
    assert engine._tradition() == engine.KINDRED_TAG
    # The wildfire that started the chain already named the colony (Ashen Kin
    # outranks Kindred in the name priority), but the fire identity stuck.
    assert state.world_state["colony"]["name"] == "The Ashen Kin"
    assert "The Settlers" in state.world_state["colony"]["history"]
    assert state.world_state["last_milestone"]["title"] == "the Kindred way"
    assert any(
        r["title"].startswith("The Kindred")
        for r in state.world_state["monument"]["runes"]
    )


# ---- The new engine link: a notable ancestor's fall is carved into the Monolith ----


def test_notable_death_carves_rune():
    state.world_state["monument"]["done"] = True
    pawn_2 = state.world_state["pawns"]["pawn_2"]
    pawn_2["relationships"] = {"pawn_1": 50}
    engine._kill("pawn_2", pawn_2, "froze in a blizzard")
    runes = state.world_state["monument"]["runes"]
    assert any(r["title"] == f"The Fall of {pawn_2['name']}" for r in runes)
    rune_events = engine._drain_runes()
    assert any(e["type"] == "rune" for e in rune_events)


def test_titled_death_carves_rune():
    state.world_state["monument"]["done"] = True
    pawn_2 = state.world_state["pawns"]["pawn_2"]
    pawn_2["title"] = "the Swift"
    pawn_2["relationships"] = {"pawn_1": 0}
    engine._kill("pawn_2", pawn_2, "starvation")
    assert any(
        r["title"] == f"The Fall of {pawn_2['name']}"
        for r in state.world_state["monument"]["runes"]
    )


def test_plain_death_does_not_carve_rune():
    state.world_state["monument"]["done"] = True
    pawn_2 = state.world_state["pawns"]["pawn_2"]
    pawn_2["title"] = None
    pawn_2["relationships"] = {"pawn_1": 0}
    engine._kill("pawn_2", pawn_2, "old age")
    assert state.world_state["monument"]["runes"] == []


def test_rune_requires_monument():
    pawn_2 = state.world_state["pawns"]["pawn_2"]
    pawn_2["relationships"] = {"pawn_1": 50}
    engine._kill("pawn_2", pawn_2, "froze in a blizzard")
    assert state.world_state["monument"]["runes"] == []
    assert engine._drain_runes() == []
