import json
import random

import pytest

import engine
import events
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


def test_rest_regenerates():
    p = pawn("pawn_1")
    p["vitals"]["hp"] = 50
    p["vitals"]["energy"] = 10
    engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert p["vitals"]["hp"] == 60
    assert p["vitals"]["energy"] == 30


def test_chop_requires_energy():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 5
    before = p["inventory"]["wood"]
    evs = engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert evs[0]["type"] == "failed"
    assert p["inventory"]["wood"] == before
    assert p["vitals"]["energy"] == 5


def test_chop_gains_wood_and_skill():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    before_wood = p["inventory"]["wood"]
    before_skill = p["skills"]["woodcutting"]
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert p["inventory"]["wood"] > before_wood
    assert p["skills"]["woodcutting"] >= before_skill


def test_attack_requires_target():
    evs = engine.resolve_actions({"pawn_1": ("Attack", None)})
    assert evs[0]["type"] == "failed"
    assert pawn("pawn_2")["vitals"]["hp"] == 90


def test_attack_self_rejected():
    evs = engine.resolve_actions({"pawn_1": ("Attack", "pawn_1")})
    assert evs[0]["type"] == "failed"
    assert pawn("pawn_1")["vitals"]["hp"] == 100


def test_attack_damages_target():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    t = pawn("pawn_2")
    t["skills"]["combat"] = 0
    before = t["vitals"]["hp"]
    engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert t["vitals"]["hp"] < before
    assert p["skills"]["combat"] > 6


def test_attack_energy_cost_enforced():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 15
    t = pawn("pawn_2")
    before = t["vitals"]["hp"]
    evs = engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert t["vitals"]["hp"] == before


def test_incapacitation_at_zero_hp():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    p["skills"]["combat"] = 20
    t = pawn("pawn_2")
    t["skills"]["combat"] = 0
    t["vitals"]["hp"] = 1
    engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert t["status"] == "incapacitated"
    assert t["vitals"]["hp"] == 0


def test_recovery_from_incapacitated():
    t = pawn("pawn_2")
    t["status"] = "incapacitated"
    t["vitals"]["hp"] = 0
    evs = engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert any(e["type"] == "recover" for e in evs)
    assert t["status"] == "active"
    assert t["vitals"]["hp"] > 0


def test_relationship_changes_on_attack():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    t = pawn("pawn_2")
    engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert p["relationships"]["pawn_2"] < 0
    assert t["relationships"]["pawn_1"] < 0


def test_chop_drains_forest_stock():
    pawn("pawn_1")["pos"] = [0, 0]
    before = state.world_state["biome"]["wood_stock"]
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert state.world_state["biome"]["wood_stock"] < before


def test_forage_gains_food_and_drains_stock():
    p = pawn("pawn_1")
    p["pos"] = [1, 1]
    before_food = p["inventory"]["food"]
    before_stock = state.world_state["biome"]["food_stock"]
    engine.resolve_actions({"pawn_1": ("Forage", None)})
    assert p["inventory"]["food"] > before_food
    assert state.world_state["biome"]["food_stock"] < before_stock


def test_forage_fails_when_stock_empty():
    pawn("pawn_1")["pos"] = [1, 1]
    state.world_state["biome"]["food_stock"] = 0
    evs = engine.resolve_actions({"pawn_1": ("Forage", None)})
    assert evs[0]["type"] == "failed"
    assert pawn("pawn_1")["inventory"]["food"] == 0


def test_build_requires_wood():
    evs = engine.resolve_actions({"pawn_1": ("Build", None)})
    assert evs[0]["type"] == "failed"
    assert state.world_state["biome"]["shelter"] == 50


def test_build_raises_shelter():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 10
    engine.resolve_actions({"pawn_1": ("Build", None)})
    assert state.world_state["biome"]["shelter"] > 50
    assert p["inventory"]["wood"] == 7


def test_build_full_shelter_repairs_campfire():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 10
    state.world_state["biome"]["shelter"] = 100
    before = state.world_state["biome"]["campfire"]
    engine.resolve_actions({"pawn_1": ("Build", None)})
    assert state.world_state["biome"]["campfire"] > before


def test_share_requires_target():
    evs = engine.resolve_actions({"pawn_1": ("Share", None)})
    assert evs[0]["type"] == "failed"


def test_share_transfers_food_and_raises_relationship():
    p, t = pawn("pawn_1"), pawn("pawn_2")
    p["inventory"]["food"] = 5
    engine.resolve_actions({"pawn_1": ("Share", "pawn_2")})
    assert p["inventory"]["food"] == 4
    assert t["inventory"]["food"] == 1
    assert p["relationships"]["pawn_2"] > 0
    assert p["vitals"]["morale"] > 80


def test_hunger_drains_and_auto_eats():
    p = pawn("pawn_1")
    p["vitals"]["hunger"] = 10
    p["inventory"]["food"] = 5
    engine.tick_environment()
    assert p["vitals"]["hunger"] > 10
    assert p["inventory"]["food"] == 4


