"""Stage 21 tests: multi-tick seasonal cataclysms (Phase 4, Step 18)."""

import pytest

import core
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


def grid():
    return state.world_state["grid"]


def test_no_cataclysm_by_default():
    assert state.world_state["biome"]["cataclysm"] is None


def test_cataclysm_kind_helper():
    assert engine._cataclysm_kind() is None
    state.world_state["biome"]["cataclysm"] = {"kind": "long_winter", "name": "The Long Winter"}
    assert engine._cataclysm_kind() == "long_winter"


def test_long_winter_triggers_on_winter_entry(monkeypatch):
    state.world_state["tick"] = 300  # Spring -> Winter
    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    result = engine.tick_environment()
    cataclysm = state.world_state["biome"]["cataclysm"]
    assert cataclysm is not None
    assert cataclysm["kind"] == "long_winter"
    assert cataclysm["ends_tick"] - cataclysm["started_tick"] == engine.LONG_WINTER_TICKS
    assert any(e["type"] == "cataclysm" for e in result)


def test_drought_triggers_on_summer_entry(monkeypatch):
    state.world_state["tick"] = 100  # Spring -> Summer
    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    engine.tick_environment()
    cataclysm = state.world_state["biome"]["cataclysm"]
    assert cataclysm is not None
    assert cataclysm["kind"] == "drought"
    assert cataclysm["ends_tick"] - cataclysm["started_tick"] == engine.DROUGHT_TICKS


def test_cataclysm_expires():
    state.world_state["biome"]["cataclysm"] = {
        "kind": "long_winter",
        "name": "The Long Winter",
        "started_tick": 1,
        "ends_tick": 1,
    }
    result = engine.tick_environment()
    assert state.world_state["biome"]["cataclysm"] is None
    assert any(e["type"] == "cataclysm_end" for e in result)


def test_long_winter_double_fuel():
    state.world_state["biome"]["cataclysm"] = {
        "kind": "long_winter",
        "name": "The Long Winter",
        "ends_tick": 999,
    }
    state.world_state["biome"]["campfire"] = 50
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 10
    engine._feed_campfire()
    assert p["inventory"]["wood"] == 10 - engine.CAMPFIRE_FUEL * engine.LONG_WINTER_FUEL_MULT


def test_drought_blocks_river_forage():
    state.world_state["biome"]["cataclysm"] = {
        "kind": "drought",
        "name": "The Great Drought",
        "ends_tick": 999,
    }
    p = pawn("pawn_1")
    p["pos"] = [2, 3]  # river tile
    ev = engine._do_forage(p, "pawn_1")
    assert ev["type"] == "failed"
    assert ev["data"]["reason"] == "drought"


def test_river_forage_ok_without_drought():
    p = pawn("pawn_1")
    p["pos"] = [2, 3]
    food = p["inventory"]["food"]
    ev = engine._do_forage(p, "pawn_1")
    assert ev["type"] != "failed"
    assert p["inventory"]["food"] > food


def test_drought_spikes_fire_spread(monkeypatch):
    grid()[1][1] = "🔥"
    state.world_state["tiles"]["1,1"] = {"burn": 1, "regrow_to": "🌲"}
    state.world_state["biome"]["cataclysm"] = {
        "kind": "drought",
        "name": "The Great Drought",
        "ends_tick": 999,
    }
    monkeypatch.setattr(engine.random, "random", lambda: 0.6)
    result = engine._spread_fire()
    assert any(e["type"] == "fire_spread" for e in result)


def test_drought_without_boost_no_spread(monkeypatch):
    grid()[1][1] = "🔥"
    state.world_state["tiles"]["1,1"] = {"burn": 1, "regrow_to": "🌲"}
    monkeypatch.setattr(engine.random, "random", lambda: 0.6)
    result = engine._spread_fire()
    assert not any(e["type"] == "fire_spread" for e in result)


def test_cataclysm_txt():
    assert "No cataclysm" in core.cataclysm_txt()
    state.world_state["biome"]["cataclysm"] = {
        "kind": "drought",
        "name": "The Great Drought",
        "started_tick": 1,
        "ends_tick": 100,
    }
    text = core.cataclysm_txt()
    assert "The Great Drought" in text
    assert "river" in text


def test_prompt_shows_cataclysm():
    state.world_state["biome"]["cataclysm"] = {
        "kind": "long_winter",
        "name": "The Long Winter",
        "started_tick": 1,
        "ends_tick": 100,
    }
    text = prompts.build_prompt()
    assert "The Long Winter" in text
    assert "⚠️" in text


def test_drought_is_feasibility_reason():
    assert "drought" in engine.FEASIBILITY_REASONS
