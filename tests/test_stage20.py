"""Stage 20 tests: fog of war & off-grid expeditions (Phase 4, Step 17)."""

import pytest

import core
import engine
import events
import prompts
import schema
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


def tiles_key(x, y):
    return f"{x},{y}"


# ---- Fog of war ----

def test_rim_tiles_are_16():
    assert len(engine._rim_tiles()) == 16


def test_all_rim_tiles_are_forest():
    for key in engine._rim_tiles():
        x, y = (int(p) for p in key.split(","))
        assert state.world_state["grid"][y][x] == "🌲"


def test_rim_starts_misted_interior_not():
    for key in engine._rim_tiles():
        assert engine._misted(key)
    assert not engine._misted(tiles_key(1, 1))
    assert not engine._misted(tiles_key(2, 2))


def test_render_grid_shows_mist():
    assert "🌫" in engine.render_grid()


def test_reveal_fog_from_camp():
    engine._reveal_fog([2, 2])
    for x, y in [(2, 0), (0, 2), (4, 2), (2, 4)]:
        assert not engine._misted(tiles_key(x, y)), f"{x},{y} should be revealed"
    assert engine._misted(tiles_key(0, 0))


def test_scout_reveals_rim():
    p = pawn("pawn_1")
    p["pos"] = [2, 0]
    engine._do_scout(p, "pawn_1")
    assert not engine._misted(tiles_key(2, 0))
    assert not engine._misted(tiles_key(0, 0))
    assert engine._misted(tiles_key(0, 1))


def test_chop_works_on_misted_tile():
    p = pawn("pawn_1")
    p["pos"] = [2, 0]
    wood = p["inventory"]["wood"]
    engine._do_chop(p, "pawn_1")
    assert p["inventory"]["wood"] > wood


def test_perimeter_mapped_milestone():
    for key in engine._rim_tiles():
        state.world_state["tiles"].setdefault(key, {})["scouted"] = True
    result = engine.resolve_actions({"pawn_1": ("Rest", None, None, None, None)})
    assert state.world_state["perimeter_mapped"] is True
    assert any(e["type"] == "mapped" for e in result)
    assert pawn("pawn_1")["vitals"]["morale"] == 80 + engine.MAPPED_MORALE


def test_milestone_fires_once():
    for key in engine._rim_tiles():
        state.world_state["tiles"].setdefault(key, {})["scouted"] = True
    engine.resolve_actions({"pawn_1": ("Rest", None, None, None, None)})
    engine.resolve_actions({"pawn_1": ("Rest", None, None, None, None)})
    mapped = sum(1 for e in state.world_state["history"] if e["type"] == "mapped")
    assert mapped == 1


# ---- Off-grid expeditions ----

def test_action_registered():
    assert "Expedition" in engine.ACTIONS
    assert "Expedition" in schema.ACTIONS
    assert engine.ACTION_COSTS["Expedition"] == 15


def test_expedition_wrong_tile():
    p = pawn("pawn_1")
    p["pos"] = [2, 2]
    ev = engine._try_expedition(p, "pawn_1", set())
    assert ev["type"] == "failed"
    assert ev["data"]["reason"] == "wrong_tile"


def test_expedition_requires_rations():
    p = pawn("pawn_1")
    p["pos"] = [2, 0]
    p["inventory"]["food"] = 2
    ev = engine._try_expedition(p, "pawn_1", {"pawn_1"})
    assert ev["data"]["reason"] == "low_food"


def test_expedition_needs_pair():
    p = pawn("pawn_1")
    p["pos"] = [2, 0]
    p["inventory"]["food"] = 20
    ev = engine._try_expedition(p, "pawn_1", {"pawn_1"})
    assert ev["data"]["reason"] == "need_partner"


def test_expedition_launches_pair():
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["pos"] = [2, 0]
    p2["pos"] = [2, 0]
    p1["inventory"]["food"] = 20
    p2["inventory"]["food"] = 20
    intents = {
        "pawn_1": ("Expedition", None, None, None, None),
        "pawn_2": ("Expedition", None, None, None, None),
    }
    result = engine.resolve_actions(intents)
    assert p1["status"] == "expedition"
    assert p2["status"] == "expedition"
    assert p1["inventory"]["food"] == 15
    assert p2["inventory"]["food"] == 15
    expo = state.world_state["expeditions"][0]
    away = expo["return_tick"] - expo["depart_tick"]
    assert engine.EXPEDITION_TICKS_MIN <= away <= engine.EXPEDITION_TICKS_MAX
    assert [e["type"] for e in result].count("expedition") == 1


def test_expedition_returns_with_loot(monkeypatch):
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["pos"] = [2, 0]
    p2["pos"] = [2, 0]
    p1["inventory"]["food"] = 30
    p2["inventory"]["food"] = 30
    engine.resolve_actions(
        {
            "pawn_1": ("Expedition", None, None, None, None),
            "pawn_2": ("Expedition", None, None, None, None),
        }
    )
    expo = state.world_state["expeditions"][0]
    state.world_state["tick"] = expo["return_tick"]
    monkeypatch.setattr(engine.random, "random", lambda: 0.9)
    monkeypatch.setattr(engine.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(engine.random, "randint", lambda a, b: a)
    before = p1["inventory"]["food"]
    engine.tick_environment()
    assert p1["status"] == "active"
    assert p2["status"] == "active"
    assert p1["pos"] == [2, 2]
    assert p1["inventory"]["food"] >= before
    assert state.world_state["expeditions"] == []
    assert any(e["type"] == "expedition_return" for e in state.world_state["history"])


def test_expedition_return_scars(monkeypatch):
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["pos"] = [2, 0]
    p2["pos"] = [2, 0]
    p1["inventory"]["food"] = 30
    p2["inventory"]["food"] = 30
    engine.resolve_actions(
        {
            "pawn_1": ("Expedition", None, None, None, None),
            "pawn_2": ("Expedition", None, None, None, None),
        }
    )
    expo = state.world_state["expeditions"][0]
    state.world_state["tick"] = expo["return_tick"]
    before_hp = p1["vitals"]["hp"]
    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    monkeypatch.setattr(engine.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(engine.random, "randint", lambda a, b: a)
    engine.tick_environment()
    assert p1["vitals"]["hp"] == before_hp - engine.EXPEDITION_SCAR_HP
    assert p1["counters"]["scars"] == 1
    assert "farm" in state.world_state["tiles"].get("1,1", {})
    assert any(w["state"] == "tamed" for w in state.world_state["wildlife"])


def test_expedition_away_prompt():
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["pos"] = [2, 0]
    p2["pos"] = [2, 0]
    p1["inventory"]["food"] = 20
    p2["inventory"]["food"] = 20
    engine.resolve_actions(
        {
            "pawn_1": ("Expedition", None, None, None, None),
            "pawn_2": ("Expedition", None, None, None, None),
        }
    )
    text = prompts.build_prompt()
    assert "AWAY on an off-grid expedition" in text


def test_fog_txt():
    assert "0 of 16 edge tiles mapped" in core.fog_txt()
    engine._reveal_fog([2, 2])
    assert "4 of 16 edge tiles mapped" in core.fog_txt()
