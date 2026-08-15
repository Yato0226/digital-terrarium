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


def raiders():
    return state.world_state.get("raiders", [])


def make_raider(pos):
    r = state.make_raider(pos)
    state.world_state.setdefault("raiders", []).append(r)
    return r


def move_pawns_off_camp():
    for p in state.world_state["pawns"].values():
        p["pos"] = [1, 1]


# --- Spawning ---------------------------------------------------------------


def test_autumn_raid_spawns_when_wealthy():
    state.world_state["tick"] = 200  # Autumn (200 // 100 % 4 == 2)
    state.world_state["biome"]["food_stock"] = 20
    pawn("pawn_1")["inventory"]["wood"] = 15
    history_len = len(state.world_state["history"])
    engine.tick_environment()
    assert len(raiders()) in (1, 2)
    for r in raiders():
        assert r["id"].startswith("scavenger_")
        x, y = r["pos"]
        assert 0 <= x < engine.GRID_SIZE and 0 <= y < engine.GRID_SIZE
        assert r["state"] in ("marching", "fleeing")
    new_events = state.world_state["history"][history_len:]
    assert any(e["type"] == "raid" for e in new_events)


def test_no_raid_when_colony_poor():
    state.world_state["tick"] = 200
    state.world_state["biome"]["food_stock"] = 5
    for p in state.world_state["pawns"].values():
        p["inventory"]["wood"] = 0
        p["inventory"]["food"] = 0
    engine.tick_environment()
    assert raiders() == []


def test_no_raid_outside_autumn():
    state.world_state["tick"] = 100  # Summer (100 // 100 % 4 == 1)
    state.world_state["biome"]["food_stock"] = 40
    engine.tick_environment()
    assert raiders() == []


def test_no_second_raid_while_raiders_present():
    state.world_state["tick"] = 200
    state.world_state["biome"]["food_stock"] = 40
    make_raider([0, 0])
    engine.tick_environment()
    assert len(raiders()) == 1


def test_wealth_counts_rucksacks_and_stock():
    state.world_state["tick"] = 200
    state.world_state["biome"]["food_stock"] = 10
    pawn("pawn_1")["inventory"]["wood"] = 20  # combined 30 >= 30
    engine.tick_environment()
    assert raiders()


# --- Raider AI --------------------------------------------------------------


def test_raider_marches_to_camp():
    move_pawns_off_camp()
    r = make_raider([0, 0])
    for _ in range(8):
        if r["state"] == "fleeing":
            break
        engine._step_raiders()
    assert r["state"] == "fleeing"  # reached the camp, looted, turned to flee
    assert r["stolen"] == 5


def test_palisade_slows_raider_movement():
    r0 = make_raider([0, 0])
    for _ in range(6):
        engine._step_raiders()
    pos_no_pal = list(r0["pos"])

    state.world_state["raiders"] = []
    state.world_state["biome"]["palisade"] = 3
    r3 = make_raider([0, 0])
    for _ in range(6):
        engine._step_raiders()
    pos_pal = list(r3["pos"])

    assert _manhattan(pos_no_pal, [2, 2]) < _manhattan(pos_pal, [2, 2])


def test_raider_steals_food_at_camp_then_flees():
    move_pawns_off_camp()
    r = make_raider([2, 2])
    state.world_state["biome"]["food_stock"] = 30
    engine._step_raiders()
    assert state.world_state["biome"]["food_stock"] == 25
    assert r["stolen"] == 5
    assert r["state"] == "fleeing"


def test_steal_falls_back_to_rucksacks():
    move_pawns_off_camp()
    r = make_raider([2, 2])
    state.world_state["biome"]["food_stock"] = 0
    pawn("pawn_1")["inventory"]["food"] = 8
    engine._step_raiders()
    assert pawn("pawn_1")["inventory"]["food"] == 3
    assert r["stolen"] == 5


def test_fleeing_raider_leaves_grid():
    r = make_raider([0, 0])
    r["state"] = "fleeing"
    for _ in range(10):
        engine._step_raiders()
    assert not raiders()


