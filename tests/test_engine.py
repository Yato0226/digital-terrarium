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
    p["mental_break"] = "paranoid"
    p["break_ticks"] = 1
    p["vitals"]["morale"] = 30
    evs = engine.tick_environment()
    assert p["mental_break"] is None
    assert p["break_ticks"] == 0
    assert p["vitals"]["morale"] == 54
    assert any(e["type"] == "break_end" for e in evs)
