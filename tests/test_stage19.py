"""Stage 19 tests: persistent named legendary beasts (Phase 4, Step 16)."""

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


def make_wolf():
    w = state.make_animal("Wolf", pos=[0, 0], hp=80)
    state.world_state["wildlife"].append(w)
    return w


def promote(w):
    for _ in range(engine.LEGEND_INJURY_MIN):
        engine._predator_bites(w, pawn("pawn_1"), [])


def test_legend_requires_multiple_injuries():
    w = make_wolf()
    engine._predator_bites(w, pawn("pawn_1"), [])
    assert not w.get("legendary")
    engine._predator_bites(w, pawn("pawn_1"), [])
    assert w.get("legendary")
    assert w.get("name") in engine.LEGEND_NAMES["Wolf"]


def test_legend_promotion_hardens_hp():
    w = make_wolf()
    promote(w)
    assert w["hp"] >= int(engine.WILDLIFE["Wolf"]["hp"] * engine.LEGEND_HP_MULT)


def test_legend_hunt_moodlet_granted():
    make_wolf()
    promote(state.world_state["wildlife"][0])
    for p in state.world_state["pawns"].values():
        assert any(m["name"] == "Legend Hunt" for m in p["moodlets"])


def test_legend_fame_grows_on_more_bites():
    w = make_wolf()
    promote(w)
    assert w["legend_fame"] == 1
    engine._predator_bites(w, pawn("pawn_2"), [])
    assert w["legend_fame"] == 2
    assert engine._legend_by_wild(w)["fame"] == 2


def test_legend_fame_capped():
    w = make_wolf()
    promote(w)
    for _ in range(engine.LEGEND_MAX_FAME + 2):
        engine._predator_bites(w, pawn("pawn_2"), [])
    assert w["legend_fame"] == engine.LEGEND_MAX_FAME


def test_legend_slay_rewards_colony():
    w = make_wolf()
    promote(w)
    legend = engine._legend_by_wild(w)
    engine._slay_legend(w, pawn("pawn_1"), "pawn_1")
    assert legend["slain"]
    assert pawn("pawn_1")["counters"]["legends_slain"] == 1
    assert pawn("pawn_2")["vitals"]["morale"] == 80 + engine.LEGEND_SLAY_MORALE
    assert not any(m["name"] == "Legend Hunt" for m in pawn("pawn_2")["moodlets"])


def test_legend_escapes_on_season_change():
    w = make_wolf()
    promote(w)
    legend = engine._legend_by_wild(w)
    state.world_state["tick"] = 100  # Spring -> Summer
    result = engine.tick_environment()
    assert legend["escapes"] == 1
    assert legend["fame"] == 2
    assert any(e["type"] == "legend_escape" for e in result)
    assert not any(x["id"] == w["id"] for x in state.world_state["wildlife"])


def test_legend_returns_to_stalk(monkeypatch):
    state.world_state["legends"] = [
        {
            "id": "legend_wild_9",
            "wild_id": None,
            "species": "Wolf",
            "name": "Old Scar-Face",
            "fame": 2,
            "created_tick": 50,
            "slain": False,
            "slain_tick": None,
            "slain_by": None,
            "escapes": 1,
        }
    ]
    state.world_state["tick"] = 300  # Spring -> Winter
    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    monkeypatch.setattr(engine.random, "choice", lambda seq: seq[0])
    result = engine.tick_environment()
    assert any(e["type"] == "legend_return" for e in result)
    beasts = [w for w in state.world_state["wildlife"] if w.get("legendary")]
    assert beasts and beasts[0]["name"] == "Old Scar-Face"


def test_attack_slays_legend():
    w = make_wolf()
    w["pos"] = list(pawn("pawn_1")["pos"])
    promote(w)
    w["hp"] = 3
    legend = engine._legend_by_wild(w)
    ev = engine._do_attack(pawn("pawn_1"), "pawn_1", w["id"])
    assert legend["slain"]
    assert w not in state.world_state["wildlife"]
    assert ev["type"] == "hunt"


def test_render_grid_marks_legend():
    w = make_wolf()
    promote(w)
    assert "👑" in engine.render_grid()


def test_prompt_shows_legend():
    w = make_wolf()
    promote(w)
    assert w["name"] in prompts.build_prompt()


def test_legends_txt():
    w = make_wolf()
    promote(w)
    assert w["name"] in core.legends_txt()
    assert "stalking" in core.legends_txt()


def test_legends_txt_empty():
    assert "No legendary beasts" in core.legends_txt()


def test_make_pawn_has_legends_counter():
    assert state.make_pawn("p9", "Foundling")["counters"]["legends_slain"] == 0
