import random

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


def pawn(pawn_id):
    return state.world_state["pawns"][pawn_id]


# --- Stage 9 Part 1: data model & registries ---------------------------------


def test_world_state_has_stage9_registries():
    assert state.world_state["custom_recipes"] == {}
    assert state.world_state["active_quests"] == []
    assert state.world_state["patch_version"] == "v1.0"
    assert state.world_state["biome"]["modifiers"] == {
        "regrowth": 1.0,
        "cold": 1.0,
        "spawn": 1.0,
    }


def test_old_save_without_stage9_keys_loads_cleanly(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "STATE_FILE", str(tmp_path / "state.json"))
    state.world_state["pawns"] = {"pawn_1": state.make_pawn("pawn_1", "Lumberjack")}
    state.world_state["biome"] = {
        "season": "Spring",
        "weather": "Clear",
        "day": 1,
        "campfire": 50,
        "shelter": 50,
        "wood_stock": 100,
        "food_stock": 100,
    }
    state.save_state()
    state.load_state()
    assert state.world_state["custom_recipes"] == {}
    assert state.world_state["active_quests"] == []
    assert state.world_state["patch_version"] == "v1.0"
    assert state.world_state["biome"]["modifiers"] == {
        "regrowth": 1.0,
        "cold": 1.0,
        "spawn": 1.0,
    }


def test_partial_modifiers_default_missing_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "STATE_FILE", str(tmp_path / "state.json"))
    state.world_state["pawns"] = {"pawn_1": state.make_pawn("pawn_1", "Lumberjack")}
    state.world_state["biome"] = {
        "season": "Spring",
        "weather": "Clear",
        "day": 1,
        "campfire": 50,
        "shelter": 50,
        "wood_stock": 100,
        "food_stock": 100,
        "modifiers": {"regrowth": 1.2},
    }
    state.save_state()
    state.load_state()
    mods = state.world_state["biome"]["modifiers"]
    assert mods["regrowth"] == 1.2
    assert mods["cold"] == 1.0
    assert mods["spawn"] == 1.0


def test_custom_recipes_persist_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "STATE_FILE", str(tmp_path / "state.json"))
    state.world_state["custom_recipes"] = {
        "Moss Knife": {"materials": {"wood": 2}, "slot": "main_hand", "tier": 4}
    }
    state.save_state()
    state.load_state()
    assert state.world_state["custom_recipes"]["Moss Knife"]["tier"] == 4


def test_active_quests_persist_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "STATE_FILE", str(tmp_path / "state.json"))
    state.world_state["active_quests"] = [
        {"id": "quest_1", "title": "Winter Stores", "progress": 3, "needed": 10}
    ]
    state.save_state()
    state.load_state()
    assert state.world_state["active_quests"][0]["title"] == "Winter Stores"
    assert state.world_state["active_quests"][0]["progress"] == 3


def test_patch_version_persists_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "STATE_FILE", str(tmp_path / "state.json"))
    state.world_state["patch_version"] = "v1.3"
    state.save_state()
    state.load_state()
    assert state.world_state["patch_version"] == "v1.3"


# --- Stage 9 Part 2: synthesis & quest engine ---------------------------------


def quest(**kw):
    base = {
        "id": "quest_1",
        "title": "Prophecy",
        "text": "The stars foretell.",
        "kind": "hunt",
        "needed": 1,
        "progress": 0,
        "reward_morale": 15,
        "reward_title": None,
        "created_tick": 1,
    }
    base.update(kw)
    state.world_state["active_quests"].append(base)
    return base


def test_all_recipes_merges_static_and_custom():
    state.world_state["custom_recipes"] = {
        "Moss Knife": {
            "materials": {"wood": 2, "stone": 1},
            "slot": "main_hand",
            "tier": 4,
            "bonus": {"combat": 1},
        }
    }
    recipes = engine._all_recipes()
    assert "Stone Axe" in recipes and recipes["Stone Axe"]["tier"] == 2
    assert recipes["Moss Knife"]["materials"] == {"wood": 2, "stone": 1}
    assert recipes["Moss Knife"]["slot"] == "main_hand"
    assert recipes["Moss Knife"]["tier"] == 4