def test_starvation_drains_hp_and_energy():
    p = pawn("pawn_1")
    p["vitals"]["hunger"] = 0
    p["vitals"]["hp"] = 50
    p["vitals"]["energy"] = 50
    engine.tick_environment()
    assert p["vitals"]["hp"] == 45
    assert p["vitals"]["energy"] == 45


def test_campfire_burns_pawn_wood():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 5
    before = state.world_state["biome"]["campfire"]
    engine.tick_environment()
    assert p["inventory"]["wood"] == 4
    assert state.world_state["biome"]["campfire"] > before


def test_unfed_campfire_decays():
    state.world_state["biome"]["campfire"] = 2
    engine.tick_environment()
    assert state.world_state["biome"]["campfire"] == 0


def test_frostbite_in_winter():
    state.world_state["tick"] = 300
    state.world_state["biome"]["campfire"] = 0
    p = pawn("pawn_1")
    p["vitals"]["warmth"] = 5
    engine.tick_environment()
    assert p["vitals"]["warmth"] == 0
    assert p["vitals"]["hp"] < 100


def test_no_regrowth_in_winter():
    state.world_state["tick"] = 300
    state.world_state["biome"]["food_stock"] = 10  # below the Solstice Feast threshold
    ws = state.world_state["biome"]["wood_stock"]
    fs = state.world_state["biome"]["food_stock"]
    engine.tick_environment()
    assert state.world_state["biome"]["wood_stock"] == ws
    assert state.world_state["biome"]["food_stock"] == fs


def test_spring_regrows_stocks():
    state.world_state["biome"]["wood_stock"] = 50
    state.world_state["biome"]["food_stock"] = 50
    engine.tick_environment()
    assert state.world_state["biome"]["wood_stock"] == 52
    assert state.world_state["biome"]["food_stock"] == 52


def test_season_changes_with_tick():
    state.world_state["tick"] = 100
    engine.tick_environment()
    assert state.world_state["biome"]["season"] == "Summer"


def test_day_night_flips():
    state.world_state["tick"] = 10
    engine.tick_environment()
    assert state.world_state["biome"]["day"] == 0


