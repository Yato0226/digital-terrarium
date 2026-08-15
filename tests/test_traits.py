import random

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


def test_make_pawn_rolls_valid_traits():
    p = state.make_pawn("x", "Wander")
    assert 1 <= len(p["traits"]) <= 2
    assert set(p["traits"]) <= set(state.TRAITS)
    assert p["moodlets"] == []


def test_make_pawn_explicit_traits():
    p = state.make_pawn("x", "Wander", traits=["Pacifist"])
    assert p["traits"] == ["Pacifist"]


def test_reset_world_founders_have_fixed_traits():
    assert pawn("pawn_1")["traits"] == ["Brawler"]
    assert pawn("pawn_2")["traits"] == ["Night Owl"]


def test_night_owl_halved_cost_at_night():
    p = pawn("pawn_2")
    p["vitals"]["energy"] = 100
    state.world_state["tick"] = 15  # night
    assert engine.is_day() is False
    engine.resolve_actions({"pawn_2": ("Scout", None)})
    assert p["vitals"]["energy"] == 100 - engine.ACTION_COSTS["Scout"] // 2


def test_night_owl_full_cost_by_day():
    p = pawn("pawn_2")
    p["vitals"]["energy"] = 100
    state.world_state["tick"] = 5  # day
    assert engine.is_day() is True
    engine.resolve_actions({"pawn_2": ("Scout", None)})
    assert p["vitals"]["energy"] == 100 - engine.ACTION_COSTS["Scout"]


def test_brawler_unarmed_damage_bonus():
    p, t = pawn("pawn_1"), pawn("pawn_2")
    p["vitals"]["energy"] = 100
    before = t["vitals"]["hp"]
    engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    expected = 5 + 6 // 2 - 4 // 4 + 3
    assert t["vitals"]["hp"] == before - expected


def test_brawler_spear_keeps_bonus_off():
    p = state.make_pawn("p_b", "Bruiser", traits=["Brawler"], skills={"combat": 20})
    p["gear"]["main_hand"] = "Flint Spear"
    t = pawn("pawn_2")
    t["skills"]["combat"] = 0
    t["vitals"]["hp"] = 100
    state.world_state["pawns"]["p_b"] = p
    p["vitals"]["energy"] = 100
    p["pos"] = t["pos"]
    engine.resolve_actions({"p_b": ("Attack", "pawn_2")})
    assert t["vitals"]["hp"] == 100 - (5 + 10 - 0 + engine.SPEAR_DAMAGE)


def test_brawler_axe_morale_penalty():
    p = pawn("pawn_1")
    p["gear"]["main_hand"] = "Stone Axe"
    p["vitals"]["morale"] = 80
    p["vitals"]["warmth"] = 100
    p["vitals"]["hunger"] = 80
    engine._metabolize(p, "pawn_1", state.world_state["biome"], lit=False, day=1, result=[])
    assert p["vitals"]["morale"] == 77
    p["gear"]["main_hand"] = None
    p["vitals"]["morale"] = 80
    engine._metabolize(p, "pawn_1", state.world_state["biome"], lit=False, day=1, result=[])
    assert p["vitals"]["morale"] == 82


def test_pacifist_refuses_attack():
    p, t = pawn("pawn_1"), pawn("pawn_2")
    p["traits"] = ["Pacifist"]
    p["vitals"]["energy"] = 100
    before = t["vitals"]["hp"]
    evs = engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "pacifist"
    assert t["vitals"]["hp"] == before
    assert p["vitals"]["energy"] == 100


