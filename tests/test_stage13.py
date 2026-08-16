"""Stage 13 tests: ancient pre-history, The Sunken Tribe (Phase 2, Step 10)."""

import pytest

import engine
import events
import prompts
import state

pytestmark = pytest.mark.usefixtures("fresh_world")


@pytest.fixture(autouse=True)
def fresh_world():
    state.reset_world()
    events.LOGGING = False
    yield
    events.LOGGING = True


def pawn(pawn_id):
    return state.world_state["pawns"][pawn_id]


def test_reset_world_has_empty_lore():
    assert state.world_state["lore"] == []


def test_ruin_discovery_lore(monkeypatch):
    p = pawn("pawn_1")
    seq = iter(["lore", engine.LORE_FRAGMENTS[0]])
    monkeypatch.setattr(engine.random, "choice", lambda x: next(seq))
    ev = engine._ruin_discovery(p, "pawn_1")
    assert ev["type"] == "discovery"
    assert ev["data"]["kind"] == "lore"
    assert state.world_state["lore"][-1]["text"] == engine.LORE_FRAGMENTS[0]


def test_ruin_discovery_blueprint(monkeypatch):
    p = pawn("pawn_1")
    monkeypatch.setattr(
        engine.random,
        "choice",
        lambda x: "blueprint" if x == ("lore", "blueprint", "warning") else "Sunken Harpoon",
    )
    ev = engine._ruin_discovery(p, "pawn_1")
    assert ev["data"]["kind"] == "blueprint"
    assert "Sunken Harpoon" in state.world_state["custom_recipes"]
    assert ev["data"]["item"] == "Sunken Harpoon"


def test_ruin_discovery_blueprint_not_duplicated(monkeypatch):
    p = pawn("pawn_1")
    state.world_state["custom_recipes"] = {
        name: dict(recipe) for name, recipe in engine.RUIN_BLUEPRINTS.items()
    }
    monkeypatch.setattr(
        engine.random,
        "choice",
        lambda x: "blueprint" if x == ("lore", "blueprint", "warning") else engine.LORE_FRAGMENTS[1],
    )
    ev = engine._ruin_discovery(p, "pawn_1")
    assert ev["data"]["kind"] == "lore"
    assert len(state.world_state["custom_recipes"]) == len(engine.RUIN_BLUEPRINTS)


def test_ruin_discovery_warning(monkeypatch):
    p = pawn("pawn_1")
    p2 = pawn("pawn_2")
    before = p["skills"]["scouting"]
    before_moral = p2["vitals"]["morale"]
    monkeypatch.setattr(
        engine.random,
        "choice",
        lambda x: "warning" if x == ("lore", "blueprint", "warning") else engine.RUIN_WARNINGS[0],
    )
    ev = engine._ruin_discovery(p, "pawn_1")
    assert ev["data"]["kind"] == "warning"
    assert p["skills"]["scouting"] == before + engine.RUIN_WARNING_XP
    assert p2["vitals"]["morale"] == before_moral + engine.RUIN_WARNING_MORALE
    assert state.world_state["lore"][-1]["text"] == engine.RUIN_WARNINGS[0]


def test_lore_capped_at_max(monkeypatch):
    state.world_state["lore"] = [{"tick": i, "text": f"old {i}"} for i in range(state.MAX_LORE)]
    p = pawn("pawn_1")
    seq = iter(["lore", "fresh fragment"])
    monkeypatch.setattr(engine.random, "choice", lambda x: next(seq))
    engine._ruin_discovery(p, "pawn_1")
    assert len(state.world_state["lore"]) == state.MAX_LORE
    assert state.world_state["lore"][-1]["text"] == "fresh fragment"
    assert state.world_state["lore"][0]["text"] == "old 1"


def test_scout_on_ruins_can_discover(monkeypatch):
    p = pawn("pawn_1")
    p["pos"] = [1, 2]
    p["vitals"]["energy"] = 100
    seq = iter([1.0, 0.0])  # no damage, discovery triggers
    monkeypatch.setattr(engine.random, "random", lambda: next(seq))
    seq_choice = iter(["lore", engine.LORE_FRAGMENTS[2]])
    monkeypatch.setattr(engine.random, "choice", lambda x: next(seq_choice))
    ev = engine._do_scout(p, "pawn_1")
    assert ev["type"] == "discovery"
    assert ev["data"]["kind"] == "lore"


def test_scout_ruins_still_scavenges_when_no_discovery(monkeypatch):
    p = pawn("pawn_1")
    p["pos"] = [1, 2]
    p["vitals"]["energy"] = 100
    seq = iter([1.0, 1.0])  # no damage, no discovery
    monkeypatch.setattr(engine.random, "random", lambda: next(seq))
    ev = engine._do_scout(p, "pawn_1")
    assert ev["type"] == "scout"
    assert ev["data"]["tile"] == "ruins"


def test_prompt_mentions_sunken_tribe_and_lore():
    state.world_state["lore"].append({"tick": 1, "text": "A mosaic of a drowned city."})
    assert "Ruins of The Sunken Tribe" in prompts.SYSTEM_PROMPT
    text = prompts.build_prompt()
    assert "A mosaic of a drowned city." in text
    assert "nothing recovered yet" not in text
