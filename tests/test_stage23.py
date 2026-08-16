"""Stage 23 tests: the Voice in the Sky & camp shrines (Phase 5, Step 20)."""

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


# ---- Prophets (the Voice in the Sky) ----


def test_no_prophet_by_default():
    assert all(not p.get("prophet") for p in state.world_state["pawns"].values())


def test_grant_prophet_needs_three_whispers():
    p = pawn("pawn_1")
    p["counters"]["god_whispers"] = engine.PROPHET_WHISPERS - 1
    assert engine._grant_prophet(p, "pawn_1") is None
    assert not p.get("prophet")
    p["counters"]["god_whispers"] = engine.PROPHET_WHISPERS
    ev = engine._grant_prophet(p, "pawn_1")
    assert ev is not None
    assert p.get("prophet")
    assert any(e["type"] == "prophet" for e in state.world_state["history"])


def test_grant_prophet_is_once_only():
    p = pawn("pawn_1")
    p["counters"]["god_whispers"] = engine.PROPHET_WHISPERS
    engine._grant_prophet(p, "pawn_1")
    assert engine._grant_prophet(p, "pawn_1") is None
    assert p.get("prophet")


def test_prophet_title():
    p = pawn("pawn_1")
    p["counters"]["god_whispers"] = engine.PROPHET_WHISPERS
    engine._grant_prophet(p, "pawn_1")
    engine._update_titles()
    assert p["title"] == "the Prophet"


def test_prophet_steady_morale():
    p = pawn("pawn_1")
    p["vitals"]["morale"] = 50
    engine._metabolize(p, "pawn_1", state.world_state["biome"], True, 1, [])
    base = p["vitals"]["morale"]
    p["prophet"] = True
    p["vitals"]["morale"] = 50
    engine._metabolize(p, "pawn_1", state.world_state["biome"], True, 1, [])
    assert p["vitals"]["morale"] == base + engine.PROPHET_MORALE


def test_prophet_whisper_prompt_marker():
    p = pawn("pawn_1")
    p["counters"]["god_whispers"] = engine.PROPHET_WHISPERS
    engine._grant_prophet(p, "pawn_1")
    assert "🕊️ Prophet of the Voice" in prompts.build_prompt()


def test_sermon_lifts_tilemates():
    p = pawn("pawn_1")
    other = pawn("pawn_2")
    other["pos"] = [2, 2]
    p["prophet"] = True
    ev = engine._do_sermon(p, "pawn_1")
    assert ev is not None
    assert ev["type"] == "sermon"
    assert other["vitals"]["morale"] == 80 + engine.PROPHET_SERMON_MORALE
    assert other["relationships"]["pawn_1"] == engine.PROPHET_SERMON_RELATIONSHIP


def test_sermon_requires_prophet():
    p = pawn("pawn_1")
    assert engine._do_sermon(p, "pawn_1") is None


def test_sermon_requires_camp():
    p = pawn("pawn_1")
    p["prophet"] = True
    p["pos"] = [0, 0]
    assert engine._do_sermon(p, "pawn_1") is None


def test_interact_preach_by_non_prophet_not_sermon():
    p = pawn("pawn_1")
    ev = engine._do_interact(p, "pawn_1", "preach")
    assert ev["type"] != "sermon"
    assert not any(e["type"] == "sermon" for e in state.world_state["history"])


def test_interact_preach_by_prophet_sermons():
    p = pawn("pawn_1")
    p["prophet"] = True
    ev = engine._do_interact(p, "pawn_1", "preach")
    assert ev["type"] == "sermon"


# ---- Camp Shrines & offerings ----


def test_no_shrine_by_default():
    assert state.world_state["shrine"]["built"] is False


def test_build_shrine_after_fortified():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 10
    p["inventory"]["stone"] = 10
    p["gear"]["main_hand"] = "Flint Spear"
    p["gear"]["body"] = "Warm Coat"
    biome = state.world_state["biome"]
    biome["shelter"] = 100
    biome["campfire"] = 100
    biome["granary"] = True
    biome["palisade"] = engine.PALISADE_MAX
    state.world_state["monument"] = {
        "wood": engine.MONUMENT_WOOD_NEEDED,
        "stone": engine.MONUMENT_STONE_NEEDED,
        "done": True,
        "inscription": None,
    }
    ev = engine._do_build(p, "pawn_1")
    assert ev["type"] == "shrine_built"
    assert state.world_state["shrine"]["built"] is True
    assert p["inventory"]["wood"] == 10 - engine.SHRINE_WOOD
    assert p["inventory"]["stone"] == 10 - engine.SHRINE_STONE


def test_build_shrine_needs_materials():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = engine.SHRINE_WOOD
    p["inventory"]["stone"] = 0
    p["gear"]["main_hand"] = "Flint Spear"
    p["gear"]["body"] = "Warm Coat"
    biome = state.world_state["biome"]
    biome["shelter"] = 100
    biome["campfire"] = 100
    biome["granary"] = True
    biome["palisade"] = engine.PALISADE_MAX
    state.world_state["monument"] = {
        "wood": engine.MONUMENT_WOOD_NEEDED,
        "stone": engine.MONUMENT_STONE_NEEDED,
        "done": True,
        "inscription": None,
    }
    ev = engine._do_build(p, "pawn_1")
    assert ev["type"] == "failed"
    assert state.world_state["shrine"]["built"] is False


