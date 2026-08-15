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


def traditions():
    return state.world_state["traditions"]


def test_chop_increments_colony_trees_felled():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    p["gear"]["main_hand"] = None
    p["gear"]["body"] = None
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert traditions()["trees_felled"] == 1


def test_hunt_predator_increments_predators_slain():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    p["gear"]["main_hand"] = "Flint Spear"
    wolf = state.make_animal("Wolf", pos=[2, 3], hp=1)
    state.world_state["wildlife"].append(wolf)
    engine.resolve_actions({"pawn_1": ("Attack", wolf["id"])})
    assert traditions()["predators_slain"] == 1


def test_hunt_prey_does_not_count_as_predator():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    p["gear"]["main_hand"] = "Flint Spear"
    deer = state.make_animal("Deer", pos=[2, 3], hp=1)
    state.world_state["wildlife"].append(deer)
    engine.resolve_actions({"pawn_1": ("Attack", deer["id"])})
    assert traditions()["predators_slain"] == 0


def test_share_increments_rations_shared():
    p1 = pawn("pawn_1")
    p2 = pawn("pawn_2")
    p1["vitals"]["energy"] = 100
    p1["inventory"]["food"] = 20
    p2["pos"] = [2, 3]
    engine.resolve_actions({"pawn_1": ("Share", "pawn_2")})
    assert traditions()["rations_shared"] == 1


def test_evaluate_tradition_assigns_hunters():
    traditions().update(
        {"tag": None, "predators_slain": engine.HUNTERS_THRESHOLD + 1, "trees_felled": 0, "rations_shared": 0}
    )
    ev = engine._evaluate_tradition()
    assert traditions()["tag"] == engine.HUNTERS_TAG
    assert ev["type"] == "tradition"


def test_tradition_priority_hunters_wins():
    traditions().update(
        {
            "tag": None,
            "predators_slain": engine.HUNTERS_THRESHOLD + 1,
            "trees_felled": engine.FORESTERS_THRESHOLD + 1,
            "rations_shared": engine.KINDRED_THRESHOLD + 1,
        }
    )
    engine._evaluate_tradition()
    assert traditions()["tag"] == engine.HUNTERS_TAG


def test_tradition_foresters_when_no_predators():
    traditions().update(
        {"tag": None, "predators_slain": 0, "trees_felled": engine.FORESTERS_THRESHOLD + 1, "rations_shared": 0}
    )
    engine._evaluate_tradition()
    assert traditions()["tag"] == engine.FORESTERS_TAG


def test_tradition_kindred_when_only_sharing():
    traditions().update(
        {"tag": None, "predators_slain": 0, "trees_felled": 0, "rations_shared": engine.KINDRED_THRESHOLD + 1}
    )
    engine._evaluate_tradition()
    assert traditions()["tag"] == engine.KINDRED_TAG


def test_tradition_thresholds_are_strict():
    traditions().update(
        {
            "tag": None,
            "predators_slain": engine.HUNTERS_THRESHOLD,
            "trees_felled": engine.FORESTERS_THRESHOLD,
            "rations_shared": engine.KINDRED_THRESHOLD,
        }
    )
    assert engine._evaluate_tradition() is None
    assert traditions()["tag"] is None


def test_tradition_is_sticky_once_assigned():
    traditions().update(
        {"tag": engine.HUNTERS_TAG, "predators_slain": 5, "trees_felled": 0, "rations_shared": 0}
    )
    assert engine._evaluate_tradition() is None
    assert traditions()["tag"] == engine.HUNTERS_TAG


def test_tradition_evaluated_on_season_change():
    traditions()["predators_slain"] = engine.HUNTERS_THRESHOLD + 1
    state.world_state["biome"]["season"] = "Winter"
    engine.tick_environment()
    assert traditions()["tag"] == engine.HUNTERS_TAG


def test_hunters_hunting_grants_extra_combat_xp():
    traditions()["tag"] = engine.HUNTERS_TAG
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    p["gear"]["main_hand"] = "Flint Spear"
    p["skills"]["combat"] = 5
    wolf = state.make_animal("Wolf", pos=[2, 3], hp=1)
    state.world_state["wildlife"].append(wolf)
    engine.resolve_actions({"pawn_1": ("Attack", wolf["id"])})
    assert p["skills"]["combat"] == 5 + engine.HUNTERS_COMBAT_XP


def test_hunters_reduce_cold_penalty():
    biome = state.world_state["biome"]
    biome["season"] = "Winter"
    biome["weather"] = "Blizzard"
    p = pawn("pawn_1")
    p["gear"]["main_hand"] = "Flint Spear"
    p["gear"]["body"] = None
    p["pos"] = [0, 0]
    cold = engine.SEASON_COLD["Winter"] + engine.WEATHER_COLD["Blizzard"]
    assert cold > engine.WARMTH_RECOVERY
    p["vitals"]["warmth"] = 50
    engine._metabolize(p, "pawn_1", biome, lit=False, day=True, result=[])
    without = p["vitals"]["warmth"]
    traditions()["tag"] = engine.HUNTERS_TAG
    p["vitals"]["warmth"] = 50
    engine._metabolize(p, "pawn_1", biome, lit=False, day=True, result=[])
    assert p["vitals"]["warmth"] - without == engine.HUNTERS_COLD_REDUCTION


def test_foresters_chop_bonus():
    traditions()["tag"] = engine.FORESTERS_TAG
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    p["gear"]["main_hand"] = None
    p["gear"]["body"] = None
    random.seed(1)
    wood_no_tag = None
    p["inventory"]["wood"] = 0
    state.world_state["biome"]["wood_stock"] = 100
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    wood_no_tag = p["inventory"]["wood"]
    p["inventory"]["wood"] = 0
    p["vitals"]["energy"] = 100
    traditions()["tag"] = engine.FORESTERS_TAG
    state.world_state["biome"]["wood_stock"] = 100
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert p["inventory"]["wood"] == wood_no_tag + engine.FORESTERS_CHOP_BONUS


def test_foresters_shelter_damage_halved():
    assert engine._shelter_damage(5) == 5
    traditions()["tag"] = engine.FORESTERS_TAG
    assert engine._shelter_damage(5) == 2
    assert engine._shelter_damage(10) == 5


def test_kindred_social_morale_boosted():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    p["vitals"]["morale"] = 50
    engine._do_interact(p, "pawn_1", "chat")
    assert p["vitals"]["morale"] == 50 + 5
    p2 = pawn("pawn_2")
    p2["pos"] = [2, 3]
    p2["vitals"]["morale"] = 50
    traditions()["tag"] = engine.KINDRED_TAG
    p["vitals"]["morale"] = 50
    p["vitals"]["energy"] = 100
    engine._do_interact(p, "pawn_1", "chat")
    assert p["vitals"]["morale"] == 50 + engine.KINDRED_SOCIAL_MORALE