def test_build_crafts_custom_recipe_over_static():
    state.world_state["custom_recipes"] = {
        "Moss Knife": {
            "materials": {"wood": 2, "stone": 1},
            "slot": "main_hand",
            "tier": 4,
            "bonus": {"combat": 1},
        }
    }
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 5
    p["inventory"]["stone"] = 3
    ev = engine._do_build(p, "pawn_1")
    assert p["gear"]["main_hand"] == "Moss Knife"
    assert p["inventory"]["wood"] == 3
    assert p["inventory"]["stone"] == 2
    assert ev["type"] == "craft"


def test_build_crafts_custom_body_recipe():
    state.world_state["custom_recipes"] = {
        "Fur Cloak": {
            "materials": {"fiber": 3},
            "slot": "body",
            "tier": 2,
            "bonus": {"scouting": 1},
        }
    }
    p = pawn("pawn_1")
    p["inventory"]["fiber"] = 5
    engine._do_build(p, "pawn_1")
    assert p["gear"]["body"] == "Fur Cloak"


def test_custom_recipe_unaffordable_falls_back_to_static():
    state.world_state["custom_recipes"] = {
        "Sky Hammer": {
            "materials": {"wood": 99, "stone": 99},
            "slot": "main_hand",
            "tier": 10,
            "bonus": {"combat": 5},
        }
    }
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 4
    p["inventory"]["stone"] = 3
    engine._do_build(p, "pawn_1")
    assert p["gear"]["main_hand"] == "Flint Spear"


def test_custom_combat_bonus_increases_damage():
    state.world_state["custom_recipes"] = {
        "Moss Knife": {
            "materials": {"wood": 2},
            "slot": "main_hand",
            "tier": 4,
            "bonus": {"combat": 2},
        }
    }
    p = pawn("pawn_1")
    p["vitals"]["morale"] = 50
    p["gear"]["main_hand"] = "Moss Knife"
    wolf = state.make_animal("Wolf", pos=[2, 2], hp=50)
    state.world_state["wildlife"].append(wolf)
    engine.resolve_actions({"pawn_1": ("Attack", wolf["id"])})
    dmg = 5 + p["skills"]["combat"] // 2 + 2
    assert wolf["hp"] == 50 - dmg