def test_shrine_offering():
    engine._shrine()["built"] = True
    p = pawn("pawn_1")
    p["inventory"]["food"] = 5
    p["vitals"]["morale"] = 50
    ev = engine._do_shrine_offering(p, "pawn_1")
    assert ev["type"] == "shrine_offering"
    assert engine._shrine()["offered"] == 1
    assert p["inventory"]["food"] == 5 - engine.SHRINE_OFFER_FOOD
    assert p["vitals"]["morale"] == 50 + engine.SHRINE_OFFER_MORALE


def test_offering_requires_food():
    engine._shrine()["built"] = True
    p = pawn("pawn_1")
    p["inventory"]["food"] = 0
    ev = engine._do_shrine_offering(p, "pawn_1")
    assert ev["type"] == "failed"
    assert ev["data"]["reason"] == "need_food"


def test_offering_requires_shrine():
    p = pawn("pawn_1")
    p["inventory"]["food"] = 5
    assert engine._do_shrine_offering(p, "pawn_1") is None


def test_offering_requires_camp():
    engine._shrine()["built"] = True
    p = pawn("pawn_1")
    p["inventory"]["food"] = 5
    p["pos"] = [0, 0]
    assert engine._do_shrine_offering(p, "pawn_1") is None


def test_prophet_tithe_counts_double():
    engine._shrine()["built"] = True
    p = pawn("pawn_1")
    p["prophet"] = True
    p["inventory"]["food"] = 5
    ev = engine._do_shrine_offering(p, "pawn_1")
    assert ev["data"]["offered"] == 2
    assert engine._shrine()["offered"] == 2


def test_blessing_fires_at_threshold():
    shrine = engine._shrine()
    shrine["built"] = True
    shrine["offered"] = engine.SHRINE_BLESSING_OFFERINGS - 1
    p = pawn("pawn_1")
    p["inventory"]["food"] = 5
    p["vitals"]["morale"] = 80
    ev = engine._do_shrine_offering(p, "pawn_1")
    assert ev["type"] == "shrine_offering"
    assert any(e["type"] == "shrine_blessing" for e in state.world_state["history"])
    assert shrine["offered"] == 0
    assert shrine["blessings"] == 1
    assert shrine["blessed"] is True
    assert any(m["name"] == "Blessed" for m in p["moodlets"])
    assert (
        p["vitals"]["morale"]
        == 80 + engine.SHRINE_OFFER_MORALE + engine.SHRINE_BLESSING_MORALE
    )


def test_interact_offer_word_bucket():
    engine._shrine()["built"] = True
    p = pawn("pawn_1")
    p["inventory"]["food"] = 5
    ev = engine._do_interact(p, "pawn_1", "offer food to the creator")
    assert ev["type"] == "shrine_offering"


def test_shrine_warmth_near_camp():
    biome = state.world_state["biome"]
    biome["season"] = "Spring"
    biome["weather"] = "Clear"
    biome["shelter"] = 0
    biome["campfire"] = 0
    p = pawn("pawn_1")
    p["vitals"]["warmth"] = 50
    engine._metabolize(p, "pawn_1", biome, False, 1, [])
    base = p["vitals"]["warmth"]
    engine._shrine()["built"] = True
    p["vitals"]["warmth"] = 50
    engine._metabolize(p, "pawn_1", biome, False, 1, [])
    assert p["vitals"]["warmth"] == base + engine.SHRINE_WARMTH


def test_blessed_halves_cataclysm_chance(monkeypatch):
    monkeypatch.setattr(engine.random, "random", lambda: 0.1)  # under 0.12, over 0.06
    state.world_state["tick"] = 100  # Spring -> Summer, drought eligible
    engine.tick_environment()
    assert state.world_state["biome"]["cataclysm"] is not None

    state.reset_world()
    monkeypatch.setattr(engine.random, "random", lambda: 0.1)
    engine._shrine()["blessed"] = True
    state.world_state["tick"] = 100
    engine.tick_environment()
    assert state.world_state["biome"]["cataclysm"] is None


def test_shrine_txt():
    engine._shrine()["built"] = True
    text = core.shrine_txt()
    assert "Offerings" in text
    assert "Blessings granted" in text


def test_prompt_shows_shrine():
    engine._shrine()["built"] = True
    assert "Shrine: a small shrine stands at camp" in prompts.build_prompt()


def test_shrine_built_event_surfaces_in_prompt_history():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 10
    p["inventory"]["stone"] = 10
    p["gear"]["main_hand"] = "Flint Spear"
    p["gear"]["body"] = "Warm Coat"
    biome = state.world_state["biome"]
    biome["shelter"] = 100
    biome["campfire"] = 100
    biome["granary"] = True
    biome["palisade"] = engine.PALISADE_MAX
    state.world_state["monument"] = {
        "wood": engine.MONUMENT_WOOD_NEEDED,
        "stone": engine.MONUMENT_STONE_NEEDED,
        "done": True,
        "inscription": None,
    }
    engine._do_build(p, "pawn_1")
    assert any(e["type"] == "shrine_built" for e in state.world_state["history"])