def test_heatwave_drains_energy(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 100
    state.world_state["biome"]["weather"] = "Heatwave"
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 50
    engine.tick_environment()
    assert p["vitals"]["energy"] == 47


def test_schema_decision_supports_quote_and_monologue():
    TickResponse = schema.build_models()
    data = TickResponse.model_validate_json(
        '{"world_event": "ok", '
        '"pawn_1": {"action": "Chop", "narrative": "swings the axe", '
        '"quote": "Timber!", "inner_monologue": "I need food."}, '
        '"pawn_2": {"action": "Rest", "narrative": "rests"}}'
    )
    assert data.pawn_1.quote == "Timber!"
    assert data.pawn_1.inner_monologue == "I need food."
    assert data.pawn_2.quote is None
    assert data.pawn_2.inner_monologue is None


def test_chop_increments_trees_felled():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert p["counters"]["trees_felled"] == 1


def test_attack_increments_counters():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert p["counters"]["attacks_won"] == 1
    assert p["counters"]["damage_dealt"] >= 1


def test_share_increments_rations_shared():
    p = pawn("pawn_1")
    p["inventory"]["food"] = 5
    engine.resolve_actions({"pawn_1": ("Share", "pawn_2")})
    assert p["counters"]["rations_shared"] == 1


def test_epithet_clear_cutter(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    p = pawn("pawn_1")
    p["counters"]["trees_felled"] = 50
    engine.tick_environment()
    assert p["title"] == "the Clear-Cutter"


def test_epithet_precedence_scarred(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    p = pawn("pawn_1")
    p["counters"]["damage_dealt"] = 120
    p["counters"]["trees_felled"] = 60
    engine.tick_environment()
    assert p["title"] == "the Scarred"


def test_winter_survival_counter(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 400
    pawn("pawn_1")["born_tick"] = 399  # young enough to survive a long world
    state.world_state["biome"]["season"] = "Winter"
    engine.tick_environment()
    assert pawn("pawn_1")["counters"]["blizzards_survived"] == 1
    assert pawn("pawn_1")["title"] is None


def test_death_in_blizzard(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 300
    state.world_state["biome"]["weather"] = "Blizzard"
    state.world_state["biome"]["campfire"] = 0
    p = pawn("pawn_1")
    p["vitals"]["warmth"] = 0
    evs = engine.tick_environment()
    assert "pawn_1" not in state.world_state["pawns"]
    assert any(e["type"] == "death" for e in evs)
    entry = state.world_state["graveyard"][0]
    assert entry["id"] == "pawn_1"
    assert entry["cause"] == "froze in a blizzard"


def test_death_by_starvation(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    p = pawn("pawn_1")
    p["vitals"]["hunger"] = 0
    p["inventory"]["food"] = 0
    p["starving_ticks"] = 6
    engine.tick_environment()
    assert "pawn_1" not in state.world_state["pawns"]
    assert state.world_state["graveyard"][0]["cause"] == "starvation"


def test_graveyard_snapshot_fields(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 50
    state.world_state["biome"]["weather"] = "Blizzard"
    state.world_state["biome"]["campfire"] = 0
    p = pawn("pawn_1")
    p["vitals"]["warmth"] = 0
    p["born_tick"] = 3
    p["counters"]["trees_felled"] = 60
    p["title"] = "the Clear-Cutter"
    engine.tick_environment()
    entry = state.world_state["graveyard"][0]
    assert entry["died_tick"] == 50
    assert entry["born_tick"] == 3
    assert entry["title"] == "the Clear-Cutter"
    assert "Here lies" in entry["epitaph"]


def test_starving_ticks_reset_after_eating():
    p = pawn("pawn_1")
    p["vitals"]["hunger"] = 10
    p["inventory"]["food"] = 5
    p["starving_ticks"] = 3
    engine.tick_environment()
    assert p["starving_ticks"] == 0


def test_dead_pawn_not_recovered():
    p = pawn("pawn_1")
    p["status"] = "dead"
    p["vitals"]["hp"] = 0
    evs = engine.resolve_actions({"pawn_2": ("Rest", None)})
    assert not any(e["type"] == "recover" for e in evs)
    assert p["status"] == "dead"
    assert p["vitals"]["hp"] == 0


def test_schema_decision_supports_direction():
    TickResponse = schema.build_models()
    data = TickResponse.model_validate_json(
        '{"world_event": "ok", '
        '"pawn_1": {"action": "Move", "narrative": "heads north", "direction": "N"}, '
        '"pawn_2": {"action": "Rest", "narrative": "rests"}}'
    )
    assert data.pawn_1.direction == "N"
    assert data.pawn_2.direction is None


def test_move_changes_position():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    engine.resolve_actions({"pawn_1": ("Move", "N")})
    assert p["pos"] == [2, 1]


def test_move_requires_direction():
    p = pawn("pawn_1")
    evs = engine.resolve_actions({"pawn_1": ("Move", None)})
    assert evs[0]["type"] == "failed"
    assert p["pos"] == [2, 2]


def test_move_off_grid_fails():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    evs = engine.resolve_actions({"pawn_1": ("Move", "W")})
    assert evs[0]["type"] == "failed"
    assert p["pos"] == [0, 0]


def test_move_requires_energy():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 3
    engine.resolve_actions({"pawn_1": ("Move", "S")})
    assert p["pos"] == [2, 2]


def test_chop_requires_forest_tile():
    p = pawn("pawn_1")
    p["pos"] = [2, 2]
    before = p["inventory"]["wood"]
    evs = engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert evs[0]["type"] == "failed"
    assert p["inventory"]["wood"] == before


def test_forage_requires_meadow_or_river():
    p = pawn("pawn_1")
    p["pos"] = [2, 2]
    evs = engine.resolve_actions({"pawn_1": ("Forage", None)})
    assert evs[0]["type"] == "failed"
    assert p["inventory"]["food"] == 0


def test_build_requires_camp_tile():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["inventory"]["wood"] = 10
    evs = engine.resolve_actions({"pawn_1": ("Build", None)})
    assert evs[0]["type"] == "failed"
    assert p["inventory"]["wood"] == 10
    assert state.world_state["biome"]["shelter"] == 50


def test_attack_requires_adjacency():
    p, t = pawn("pawn_1"), pawn("pawn_2")
    p["pos"] = [0, 0]
    t["pos"] = [3, 3]
    p["vitals"]["energy"] = 100
    evs = engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert t["vitals"]["hp"] == 90


def test_share_requires_adjacency():
    p, t = pawn("pawn_1"), pawn("pawn_2")
    p["pos"] = [0, 0]
    t["pos"] = [3, 3]
    p["inventory"]["food"] = 5
    evs = engine.resolve_actions({"pawn_1": ("Share", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert t["inventory"]["food"] == 0


def test_adjacent_attack_works():
    p, t = pawn("pawn_1"), pawn("pawn_2")
    p["pos"] = [1, 1]
    t["pos"] = [2, 1]
    p["vitals"]["energy"] = 100
    before = t["vitals"]["hp"]
    engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert t["vitals"]["hp"] < before


def test_campfire_warmth_only_near_camp(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 300
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["warmth"] = 50
    engine.tick_environment()
    assert p["vitals"]["warmth"] < 50


def test_campfire_warmth_near_camp(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 300
    p = pawn("pawn_1")
    p["pos"] = [1, 2]
    p["vitals"]["warmth"] = 50
    engine.tick_environment()
    assert p["vitals"]["warmth"] > 50


def test_render_grid_shows_pawns():
    pawn("pawn_1")["pos"] = [0, 0]
    pawn("pawn_2")["pos"] = [1, 1]
    view = engine.render_grid()
    lines = view.split("\n")
    assert len(lines) == 5
    assert lines[0].startswith("[🧙]")
    assert lines[1].startswith("[🌲][🧙]")


def test_family_tree_renders_couples_kin_and_rivals():
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["relationships"]["pawn_2"] = 60
    p2["relationships"]["pawn_1"] = 60
    kid = state.make_pawn(state.next_pawn_id(), "Sprout")
    kid["mother_id"] = "pawn_2"
    kid["father_id"] = "pawn_1"
    state.world_state["pawns"][kid["id"]] = kid
    rival = state.make_pawn(state.next_pawn_id(), "Gruff")
    rival["relationships"]["pawn_1"] = -40
    p1["relationships"][rival["id"]] = -40
    state.world_state["pawns"][rival["id"]] = rival
    tree = engine.render_family_tree()
    assert "💞" in tree and "Lumberjack" in tree and "Scout" in tree
    assert "Sprout" in tree and "child of Scout & Lumberjack" in tree
    assert "💢" in tree and "Gruff" in tree


def test_family_tree_bonded_is_not_couple():
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["relationships"]["pawn_2"] = 40
    p2["relationships"]["pawn_1"] = 40
    tree = engine.render_family_tree()
    assert "💞" not in tree
    assert "🤝" in tree and "Lumberjack" in tree and "Scout" in tree


def test_family_tree_kids_make_a_couple():
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["relationships"]["pawn_2"] = 30
    p2["relationships"]["pawn_1"] = 30
    kid = state.make_pawn(state.next_pawn_id(), "Sprout")
    kid["mother_id"] = "pawn_2"
    kid["father_id"] = "pawn_1"
    state.world_state["pawns"][kid["id"]] = kid
    tree = engine.render_family_tree()
    assert "💞" in tree and "Sprout" in tree
    assert "🤝" not in tree


def test_family_tree_partners_are_couples_even_when_bond_low():
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["partners"].append("pawn_2")
    p2["partners"].append("pawn_1")
    tree = engine.render_family_tree()
    assert "💞" in tree and "🤝" not in tree


def test_family_tree_high_bond_without_partners_is_not_a_couple():
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["relationships"]["pawn_2"] = 90
    p2["relationships"]["pawn_1"] = 90
    tree = engine.render_family_tree()
    assert "💞" not in tree
    assert "🤝" in tree


def test_family_tree_empty_world():
    assert "lonely" in engine.render_family_tree()


def test_scout_ruins_rich_loot(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    p = pawn("pawn_1")
    p["pos"] = [1, 2]
    p["skills"]["scouting"] = 20
    p["vitals"]["energy"] = 100
    before = p["inventory"]["food"]
    engine.resolve_actions({"pawn_1": ("Scout", None)})
    assert p["inventory"]["food"] == before + 10


def test_scout_ruins_can_hurt(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    p = pawn("pawn_1")
    p["pos"] = [1, 2]
    p["vitals"]["energy"] = 100
    before = p["vitals"]["hp"]
    evs = engine.resolve_actions({"pawn_1": ("Scout", None)})
    assert p["vitals"]["hp"] < before
    assert evs[0]["data"].get("damage") == 3


def test_craft_warm_coat():
    p = pawn("pawn_1")
    p["inventory"]["fiber"] = 5
    evs = engine.resolve_actions({"pawn_1": ("Build", None)})
    assert any(e["type"] == "craft" and e["data"]["item"] == "Warm Coat" for e in evs)
    assert p["gear"]["body"] == "Warm Coat"
    assert p["inventory"]["fiber"] == 0


def test_craft_prioritizes_spear_over_axe():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 5
    p["inventory"]["stone"] = 3
    engine.resolve_actions({"pawn_1": ("Build", None)})
    assert p["gear"]["main_hand"] == "Flint Spear"
    assert p["inventory"]["wood"] == 3
    assert p["inventory"]["stone"] == 2


def test_craft_requires_energy():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 3
    p["inventory"]["stone"] = 2
    p["vitals"]["energy"] = 5
    evs = engine.resolve_actions({"pawn_1": ("Build", None)})
    assert evs[0]["type"] == "failed"
    assert p["gear"]["main_hand"] is None


def test_axe_doubles_chop_yield(monkeypatch):
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["skills"]["woodcutting"] = 20
    p["vitals"]["energy"] = 100
    p["gear"]["main_hand"] = "Stone Axe"
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert p["inventory"]["wood"] == 18


def test_spear_adds_attack_damage():
    p, t = pawn("pawn_1"), pawn("pawn_2")
    p["vitals"]["energy"] = 100
    p["skills"]["combat"] = 20
    p["gear"]["main_hand"] = "Flint Spear"
    t["skills"]["combat"] = 0
    t["vitals"]["hp"] = 100
    engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert t["vitals"]["hp"] == 81


def test_warm_coat_reduces_cold(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 300
    state.world_state["biome"]["weather"] = "Snow"
    state.world_state["biome"]["campfire"] = 0
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["gear"]["body"] = "Warm Coat"
    p1["vitals"]["warmth"] = 50
    p2["vitals"]["warmth"] = 50
    engine.tick_environment()
    assert p1["vitals"]["warmth"] == 45
    assert p2["vitals"]["warmth"] == 41


def test_inspired_bonus_yields_more(monkeypatch):
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["skills"]["woodcutting"] = 20
    p["vitals"]["energy"] = 100
    p["gear"]["main_hand"] = "Stone Axe"
    p["vitals"]["morale"] = 95
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert p["inventory"]["wood"] == 19


def test_stone_from_quarry(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    p = pawn("pawn_1")
    p["pos"] = [2, 1]
    p["skills"]["scouting"] = 20
    p["vitals"]["energy"] = 100
    engine.resolve_actions({"pawn_1": ("Scout", None)})
    assert p["inventory"]["stone"] == 5


def test_fiber_from_meadow(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    p = pawn("pawn_1")
    p["pos"] = [1, 1]
    p["skills"]["scouting"] = 20
    p["vitals"]["energy"] = 100
    engine.resolve_actions({"pawn_1": ("Forage", None)})
    assert p["inventory"]["fiber"] == 1
    assert p["inventory"]["food"] == 7


def test_mental_break_starts_at_morale_zero(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 10
    state.world_state["biome"]["campfire"] = 0
    p = pawn("pawn_1")
    p["vitals"]["morale"] = 0
    p["vitals"]["warmth"] = 10
    p["vitals"]["hunger"] = 0
    p["inventory"]["food"] = 0
    evs = engine.tick_environment()
    assert p["mental_break"] == "berserk"
    assert p["break_ticks"] == 3
    assert any(e["type"] == "break" for e in evs)


def test_break_berserk_attacks_nearest():
    p, t = pawn("pawn_1"), pawn("pawn_2")
    p["mental_break"] = "berserk"
    p["break_ticks"] = 2
    evs = engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert any(e["type"] == "break" for e in evs)
    assert t["vitals"]["hp"] < 90


def test_break_paranoid_hoards_food():
    p = pawn("pawn_1")
    p["mental_break"] = "paranoid"
    p["break_ticks"] = 2
    p["inventory"]["food"] = 5
    evs = engine.resolve_actions({"pawn_1": ("Forage", None)})
    assert p["inventory"]["food"] == 3
    assert any(e["type"] == "break" for e in evs)


def test_break_apathetic_wanders():
    p = pawn("pawn_1")
    p["mental_break"] = "apathetic"
    p["break_ticks"] = 2
    engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert p["pos"] != [2, 2]


def test_break_ends_after_ticks(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    p = pawn("pawn_1")
    p["traits"] = []
    p["mental_break"] = "paranoid"
    p["break_ticks"] = 1
    p["vitals"]["morale"] = 30
    evs = engine.tick_environment()
    assert p["mental_break"] is None
    assert p["break_ticks"] == 0
    assert p["vitals"]["morale"] == 54
    assert any(e["type"] == "break_end" for e in evs)


def test_mate_requires_target():
    evs = engine.resolve_actions({"pawn_1": ("Mate", None)})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "no_target"


def test_mate_same_sex_rejected():
    pawn("pawn_2")["sex"] = "M"
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "same_sex"


def test_mate_requires_bond():
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "relationship_too_low"


def test_mate_requires_mutual_relationship():
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 0
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "relationship_too_low"


def test_mate_mutual_relationship_succeeds(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "mate"
    assert evs[0]["data"]["conceived"] is True


def test_relationship_decay_once_per_day():
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["relationships"]["pawn_2"] = 50
    p2["relationships"]["pawn_1"] = -40
    state.world_state["tick"] = 15  # night: no decay
    state.world_state["biome"]["day"] = 1
    engine.tick_environment()
    assert p1["relationships"]["pawn_2"] == 50
    state.world_state["tick"] = 25  # dawn of the next day
    state.world_state["biome"]["day"] = 0
    engine.tick_environment()
    assert p1["relationships"]["pawn_2"] == 45
    assert p2["relationships"]["pawn_1"] == -35


def test_mate_requires_same_tile():
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["pos"] = [2, 1]
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "not_same_tile"


def test_mate_mother_starving_rejected():
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    pawn("pawn_2")["starving_ticks"] = 2
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "mother_starving"


def test_mate_child_suitor_rejected():
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_1")["child_ticks"] = 1
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "too_young"
    assert pawn("pawn_2")["pregnant_ticks"] == 0


def test_mate_child_target_rejected():
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["child_ticks"] = 1
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "too_young"
    assert pawn("pawn_2")["pregnant_ticks"] == 0


def test_mate_energy_cost_enforced():
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    pawn("pawn_1")["vitals"]["energy"] = 5
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "low_energy"
    assert pawn("pawn_2")["pregnant_ticks"] == 0


def test_mate_conceives(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "mate"
    assert evs[0]["data"]["conceived"] is True
    assert pawn("pawn_2")["pregnant_ticks"] == engine.PREGNANCY_TICKS
    assert pawn("pawn_1")["vitals"]["energy"] == 70


def test_mate_without_conception(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "mate"
    assert evs[0]["data"]["conceived"] is False
    assert pawn("pawn_2")["pregnant_ticks"] == 0


def test_conception_pins_father(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert pawn("pawn_2")["partner_id"] == "pawn_1"


def test_mate_success_records_partners():
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert "pawn_2" in pawn("pawn_1")["partners"]
    assert "pawn_1" in pawn("pawn_2")["partners"]


def test_mate_partners_skip_bond_gate(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["partners"].append("pawn_2")
    p2["partners"].append("pawn_1")
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "mate"
    assert evs[0]["data"]["conceived"] is True


def test_mate_polygamy_allowed(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    p3 = state.make_pawn("pawn_3", "Tertia", sex="F")
    state.world_state["pawns"]["pawn_3"] = p3
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    pawn("pawn_1")["relationships"]["pawn_3"] = 30
    pawn("pawn_3")["relationships"]["pawn_1"] = 30
    engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    engine.resolve_actions({"pawn_1": ("Mate", "pawn_3")})
    assert pawn("pawn_1")["partners"] == ["pawn_2", "pawn_3"]


def test_kill_clears_partners():
    p1, p2 = pawn("pawn_1"), pawn("pawn_2")
    p1["partners"].append("pawn_2")
    p2["partners"].append("pawn_1")
    engine._kill("pawn_2", p2, "test")
    assert "pawn_2" not in pawn("pawn_1")["partners"]


def test_mate_blocked_for_siblings():
    pawn("pawn_1")["father_id"] = "dad"
    pawn("pawn_2")["father_id"] = "dad"
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "too_close_kin"
    assert pawn("pawn_2")["pregnant_ticks"] == 0


def test_mate_blocked_parent_child():
    pawn("pawn_2")["father_id"] = "pawn_1"
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "too_close_kin"


def test_unrelated_pawns_can_mate():
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "mate"


def test_pregnancy_leads_to_birth():
    mother = pawn("pawn_2")
    mother["pregnant_ticks"] = 1
    before = len(state.world_state["pawns"])
    evs = engine.tick_environment()
    assert len(state.world_state["pawns"]) == before + 1
    assert any(e["type"] == "birth" for e in evs)
    newborn = [p for p in state.world_state["pawns"].values() if p["id"] != "pawn_1" and p["id"] != "pawn_2"]
    assert len(newborn) == 1
    assert newborn[0]["pos"] == list(mother["pos"])
    assert newborn[0]["child_ticks"] == engine.CHILD_MATURITY
    assert newborn[0]["vitals"]["hp"] == engine.NEWBORN_HP
    assert newborn[0]["vitals"]["energy"] == engine.NEWBORN_ENERGY


def test_birth_records_parents():
    mother = pawn("pawn_2")
    mother["pregnant_ticks"] = 1
    mother["partner_id"] = "pawn_1"
    engine.tick_environment()
    newborn = [p for p in state.world_state["pawns"].values() if p["id"] not in ("pawn_1", "pawn_2")]
    assert len(newborn) == 1
    assert newborn[0]["mother_id"] == "pawn_2"
    assert newborn[0]["father_id"] == "pawn_1"
    assert mother["partner_id"] is None
    assert engine.lineage_label(newborn[0]) == "child of Scout & Lumberjack"


def test_birth_keeps_father_through_delay():
    while len(state.world_state["pawns"]) < engine.MAX_PAWNS:
        pid = state.next_pawn_id()
        state.world_state["pawns"][pid] = state.make_pawn(pid, f"Extra_{pid}")
    mother = pawn("pawn_2")
    mother["pregnant_ticks"] = 1
    mother["partner_id"] = "pawn_1"
    engine.tick_environment()
    assert mother["pregnant_ticks"] == engine.PREGNANCY_TICKS
    assert mother["partner_id"] == "pawn_1"
    state.world_state["pawns"].popitem()
    mother["pregnant_ticks"] = 1
    engine.tick_environment()
    kids = [p for p in state.world_state["pawns"].values() if p.get("mother_id") == "pawn_2"]
    assert len(kids) == 1
    assert kids[0]["father_id"] == "pawn_1"


def test_birth_blocked_at_population_cap():
    while len(state.world_state["pawns"]) < engine.MAX_PAWNS:
        pid = state.next_pawn_id()
        state.world_state["pawns"][pid] = state.make_pawn(pid, f"Extra_{pid}")
    mother = pawn("pawn_2")
    mother["pregnant_ticks"] = 1
    before = len(state.world_state["pawns"])
    evs = engine.tick_environment()
    assert len(state.world_state["pawns"]) == before
    birth = [e for e in evs if e["type"] == "birth"]
    assert birth and birth[0]["data"]["delivered"] is False
    assert mother["pregnant_ticks"] == engine.PREGNANCY_TICKS


def test_birth_delivered_after_slot_frees():
    while len(state.world_state["pawns"]) < engine.MAX_PAWNS:
        pid = state.next_pawn_id()
        state.world_state["pawns"][pid] = state.make_pawn(pid, f"Extra_{pid}")
    mother = pawn("pawn_2")
    mother["pregnant_ticks"] = 1
    engine.tick_environment()
    assert mother["pregnant_ticks"] == engine.PREGNANCY_TICKS
    state.world_state["pawns"].popitem()
    mother["pregnant_ticks"] = 1
    evs = engine.tick_environment()
    assert len(state.world_state["pawns"]) == engine.MAX_PAWNS
    birth = [e for e in evs if e["type"] == "birth"]
    assert birth and birth[0]["data"]["child"] in state.world_state["pawns"]


def test_mate_blocked_at_population_cap(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    while len(state.world_state["pawns"]) < engine.MAX_PAWNS:
        pid = state.next_pawn_id()
        state.world_state["pawns"][pid] = state.make_pawn(pid, f"Extra_{pid}")
    pawn("pawn_1")["relationships"]["pawn_2"] = 30
    pawn("pawn_2")["relationships"]["pawn_1"] = 30
    evs = engine.resolve_actions({"pawn_1": ("Mate", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "population_cap"


def test_child_matures_over_ticks():
    p = pawn("pawn_1")
    p["child_ticks"] = 1
    engine.tick_environment()
    assert p["child_ticks"] == 0


def test_age_of():
    assert engine.age_of(pawn("pawn_1")) == 0
    pawn("pawn_1")["born_tick"] = -10
    assert engine.age_of(pawn("pawn_1")) == 11


def test_is_elder_threshold():
    p = pawn("pawn_1")
    p["born_tick"] = 1 - engine.ELDER_AGE + 1
    assert not engine.is_elder(p)
    p["born_tick"] = 1 - engine.ELDER_AGE
    assert engine.is_elder(p)


def test_elder_energy_and_morale_tax():
    biome = state.world_state["biome"]
    result = []
    young = pawn("pawn_1")
    young["traits"] = []
    elder = state.make_pawn("pawn_9", "Old", hp=100, energy=80, traits=[])
    elder["born_tick"] = 1 - engine.ELDER_AGE
    state.world_state["pawns"]["pawn_9"] = elder
    engine._metabolize(young, "pawn_1", biome, lit=False, day=1, result=result)
    engine._metabolize(elder, "pawn_9", biome, lit=False, day=1, result=result)
    assert elder["vitals"]["energy"] == young["vitals"]["energy"] - engine.ELDER_ENERGY_TAX
    assert elder["vitals"]["morale"] == young["vitals"]["morale"] - engine.ELDER_MORALE_TAX


def test_elder_rest_recovery_penalty():
    p = pawn("pawn_1")
    p["vitals"]["hp"] = 50
    p["born_tick"] = 1 - engine.ELDER_AGE
    engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert p["vitals"]["hp"] == 50 + engine.RECOVER_HEAL - engine.ELDER_REST_PENALTY


def test_no_age_death_before_elder():
    p = pawn("pawn_1")
    p["born_tick"] = 1 - engine.ELDER_AGE + 1
    engine.tick_environment()
    assert "pawn_1" in state.world_state["pawns"]
    assert all(e.get("data", {}).get("cause") != "old age" for e in state.world_state["history"])


def test_old_age_hard_cap_death():
    p = pawn("pawn_1")
    p["born_tick"] = 1 - engine.OLD_AGE_MAX
    evs = engine.tick_environment()
    assert "pawn_1" not in state.world_state["pawns"]
    death = [e for e in evs if e["type"] == "death" and e["actor"] == "pawn_1"]
    assert death and death[0]["data"]["cause"] == "old age"
    entry = state.world_state["graveyard"][-1]
    assert entry["id"] == "pawn_1"
    assert entry["cause"] == "old age"


def test_elder_random_death_chance(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    p = pawn("pawn_1")
    p["born_tick"] = 1 - engine.ELDER_AGE
    evs = engine.tick_environment()
    assert "pawn_1" not in state.world_state["pawns"]
    assert any(
        e["type"] == "death" and e.get("data", {}).get("cause") == "old age" for e in evs
    )


def test_elder_gets_ancient_title(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    p = pawn("pawn_1")
    p["born_tick"] = 1 - engine.ELDER_AGE
    engine.tick_environment()
    assert p["title"] == "the Ancient"


def test_break_archetype_defaults():
    p = pawn("pawn_1")
    p["personality"] = {"bravery": 2}
    assert engine._break_archetype(p) == "paranoid"
    p["personality"] = {"aggression": 7}
    assert engine._break_archetype(p) == "berserk"
    p["personality"] = {}
    assert engine._break_archetype(p) == "apathetic"


def test_load_state_preserves_extinction(monkeypatch, tmp_path):
    state.world_state["pawns"] = {}
    state.world_state["graveyard"] = [
        {"id": "pawn_1", "name": "Lumberjack", "cause": "old age", "died_tick": 10}
    ]
    state.world_state["extinct"] = True
    f = tmp_path / "state.json"
    f.write_text(json.dumps(state.world_state), encoding="utf-8")
    monkeypatch.setattr(state, "STATE_FILE", str(f))
    state.load_state()
    assert state.world_state["pawns"] == {}
    assert state.world_state["extinct"] is True
    assert len(state.world_state["graveyard"]) == 1


def test_load_state_respawns_fresh_when_empty_and_no_graveyard(monkeypatch, tmp_path):
    state.world_state["pawns"] = {}
    state.world_state["graveyard"] = []
    f = tmp_path / "state.json"
    f.write_text(json.dumps(state.world_state), encoding="utf-8")
    monkeypatch.setattr(state, "STATE_FILE", str(f))
    state.load_state()
    assert len(state.world_state["pawns"]) == 2


def test_schema_has_interact_and_goal_fields():
    assert "Interact" in schema.ACTIONS
    assert "Interact" in engine.ACTIONS
    tick_model = schema.build_models()
    agent = tick_model.model_fields["pawn_1"].annotation
    assert "flavor" in agent.model_fields
    assert "new_goal" in agent.model_fields


def test_interact_social_boosts_morale_and_relationship():
    p, t = pawn("pawn_1"), pawn("pawn_2")
    p["pos"] = t["pos"] = [2, 2]
    evs = engine.resolve_actions({"pawn_1": ("Interact", None, "talking")})
    assert evs[0]["type"] == "interact"
    assert p["vitals"]["morale"] == 85
    assert p["relationships"]["pawn_2"] > 0
    assert t["relationships"]["pawn_1"] > 0


def test_interact_gather_food_on_meadow():
    p = pawn("pawn_1")
    p["pos"] = [1, 1]
    before = p["inventory"]["food"]
    evs = engine.resolve_actions({"pawn_1": ("Interact", None, "fishing")})
    assert evs[0]["type"] == "interact"
    assert p["inventory"]["food"] > before


def test_interact_gather_wood_on_forest():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    before = p["inventory"]["wood"]
    evs = engine.resolve_actions({"pawn_1": ("Interact", None, "gathering")})
    assert evs[0]["type"] == "interact"
    assert p["inventory"]["wood"] > before


def test_interact_unknown_verb_lifts_morale():
    p = pawn("pawn_1")
    p["traits"] = []
    before = p["vitals"]["morale"]
    evs = engine.resolve_actions({"pawn_1": ("Interact", None, "fiddling")})
    assert evs[0]["type"] == "interact"
    assert p["vitals"]["morale"] == before + 3


def test_interact_low_energy_fails():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 3
    evs = engine.resolve_actions({"pawn_1": ("Interact", None, "dancing")})
    assert evs[0]["type"] == "failed"


def test_goal_adopted_from_new_goal():
    p = pawn("pawn_1")
    engine.resolve_actions({"pawn_1": ("Rest", None, None, "gather 10 wood")})
    g = p["goal"]
    assert g["kind"] == "gather"
    assert g["resource"] == "wood"
    assert g["needed"] == 10
    assert g["progress"] == 0


def test_goal_kept_when_already_held():
    p = pawn("pawn_1")
    p["goal"] = {"kind": "survive", "needed": 20, "progress": 0, "text": "survive 1 day"}
    engine.resolve_actions({"pawn_1": ("Rest", None, None, "gather 10 wood")})
    assert p["goal"]["kind"] == "survive"


def test_goal_completes_on_gather():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["goal"] = {"kind": "gather", "resource": "wood", "needed": 3, "progress": 0, "text": "gather 3 wood"}
    before = p["vitals"]["morale"]
    evs = engine.resolve_actions({"pawn_1": ("Chop", None)})
    types = [e["type"] for e in evs]
    assert "goal" in types
    assert p["goal"] is None
    assert p["vitals"]["morale"] == before + 15


def test_goal_social_advances_on_share():
    p = pawn("pawn_1")
    p["goal"] = {"kind": "social", "target_id": "pawn_2", "needed": 2, "progress": 0, "text": "befriend Scout"}
    p["inventory"]["food"] = 5
    engine.resolve_actions({"pawn_1": ("Share", "pawn_2")})
    assert p["goal"]["progress"] == 1
    engine.resolve_actions({"pawn_1": ("Share", "pawn_2")})
    assert p["goal"] is None


def test_goal_survive_ticks_in_environment():
    p = pawn("pawn_1")
    p["goal"] = {"kind": "survive", "needed": 3, "progress": 0, "text": "survive 3 days"}
    engine.tick_environment()
    assert p["goal"]["progress"] == 1
    engine.tick_environment()
    evs = engine.tick_environment()
    assert "goal" in [e["type"] for e in evs]
    assert p["goal"] is None


def test_migrate_pawn_keeps_goal():
    goal = {"kind": "gather", "resource": "wood", "needed": 10, "progress": 3, "text": "gather 10 wood"}
    out = state._migrate_pawn("p1", {"name": "A", "goal": goal})
    assert out["goal"] == goal
    out = state._migrate_pawn("p2", {"name": "B"})
    assert out["goal"] is None


def test_migrate_pawn_keeps_lineage():
    out = state._migrate_pawn(
        "p1",
        {"name": "A", "mother_id": "m", "father_id": "f", "partner_id": "x", "partners": ["q", "r"]},
    )
    assert out["mother_id"] == "m"
    assert out["father_id"] == "f"
    assert out["partner_id"] == "x"
    assert out["partners"] == ["q", "r"]
    out = state._migrate_pawn("p2", {"name": "B"})
    assert out["mother_id"] is None
    assert out["father_id"] is None
    assert out["partner_id"] is None
    assert out["partners"] == []

