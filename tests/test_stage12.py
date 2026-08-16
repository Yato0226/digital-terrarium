"""Stage 12 tests: monolith oracle & rune archive (Phase 2, Step 9)."""

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


def _monument_done():
    state.world_state["monument"]["done"] = True


def _pray(pawn_id="pawn_1", flavor="pray"):
    return engine._do_interact(pawn(pawn_id), pawn_id, flavor)


def test_carve_rune_requires_completed_monument():
    assert engine._carve_rune("Test", "x") is None
    assert state.world_state["monument"].get("runes") in (None, [])
    assert state.pending_runes == []


def test_carve_rune_records_and_stages_event():
    _monument_done()
    ev = engine._carve_rune("The First Snow", "Winter came.")
    assert ev["type"] == "rune"
    assert state.world_state["monument"]["runes"][-1]["title"] == "The First Snow"
    assert state.pending_runes == [ev]
    assert any(h["type"] == "rune" for h in state.world_state["history"])


def test_carve_rune_caps_archive():
    _monument_done()
    for i in range(engine.MONUMENT_RUNE_MAX + 3):
        engine._carve_rune(f"Rune {i}", "x")
    runes = state.world_state["monument"]["runes"]
    assert len(runes) == engine.MONUMENT_RUNE_MAX
    assert runes[0]["title"] == "Rune 3"
    assert runes[-1]["title"] == f"Rune {engine.MONUMENT_RUNE_MAX + 2}"


def test_resolve_actions_drains_pending_runes():
    _monument_done()
    engine._carve_rune("A Rune", "x")
    tick_events = engine.resolve_actions({})
    assert any(e["type"] == "rune" for e in tick_events)
    assert state.pending_runes == []


def test_build_monument_completes_carves_foundation_rune():
    biome = state.world_state["biome"]
    biome["shelter"] = 100
    biome["campfire"] = 100
    biome["granary"] = True
    biome["palisade"] = engine.PALISADE_MAX
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 20
    p["inventory"]["stone"] = 20
    p["inventory"]["food"] = 20
    p["vitals"]["energy"] = 100
    p["gear"]["main_hand"] = "Flint Spear"
    p["gear"]["body"] = "Warm Coat"
    for _ in range(4):
        engine._do_build(p, "pawn_1")
    assert state.world_state["monument"]["done"]
    assert state.world_state["monument"]["runes"][0]["title"] == "The Monolith Rises"


def test_pray_at_monolith_grants_inspiration():
    _monument_done()
    p = pawn("pawn_1")
    weakest = min(p["skills"], key=p["skills"].get)
    before = p["skills"][weakest]
    morale = p["vitals"]["morale"]
    ev = _pray()
    assert ev["type"] == "pray"
    assert p["vitals"]["morale"] > morale
    assert p["skills"][weakest] == before + engine.MONUMENT_PRAY_XP


def test_pray_before_monolith_falls_back_to_meditation():
    ev = _pray()
    assert ev["type"] == "interact"
    assert "meditation" in ev["description"]


def test_pray_away_from_camp_falls_back_to_meditation():
    _monument_done()
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    ev = _pray()
    assert ev["type"] == "interact"
    assert "meditation" in ev["description"]


def test_pray_in_winter_grants_divine_warmth():
    _monument_done()
    state.world_state["biome"]["season"] = "Winter"
    _pray()
    moodlets = {m["name"] for m in pawn("pawn_1")["moodlets"]}
    assert "Divine Warmth" in moodlets


def test_pray_in_spring_no_weather_blessing():
    _monument_done()
    state.world_state["biome"]["season"] = "Spring"
    state.world_state["biome"]["weather"] = "Clear"
    _pray()
    moodlets = {m["name"] for m in pawn("pawn_1")["moodlets"]}
    assert "Divine Warmth" not in moodlets


def test_divine_warmth_shields_from_cold():
    _monument_done()
    biome = state.world_state["biome"]
    biome["season"] = "Winter"
    result = []
    p1 = pawn("pawn_1")
    p1["vitals"]["warmth"] = 60
    p1["pos"] = [engine.CAMP_POS[0], engine.CAMP_POS[1]]
    engine._metabolize(p1, "pawn_1", biome, lit=True, day=True, result=result)
    after_plain = p1["vitals"]["warmth"]

    p2 = pawn("pawn_2")
    p2["vitals"]["warmth"] = 60
    p2["pos"] = [engine.CAMP_POS[0], engine.CAMP_POS[1]]
    engine._add_moodlet(p2, "Divine Warmth", 0, 5)
    engine._metabolize(p2, "pawn_2", biome, lit=True, day=True, result=result)
    assert p2["vitals"]["warmth"] > after_plain


def test_tradition_forge_carves_rune():
    _monument_done()
    state.world_state["traditions"]["predators_slain"] = engine.HUNTERS_THRESHOLD + 1
    engine._evaluate_tradition()
    titles = [r["title"] for r in state.world_state["monument"]["runes"]]
    assert any("tradition is born" in t for t in titles)


def test_quest_completion_carves_rune():
    _monument_done()
    q = {
        "id": "q1",
        "title": "Tame the woods",
        "kind": "hunt",
        "needed": 3,
        "progress": 0,
        "reward_morale": 10,
        "created_tick": 0,
    }
    state.world_state["active_quests"].append(q)
    engine._complete_quest(q, actor="pawn_1")
    titles = [r["title"] for r in state.world_state["monument"]["runes"]]
    assert any("Prophecy fulfilled" in t for t in titles)


def test_first_predator_kill_carves_rune():
    _monument_done()
    state.world_state["wildlife"].append(
        {
            "id": "wild_w1",
            "species": "Wolf",
            "pos": [2, 3],
            "state": "wandering",
            "hp": 1,
            "spawn_tick": 0,
            "tamed_by": None,
        }
    )
    engine._do_attack(pawn("pawn_1"), "pawn_1", "wild_w1")
    titles = [r["title"] for r in state.world_state["monument"]["runes"]]
    assert "The First Predator Falls" in titles


def test_second_generation_birth_carves_rune():
    _monument_done()
    mother = pawn("pawn_2")
    mother["partner_id"] = "pawn_1"
    mother["pregnant_ticks"] = 1
    engine._give_birth(mother, "pawn_2", [])
    titles = [r["title"] for r in state.world_state["monument"]["runes"]]
    assert "The Second Generation Rises" in titles


def test_second_gen_rune_only_first_time():
    _monument_done()
    state.world_state["graveyard"].append(
        {"id": "p9", "name": "Old One", "generation": 2, "cause": "age", "beloved": False}
    )
    mother = pawn("pawn_2")
    mother["generation"] = 2
    mother["partner_id"] = "pawn_1"
    mother["pregnant_ticks"] = 1
    engine._give_birth(mother, "pawn_2", [])
    assert state.world_state["monument"]["runes"] == []


def test_prompt_mentions_runes_and_oracle():
    _monument_done()
    engine._carve_rune("The First Snow", "Winter came.")
    text = prompts.build_prompt()
    assert "1 runes carved" in text
    assert "pray" in text