def test_fleeing_raider_reports_stolen():
    r = make_raider([2, 2])
    r["state"] = "fleeing"
    r["stolen"] = 5
    history_len = len(state.world_state["history"])
    for _ in range(6):
        engine._step_raiders()
    new_events = state.world_state["history"][history_len:]
    assert any(e["type"] == "raid" and e["data"].get("action") == "fled" for e in new_events)


# --- Defenses ---------------------------------------------------------------


def test_high_combat_pawn_defends_stocks():
    r = make_raider([2, 2])
    p = pawn("pawn_1")
    p["pos"] = [2, 2]
    p["skills"]["combat"] = 50
    p["gear"]["main_hand"] = "Flint Spear"
    state.world_state["biome"]["food_stock"] = 30
    hp_before = r["hp"]
    engine._step_raiders()
    assert r["hp"] < hp_before
    assert state.world_state["biome"]["food_stock"] == 30  # nothing stolen
    assert r["state"] == "fleeing"


def test_defense_kills_weak_raider():
    r = make_raider([2, 2])
    r["hp"] = 1
    p = pawn("pawn_1")
    p["pos"] = [2, 2]
    p["skills"]["combat"] = 50
    engine._step_raiders()
    assert not raiders()


def test_tamed_predator_intercepts_at_camp():
    r = make_raider([2, 2])
    wolf = state.make_animal("Wolf", pos=[2, 2], hp=30)
    wolf["state"] = "tamed"
    state.world_state["wildlife"].append(wolf)
    state.world_state["biome"]["food_stock"] = 30
    hp_before = r["hp"]
    engine._step_raiders()
    assert r["hp"] < hp_before
    assert r["state"] == "fleeing"
    assert state.world_state["biome"]["food_stock"] == 30


def test_undefended_camp_gets_looted():
    move_pawns_off_camp()
    r = make_raider([2, 2])
    state.world_state["biome"]["food_stock"] = 30
    engine._step_raiders()
    assert state.world_state["biome"]["food_stock"] == 25
    assert r["state"] == "fleeing"


# --- Combat -----------------------------------------------------------------


def test_pawn_can_attack_raider():
    r = make_raider([2, 3])
    r["hp"] = 10
    p = pawn("pawn_1")
    p["pos"] = [2, 2]
    p["vitals"]["energy"] = 100
    p["gear"]["main_hand"] = None
    p["skills"]["combat"] = 10
    engine.resolve_actions({"pawn_1": ("Attack", r["id"])})
    assert not raiders()  # killed


def test_wounding_raider_makes_it_flee():
    r = make_raider([2, 3])
    r["hp"] = 1000
    p = pawn("pawn_1")
    p["pos"] = [2, 2]
    p["vitals"]["energy"] = 100
    p["gear"]["main_hand"] = None
    engine.resolve_actions({"pawn_1": ("Attack", r["id"])})
    assert r["state"] == "fleeing"


def test_attack_too_far_fails():
    r = make_raider([0, 0])
    p = pawn("pawn_1")
    p["pos"] = [2, 2]
    p["vitals"]["energy"] = 100
    engine.resolve_actions({"pawn_1": ("Attack", r["id"])})
    assert r in raiders()
    assert r["state"] == "marching"


# --- Schema & view ----------------------------------------------------------


def test_schema_accepts_raider_target():
    r = make_raider([0, 0])
    import schema
    model = schema.build_models()
    data = model.model_validate_json(
        '{"world_event": "ok", '
        f'"pawn_1": {{"action": "Attack", "narrative": "defends", "target": "{r["id"]}"}}, '
        '"pawn_2": {"action": "Rest", "narrative": "rests"}}'
    )
    assert data.pawn_1.target == r["id"]


def test_render_grid_marks_raiders():
    make_raider([0, 0])
    grid_txt = engine.render_grid()
    assert "🥷" in grid_txt


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