def test_pacifist_forage_bonus(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    p = pawn("pawn_1")
    p["traits"] = ["Pacifist"]
    p["pos"] = [1, 1]
    p["skills"]["scouting"] = 20
    p["vitals"]["energy"] = 100
    before = p["inventory"]["food"]
    engine.resolve_actions({"pawn_1": ("Forage", None)})
    assert p["inventory"]["food"] == before + 9


def test_pacifist_interact_gather_bonus(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    p = pawn("pawn_1")
    p["traits"] = ["Pacifist"]
    p["pos"] = [1, 1]
    p["skills"]["scouting"] = 6
    p["vitals"]["energy"] = 100
    before = p["inventory"]["food"]
    engine.resolve_actions({"pawn_1": ("Interact", None, "gather berries")})
    assert p["inventory"]["food"] == before + 4


def test_iron_stomach_drains_slower():
    p1 = pawn("pawn_1")
    p1["vitals"]["hunger"] = 80
    engine._metabolize(p1, "pawn_1", state.world_state["biome"], lit=False, day=1, result=[])
    assert p1["vitals"]["hunger"] == 78
    p2 = state.make_pawn("p_iron", "Stomach", traits=["Iron Stomach"])
    p2["vitals"]["hunger"] = 80
    state.world_state["pawns"]["p_iron"] = p2
    engine._metabolize(p2, "p_iron", state.world_state["biome"], lit=False, day=1, result=[])
    assert p2["vitals"]["hunger"] == 79


def test_pyromaniac_near_lit_fire_morale():
    p = pawn("pawn_1")
    p["traits"] = ["Pyromaniac"]
    p["pos"] = [2, 2]
    p["vitals"]["morale"] = 80
    p["vitals"]["warmth"] = 100
    p["vitals"]["hunger"] = 80
    engine._metabolize(p, "pawn_1", state.world_state["biome"], lit=True, day=1, result=[])
    assert p["vitals"]["morale"] == 89


def test_pyromaniac_break_is_firesetter():
    p = pawn("pawn_1")
    p["traits"] = ["Pyromaniac"]
    p["personality"] = {"aggression": 2, "bravery": 2}
    assert engine._break_archetype(p) == "firesetter"


def test_firesetter_douses_fire():
    p = pawn("pawn_1")
    p["mental_break"] = "firesetter"
    p["break_ticks"] = 2
    before = state.world_state["biome"]["campfire"]
    evs = engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert state.world_state["biome"]["campfire"] == before - 10
    assert any(e["type"] == "break" and e["data"]["break"] == "firesetter" for e in evs)


def test_firesetter_burns_wood_when_no_fire():
    p = pawn("pawn_1")
    p["mental_break"] = "firesetter"
    p["break_ticks"] = 2
    p["inventory"]["wood"] = 5
    state.world_state["biome"]["campfire"] = 0
    engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert p["inventory"]["wood"] == 3


def test_firesetter_damages_shelter_fallback():
    p = pawn("pawn_1")
    p["mental_break"] = "firesetter"
    p["break_ticks"] = 2
    p["inventory"]["wood"] = 0
    state.world_state["biome"]["campfire"] = 0
    before = state.world_state["biome"]["shelter"]
    engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert state.world_state["biome"]["shelter"] == before - 5


def test_moodlet_apply_and_decay():
    p = pawn("pawn_1")
    p["moodlets"] = [{"name": "Grief", "delta": -10, "ticks_left": 2}]
    assert engine._tick_moodlets(p) == -10
    assert len(p["moodlets"]) == 1
    assert p["moodlets"][0]["ticks_left"] == 1
    assert engine._tick_moodlets(p) == -10
    assert p["moodlets"] == []
    assert engine._tick_moodlets(p) == 0


def test_moodlet_add_dedupes_by_name():
    p = pawn("pawn_1")
    p["traits"] = []
    engine._add_moodlet(p, "Grief", -10, 10)
    engine._add_moodlet(p, "Grief", -5, 5)
    assert len(p["moodlets"]) == 1
    m = p["moodlets"][0]
    assert m["name"] == "Grief"
    assert m["delta"] == -5
    assert m["ticks_left"] == 10
    engine._add_moodlet(p, "Grief", -7, 20)
    assert len(p["moodlets"]) == 1
    assert p["moodlets"][0]["delta"] == -7
    assert p["moodlets"][0]["ticks_left"] == 20
    engine._add_moodlet(p, "Frostbitten", -5, 10)
    assert len(p["moodlets"]) == 2


def test_moodlet_affects_morale():
    p = pawn("pawn_1")
    p["traits"] = []
    p["vitals"]["morale"] = 80
    p["vitals"]["warmth"] = 100
    p["vitals"]["hunger"] = 80
    p["moodlets"] = [{"name": "Grief", "delta": -10, "ticks_left": 1}]
    engine._metabolize(p, "pawn_1", state.world_state["biome"], lit=False, day=1, result=[])
    assert p["vitals"]["morale"] == 72


def test_grief_applied_on_death():
    engine._kill("pawn_2", pawn("pawn_2"), "old age")
    moods = pawn("pawn_1")["moodlets"]
    assert any(m["name"] == "Grief" and m["delta"] == -10 and m["ticks_left"] == 10 for m in moods)


def test_frostbite_adds_moodlet():
    state.world_state["tick"] = 300
    state.world_state["biome"]["season"] = "Winter"
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["warmth"] = 5
    engine._metabolize(p, "pawn_1", state.world_state["biome"], lit=False, day=0, result=[])
    assert any(m["name"] == "Frostbitten" and m["delta"] == -5 for m in p["moodlets"])


def test_director_hint_after_repeated_failures():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 5
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    info = state.failed_intents["pawn_1"]
    assert info["count"] == 2
    assert info["action"] == "Chop"
    assert "Director note" in prompts.build_prompt()
    assert "Lumberjack" in prompts.build_prompt()


def test_director_hint_resets_on_success():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 5
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert state.failed_intents["pawn_1"]["count"] == 2
    engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert state.failed_intents == {}


def test_hint_suppressed_for_god_orders():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 5
    state.god_orders["pawn_1"] = {"action": "Chop", "target": None}
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert state.failed_intents == {}
    state.god_orders.clear()


def test_inherit_traits_from_both_parents(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    mother = state.make_pawn("m", "Mom", traits=["Pacifist"])
    father = state.make_pawn("f", "Dad", traits=["Brawler", "Night Owl"])
    result = engine._inherit_traits(mother, father)
    result_set = set(result)
    assert result_set == {"Pacifist", "Brawler"}
    assert len(result) == len(result_set)


def test_birth_child_has_valid_traits():
    mother = pawn("pawn_2")
    mother["pregnant_ticks"] = 1
    engine.tick_environment()
    newborn = [p for p in state.world_state["pawns"].values() if p["id"] not in ("pawn_1", "pawn_2")]
    assert len(newborn) == 1
    assert 1 <= len(newborn[0]["traits"]) <= 2
    assert set(newborn[0]["traits"]) <= set(state.TRAITS)


def test_migrate_pawn_keeps_traits_and_moodlets():
    out = state._migrate_pawn(
        "p1",
        {
            "name": "A",
            "traits": ["Pacifist", "Bogus"],
            "moodlets": [{"name": "Grief", "delta": -10, "ticks_left": 5}],
        },
    )
    assert out["traits"] == ["Pacifist"]
    assert out["moodlets"] == [{"name": "Grief", "delta": -10, "ticks_left": 5}]


def test_migrate_pawn_old_save_rolls_traits():
    out = state._migrate_pawn("p2", {"name": "B"})
    assert 1 <= len(out["traits"]) <= 2
    assert set(out["traits"]) <= set(state.TRAITS)
    assert out["moodlets"] == []