def test_custom_forage_bonus_increases_yield(monkeypatch):
    state.world_state["custom_recipes"] = {
        "Sickle": {
            "materials": {"wood": 2},
            "slot": "main_hand",
            "tier": 4,
            "bonus": {"scouting": 2, "fiber": 1},
        }
    }
    monkeypatch.setattr(random, "choice", lambda seq: 0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    p = pawn("pawn_1")
    p["vitals"]["morale"] = 50
    p["pos"] = [1, 1]
    p["gear"]["main_hand"] = "Sickle"
    skill = p["skills"]["scouting"]
    engine._do_forage(p, "pawn_1")
    assert p["inventory"]["food"] == 2 + skill // 4 + 2
    assert p["inventory"]["fiber"] == 1 + 1


def test_custom_woodcutting_bonus_increases_chop(monkeypatch):
    state.world_state["custom_recipes"] = {
        "Bone Axe": {
            "materials": {"wood": 2},
            "slot": "main_hand",
            "tier": 4,
            "bonus": {"woodcutting": 2},
        }
    }
    monkeypatch.setattr(random, "choice", lambda seq: 0)
    p = pawn("pawn_1")
    p["vitals"]["morale"] = 50
    p["pos"] = [0, 0]
    p["gear"]["main_hand"] = "Bone Axe"
    state.world_state["biome"]["wood_stock"] = 50
    skill = p["skills"]["woodcutting"]
    engine._do_chop(p, "pawn_1")
    assert p["inventory"]["wood"] == 3 + skill // 3 + 2
    assert state.world_state["biome"]["wood_stock"] == 50 - p["inventory"]["wood"]


def test_brawler_custom_weapon_avoids_penalty():
    state.world_state["custom_recipes"] = {
        "Moss Knife": {
            "materials": {"wood": 2},
            "slot": "main_hand",
            "tier": 4,
            "bonus": {"combat": 2},
        }
    }
    biome = state.world_state["biome"]
    biome.update({"season": "Spring", "weather": "Clear", "shelter": 30})
    p1 = pawn("pawn_1")
    p2 = pawn("pawn_2")
    for p in (p1, p2):
        p["traits"] = ["Brawler"]
        p["vitals"]["morale"] = 80
        p["vitals"]["warmth"] = 40
        p["vitals"]["hunger"] = 40
        p["pos"] = [0, 0]
    p1["gear"]["main_hand"] = "Moss Knife"
    p2["gear"]["main_hand"] = "Bone Axe"
    state.world_state["custom_recipes"]["Bone Axe"] = {
        "materials": {"wood": 2},
        "slot": "main_hand",
        "tier": 4,
        "bonus": {"woodcutting": 2},
    }
    engine._metabolize(p1, "pawn_1", biome, lit=True, day=True, result=[])
    engine._metabolize(p2, "pawn_2", biome, lit=True, day=True, result=[])
    assert p1["vitals"]["morale"] == 80
    assert p2["vitals"]["morale"] == 75


def test_cold_modifier_scales_warmth_drain():
    biome = state.world_state["biome"]
    biome.update({"season": "Winter", "weather": "Blizzard", "shelter": 30})
    p1 = pawn("pawn_1")
    p2 = pawn("pawn_2")
    for p in (p1, p2):
        p["pos"] = [0, 0]
        p["vitals"]["warmth"] = 100
    p1["vitals"]["morale"] = 50
    p2["vitals"]["morale"] = 50
    biome["modifiers"]["cold"] = 1.3
    engine._metabolize(p1, "pawn_1", biome, lit=False, day=True, result=[])
    biome["modifiers"]["cold"] = 0.7
    engine._metabolize(p2, "pawn_2", biome, lit=False, day=True, result=[])
    assert p1["vitals"]["warmth"] < p2["vitals"]["warmth"]


def test_regrowth_modifier_scales_growth():
    biome = state.world_state["biome"]
    biome.update({"season": "Spring", "weather": "Clear"})
    biome["wood_stock"] = 50
    biome["food_stock"] = 100
    biome["campfire"] = 100
    biome["modifiers"]["regrowth"] = 1.3
    engine.tick_environment()
    assert biome["wood_stock"] == 50 + round(2 * 1.3)


def test_spawn_modifier_suppresses_wildlife(monkeypatch):
    state.world_state["tick"] = 300
    biome = state.world_state["biome"]
    biome.update(
        {"season": "Winter", "weather": "Snow", "campfire": 100, "shelter": 100}
    )
    state.world_state["wildlife"] = []
    for p in state.world_state["pawns"].values():
        p["vitals"]["hp"] = 200
        p["vitals"]["energy"] = 200
        p["vitals"]["warmth"] = 100
        p["vitals"]["hunger"] = 100
        p["inventory"]["food"] = 50
    biome["modifiers"]["spawn"] = 0.7
    monkeypatch.setattr(random, "random", lambda: 0.24)
    engine.tick_environment()
    assert not state.world_state["wildlife"]


def test_default_spawn_allows_predator(monkeypatch):
    state.world_state["tick"] = 300
    biome = state.world_state["biome"]
    biome.update(
        {"season": "Winter", "weather": "Snow", "campfire": 100, "shelter": 100}
    )
    state.world_state["wildlife"] = []
    for p in state.world_state["pawns"].values():
        p["vitals"]["hp"] = 200
        p["vitals"]["energy"] = 200
        p["vitals"]["warmth"] = 100
        p["vitals"]["hunger"] = 100
        p["inventory"]["food"] = 50
    monkeypatch.setattr(random, "random", lambda: 0.24)
    engine.tick_environment()
    assert any(
        w["species"] in engine.PREDATOR_SPECIES for w in state.world_state["wildlife"]
    )


def test_clamp_modifier_bounds():
    assert engine._clamp_modifier(0.5) == 0.7
    assert engine._clamp_modifier(2.0) == 1.3
    assert engine._clamp_modifier(1.0) == 1.0
    assert engine._clamp_modifier(None) == 1.0
    assert engine._clamp_modifier("junk") == 1.0


def test_modifier_reads_clamped_biome_value():
    state.world_state["biome"]["modifiers"]["regrowth"] = 9.0
    assert engine._modifier("regrowth") == 1.3
    state.world_state["biome"]["modifiers"] = {}
    assert engine._modifier("regrowth") == 1.0


def test_hunt_quest_completes_on_species_kill():
    wolf = state.make_animal("Wolf", pos=[2, 2], hp=5)
    state.world_state["wildlife"].append(wolf)
    quest(
        kind="hunt",
        species="Wolf",
        needed=1,
        reward_title="the Wolf-Slayer",
    )
    p = pawn("pawn_1")
    engine.resolve_actions({"pawn_1": ("Attack", wolf["id"])})
    assert state.world_state["active_quests"] == []
    assert p["vitals"]["morale"] == 95
    assert p["title"] == "the Wolf-Slayer"
    assert any(
        ev["type"] == "quest_complete"
        for ev in state.world_state["history"]
    )


def test_hunt_quest_ignores_other_species():
    deer = state.make_animal("Deer", pos=[2, 2], hp=5)
    state.world_state["wildlife"].append(deer)
    quest(kind="hunt", species="Bear", needed=1)
    engine.resolve_actions({"pawn_1": ("Attack", deer["id"])})
    assert len(state.world_state["active_quests"]) == 1
    assert state.world_state["active_quests"][0]["progress"] == 0


def test_chop_quest_progresses_and_completes(monkeypatch):
    monkeypatch.setattr(random, "choice", lambda seq: 0)
    quest(kind="chop", needed=1)
    p = pawn("pawn_1")
    p["vitals"]["morale"] = 50
    p["pos"] = [0, 0]
    state.world_state["biome"]["wood_stock"] = 50
    engine._do_chop(p, "pawn_1")
    assert state.world_state["active_quests"] == []
    assert p["vitals"]["morale"] == 65


def test_stockpile_quest_completes_at_threshold():
    quest(kind="stockpile", resource="wood", needed=10)
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 12
    events_list = engine._check_quests()
    assert len(events_list) == 1
    assert state.world_state["active_quests"] == []
    assert p["vitals"]["morale"] == 95


def test_stockpile_quest_stays_open_below_threshold():
    quest(kind="stockpile", resource="wood", needed=10)
    pawn("pawn_1")["inventory"]["wood"] = 5
    events_list = engine._check_quests()
    assert events_list == []
    assert len(state.world_state["active_quests"]) == 1


def test_survive_quest_completes_after_days():
    quest(kind="survive", needed=2, created_tick=1)
    state.world_state["tick"] = 41
    events_list = engine._check_quests()
    assert len(events_list) == 1
    assert state.world_state["active_quests"] == []


def test_survive_quest_stays_open_early():
    quest(kind="survive", needed=2, created_tick=1)
    state.world_state["tick"] = 39
    events_list = engine._check_quests()
    assert events_list == []
    assert len(state.world_state["active_quests"]) == 1
    assert state.world_state["active_quests"][0]["progress"] == 1


def test_quest_reward_goes_to_all_active_pawns():
    quest(kind="hunt", species="Wolf", needed=1)
    wolf = state.make_animal("Wolf", pos=[2, 2], hp=5)
    state.world_state["wildlife"].append(wolf)
    engine.resolve_actions({"pawn_1": ("Attack", wolf["id"])})
    assert pawn("pawn_2")["vitals"]["morale"] == 95
