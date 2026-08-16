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


def animal_by_id(aid):
    return next(w for w in state.world_state["wildlife"] if w["id"] == aid)


def test_wildlife_spawns_in_spring(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = 1
    evs = engine.tick_environment()
    assert len(state.world_state["wildlife"]) == 1
    a = state.world_state["wildlife"][0]
    assert a["species"] in engine.PREY_SPECIES
    assert a["pos"] == [0, 0]
    assert a["hp"] == engine.WILDLIFE[a["species"]]["hp"]
    assert a["state"] == "wandering"
    assert any(e["type"] == "wildlife" for e in evs)


def test_wildlife_spawn_is_capped(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.15)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = 1
    # A wild predator in the world keeps prey under normal predator pressure
    # (Stage 15 trophic cascade: prey only overpopulate when no predator hunts).
    state.world_state["wildlife"].append(state.make_animal("Wolf", pos=[0, 0], hp=40))
    for _ in range(engine.WILDLIFE_MAX):
        engine.tick_environment()
    assert len(state.world_state["wildlife"]) == engine.WILDLIFE_MAX
    # Cap reached: one more tick must not add a fourth.
    engine.tick_environment()
    assert len(state.world_state["wildlife"]) == engine.WILDLIFE_MAX


def test_predator_spawns_in_winter(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = 300  # Winter
    state.world_state["biome"]["palisade"] = 0
    engine.tick_environment()
    a = state.world_state["wildlife"][0]
    assert a["species"] in engine.PREDATOR_SPECIES


def test_palisade_reduces_predator_spawn(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.2)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = 300  # Winter
    # With no palisade, 0.2 < 0.25 → spawns.
    state.world_state["biome"]["palisade"] = 0
    engine.tick_environment()
    assert len(state.world_state["wildlife"]) == 1
    # With a level-2 palisade, chance = 0.25 * (1 - 0.6) = 0.10; 0.2 >= 0.10 → no spawn.
    state.world_state["wildlife"] = []
    state.world_state["biome"]["palisade"] = 2
    state.world_state["biome"]["season"] = "Winter"  # keep the season constant
    state.world_state["biome"]["weather"] = "Clear"
    engine.tick_environment()
    assert len(state.world_state["wildlife"]) == 0


def test_predators_despawn_at_season_change(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 100  # Winter→Summer boundary
    state.world_state["biome"]["season"] = "Winter"
    wolf = state.make_animal("Wolf", pos=[4, 4])
    wolf["hp"] = engine.WILDLIFE["Wolf"]["hp"]
    state.world_state["wildlife"].append(wolf)
    evs = engine.tick_environment()
    assert len(state.world_state["wildlife"]) == 0
    assert any(e["type"] == "wildlife_despawn" for e in evs)


def test_prey_flees_nearest_pawn(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.9)
    deer = state.make_animal("Deer", pos=[3, 3])
    deer["hp"] = engine.WILDLIFE["Deer"]["hp"]
    state.world_state["wildlife"].append(deer)
    pawn("pawn_2")["pos"] = [4, 3]  # distance 1 from the deer
    engine.tick_environment()
    # deer should move to a tile farther from pawn_2: (3,2) over (3,4) (N before S).
    assert deer["pos"] == [3, 2]


def test_predator_stalks_furthest_from_camp(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.9)
    wolf = state.make_animal("Wolf", pos=[0, 0])
    wolf["hp"] = engine.WILDLIFE["Wolf"]["hp"]
    state.world_state["wildlife"].append(wolf)
    pawn("pawn_1")["pos"] = [2, 2]  # at camp, distance 0
    pawn("pawn_2")["pos"] = [4, 4]  # furthest from camp
    engine.tick_environment()
    # wolf moves from (0,0) toward (4,4): N invalid, S=(0,1) first improving step.
    assert wolf["pos"] == [0, 1]


def test_predator_bite_incapacitates_never_kills(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.9)
    wolf = state.make_animal("Wolf", pos=[4, 4])
    wolf["hp"] = engine.WILDLIFE["Wolf"]["hp"]
    state.world_state["wildlife"].append(wolf)
    pawn("pawn_2")["pos"] = [4, 4]
    pawn("pawn_2")["vitals"]["hp"] = 5  # bite is 8
    engine.tick_environment()
    assert "pawn_2" in state.world_state["pawns"]
    assert pawn("pawn_2")["vitals"]["hp"] == 0
    assert pawn("pawn_2")["status"] == "incapacitated"
    assert any(e["type"] == "bite" for e in state.world_state["history"])


def test_hunt_yields_food_and_fiber():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    deer = state.make_animal("Deer", pos=[1, 0])
    deer["hp"] = 1  # one shot
    state.world_state["wildlife"].append(deer)
    evs = engine.resolve_actions({"pawn_1": ("Attack", "wild_1")})
    assert not state.world_state["wildlife"]
    assert p["inventory"]["food"] == engine.WILDLIFE["Deer"]["food_yield"]
    assert p["inventory"]["fiber"] == engine.WILDLIFE["Deer"]["fiber_yield"]
    assert any(e["type"] == "hunt" for e in evs)


def test_hunt_wounded_prey_flees(monkeypatch):
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    p["skills"]["combat"] = 0
    deer = state.make_animal("Deer", pos=[1, 0])
    deer["hp"] = 40
    state.world_state["wildlife"].append(deer)
    evs = engine.resolve_actions({"pawn_1": ("Attack", "wild_1")})
    assert len(state.world_state["wildlife"]) == 1
    assert deer["pos"] != [1, 0]
    assert any(e["type"] == "attack" for e in evs)
    assert any(e["data"].get("species") == "Deer" for e in evs)


def test_hunt_surviving_predator_retaliates():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    p["skills"]["combat"] = 0
    p["vitals"]["hp"] = 100
    wolf = state.make_animal("Wolf", pos=[1, 0])
    wolf["hp"] = 50
    state.world_state["wildlife"].append(wolf)
    evs = engine.resolve_actions({"pawn_1": ("Attack", "wild_1")})
    assert wolf["hp"] > 0
    assert p["vitals"]["hp"] < 100
    assert any(e["type"] == "attack" and e["data"].get("bite") for e in evs)
    assert "pawn_1" in state.world_state["pawns"]  # not killed


def test_hunt_requires_adjacency():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    deer = state.make_animal("Deer", pos=[4, 4])
    state.world_state["wildlife"].append(deer)
    evs = engine.resolve_actions({"pawn_1": ("Attack", "wild_1")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "too_far"


def test_attack_unknown_wildlife_id_fails():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    evs = engine.resolve_actions({"pawn_1": ("Attack", "wild_9")})
    assert evs[0]["type"] == "failed"


def test_pacifist_refuses_hunt(monkeypatch):
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    p["traits"] = ["Pacifist"]
    deer = state.make_animal("Deer", pos=[1, 0])
    state.world_state["wildlife"].append(deer)
    evs = engine.resolve_actions({"pawn_1": ("Attack", "wild_1")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "pacifist"
    assert len(state.world_state["wildlife"]) == 1


def test_tame_succeeds_high_skill(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    p = pawn("pawn_1")
    p["pos"] = [1, 1]
    p["vitals"]["energy"] = 100
    p["skills"]["scouting"] = 20  # chance = 0.5 + 0.4 = 0.9
    deer = state.make_animal("Deer", pos=[1, 1])
    state.world_state["wildlife"].append(deer)
    evs = engine.resolve_actions({"pawn_1": ("Interact", "wild_1", "tame")})
    assert any(e["type"] == "tame" for e in evs)
    assert deer["state"] == "tamed"
    assert deer["tamed_by"] == "pawn_1"
    assert deer["pos"] == [2, 2]


def test_tame_fails_low_skill(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    p = pawn("pawn_1")
    p["pos"] = [1, 1]
    p["vitals"]["energy"] = 100
    p["skills"]["scouting"] = 0  # chance = 0.5
    deer = state.make_animal("Deer", pos=[1, 1])
    state.world_state["wildlife"].append(deer)
    evs = engine.resolve_actions({"pawn_1": ("Interact", "wild_1", "tame")})
    assert not any(e["type"] == "tame" for e in evs)
    assert deer["state"] == "wandering"


def test_tame_requires_same_tile(monkeypatch):
    p = pawn("pawn_1")
    p["pos"] = [1, 1]
    p["vitals"]["energy"] = 100
    deer = state.make_animal("Deer", pos=[4, 4])
    state.world_state["wildlife"].append(deer)
    evs = engine.resolve_actions({"pawn_1": ("Interact", "wild_1", "tame")})
    assert not any(e["type"] == "tame" for e in evs)
    assert deer["state"] == "wandering"


def test_pet_grants_camp_morale_bonus():
    result = []
    biome = state.world_state["biome"]
    a = pawn("pawn_1")
    b = pawn("pawn_2")
    a["traits"] = []
    b["traits"] = []
    # metabolize a pawn with no pet yet
    engine._metabolize(b, "pawn_2", biome, lit=False, day=1, result=result)
    b_morale = b["vitals"]["morale"]
    # now add a tamed pet; both pawns would gain the bonus, but a gets it fresh
    pet = state.make_animal("Deer")
    pet["state"] = "tamed"
    state.world_state["wildlife"].append(pet)
    engine._metabolize(a, "pawn_1", biome, lit=False, day=1, result=result)
    assert a["vitals"]["morale"] == b_morale + engine.PET_MORALE_BONUS


def test_granary_stops_summer_food_decay(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 100  # Summer
    state.world_state["biome"]["season"] = "Summer"
    state.world_state["biome"]["food_stock"] = 60
    state.world_state["biome"]["granary"] = False
    engine.tick_environment()
    # regrowth +1, Summer decay -2 → 59
    assert state.world_state["biome"]["food_stock"] == 59


def test_granary_preserves_food(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 100  # Summer
    state.world_state["biome"]["season"] = "Summer"
    state.world_state["biome"]["food_stock"] = 60
    state.world_state["biome"]["granary"] = True
    engine.tick_environment()
    # regrowth +1, no decay → 61
    assert state.world_state["biome"]["food_stock"] == 61


def test_build_granary_after_infra_maxed():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 10
    state.world_state["biome"]["shelter"] = 100
    state.world_state["biome"]["campfire"] = 100
    state.world_state["biome"]["granary"] = False
    evs = engine.resolve_actions({"pawn_1": ("Build", None)})
    assert state.world_state["biome"]["granary"] is True
    assert p["inventory"]["wood"] == 5
    assert any(e["data"]["structure"] == "granary" for e in evs)


def test_build_palisade_upgrades():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 12
    biome = state.world_state["biome"]
    biome["shelter"] = 100
    biome["campfire"] = 100
    biome["granary"] = True
    biome["palisade"] = 0
    evs = engine.resolve_actions({"pawn_1": ("Build", None)})
    assert biome["palisade"] == 1
    assert p["inventory"]["wood"] == 7
    assert any(e["data"]["structure"] == "palisade" for e in evs)


def test_build_palisade_capped():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 100
    p["inventory"]["stone"] = 20
    p["gear"]["main_hand"] = "Flint Spear"
    biome = state.world_state["biome"]
    biome["shelter"] = 100
    biome["campfire"] = 100
    biome["granary"] = True
    biome["palisade"] = engine.PALISADE_MAX
    evs = engine.resolve_actions({"pawn_1": ("Build", None)})
    assert biome["palisade"] == engine.PALISADE_MAX
    # Once fully fortified, Build raises the Ancestral Monolith (Stage 6).
    assert state.world_state["monument"]["wood"] == 5
    assert any(e["data"]["structure"] == "monument" for e in evs)


def test_render_grid_shows_wildlife():
    deer = state.make_animal("Deer", pos=[0, 0])
    state.world_state["wildlife"].append(deer)
    view = engine.render_grid()
    lines = view.split("\n")
    assert lines[0].startswith("[🦌]")


def test_render_grid_shows_wildlife_and_pawn():
    deer = state.make_animal("Deer", pos=[0, 0])
    state.world_state["wildlife"].append(deer)
    pawn("pawn_1")["pos"] = [0, 0]
    view = engine.render_grid()
    assert view.split("\n")[0].startswith("[🧙🦌]")


def test_schema_target_includes_wildlife_ids():
    deer = state.make_animal("Deer", pos=[0, 0])
    state.world_state["wildlife"].append(deer)
    TickResponse = schema.build_models()
    data = TickResponse.model_validate_json(
        '{"world_event": "ok", '
        '"pawn_1": {"action": "Attack", "narrative": "hunts", "target": "wild_1"}, '
        '"pawn_2": {"action": "Rest", "narrative": "rests"}}'
    )
    assert data.pawn_1.target == "wild_1"


def test_migrate_old_world_without_wildlife(monkeypatch, tmp_path):
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
    state.world_state["wildlife"] = []
    state.save_state()
    state.load_state()
    assert state.world_state["wildlife"] == []
    assert state.world_state["biome"]["granary"] is False
    assert state.world_state["biome"]["palisade"] == 0


def test_tamed_pet_despawn_at_season_change_kept(monkeypatch):
    # Tamed pets are NOT removed by predators-despawn-at-season-change.
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 100
    state.world_state["biome"]["season"] = "Winter"
    pet = state.make_animal("Deer", pos=[2, 2])
    pet["state"] = "tamed"
    pet["tamed_by"] = "pawn_1"
    state.world_state["wildlife"].append(pet)
    engine.tick_environment()
    assert len(state.world_state["wildlife"]) == 1
    assert state.world_state["wildlife"][0]["state"] == "tamed"


def test_empty_wildlife_when_world_extinct():
    state.world_state["pawns"] = {}
    wolf = state.make_animal("Wolf", pos=[4, 4])
    state.world_state["wildlife"].append(wolf)
    engine.tick_environment()
    assert state.world_state["wildlife"] == []


def test_prey_despawn_chance(monkeypatch):
    vals = iter([0.9, 0.0, 0.9])  # no spawn, prey despawn roll, no weather change
    monkeypatch.setattr(random, "random", lambda: next(vals))
    state.world_state["tick"] = 20
    deer = state.make_animal("Deer", pos=[4, 4])
    deer["spawn_tick"] = 1
    state.world_state["wildlife"].append(deer)
    evs = engine.tick_environment()
    assert len(state.world_state["wildlife"]) == 0
    assert any(e["type"] == "wildlife_despawn" for e in evs)


def test_freshly_spawned_prey_not_immediately_despawned(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    state.world_state["tick"] = 1
    engine.tick_environment()
    assert len(state.world_state["wildlife"]) == 1


def test_tamed_pet_never_despawns(monkeypatch):
    vals = iter([0.9, 0.0, 0.9])  # no spawn, despawn roll (ignored for tamed), no weather change
    monkeypatch.setattr(random, "random", lambda: next(vals))
    state.world_state["tick"] = 20
    pet = state.make_animal("Deer", pos=[2, 2])
    pet["spawn_tick"] = 1
    pet["state"] = "tamed"
    pet["tamed_by"] = "pawn_1"
    state.world_state["wildlife"].append(pet)
    engine.tick_environment()
    assert len(state.world_state["wildlife"]) == 1
