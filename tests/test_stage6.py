import pytest

import engine
import events
import state
from engine import (
    _do_build,
    _metabolize,
    CAMP_POS,
    CAMP_RANGE,
    MONUMENT_INSULATION,
    MONUMENT_MORALE_FLOOR,
    MONUMENT_STONE_NEEDED,
    MONUMENT_WOOD_NEEDED,
)

pytestmark = pytest.mark.usefixtures("fresh_world")


@pytest.fixture(autouse=True)
def fresh_world():
    state.reset_world()
    events.LOGGING = False
    yield
    events.LOGGING = True


def _fortify():
    """Fully fortify the camp so the monument is unlocked."""
    biome = state.world_state["biome"]
    biome["shelter"] = 100
    biome["campfire"] = 100
    biome["granary"] = True
    biome["palisade"] = engine.PALISADE_MAX


def _pawn_with(mineral):
    pawn_id, pawn = next(iter(state.world_state["pawns"].items()))
    pawn["inventory"]["wood"] = 20
    pawn["inventory"]["stone"] = 20 if mineral else 0
    pawn["inventory"]["food"] = 20
    pawn["vitals"]["energy"] = 100
    pawn["pos"] = [CAMP_POS[0], CAMP_POS[1]]
    pawn["gear"]["main_hand"] = "Flint Spear"
    pawn["gear"]["body"] = "Warm Coat"
    return pawn_id, pawn


def _warmth_expected(pos, warmth, day=True):
    """Expected warmth after _metabolize for a pawn at pos (no campfire)."""
    biome = state.world_state["biome"]
    cold = (
        engine.SEASON_COLD[biome["season"]]
        + engine.WEATHER_COLD[biome["weather"]]
        + (0 if day else 3)
    )
    recovery = engine.WARMTH_RECOVERY + (
        engine.SHELTER_WARMTH if biome["shelter"] > 50 else 0
    )
    near_camp = (
        abs(pos[0] - CAMP_POS[0]) + abs(pos[1] - CAMP_POS[1]) <= CAMP_RANGE
    )
    if state.world_state["monument"].get("done") and near_camp:
        recovery += MONUMENT_INSULATION
    return max(0, min(100, warmth + (recovery - cold)))


def test_build_does_not_start_monument_until_fortified():
    pawn_id, pawn = _pawn_with(True)
    _do_build(pawn, pawn_id)
    mon = state.world_state["monument"]
    assert mon["wood"] == 0 and mon["stone"] == 0
    _fortify()
    _do_build(pawn, pawn_id)
    assert state.world_state["monument"]["wood"] == 5


def test_build_monument_progresses_and_deducts_inventory():
    _fortify()
    pawn_id, pawn = _pawn_with(True)
    _do_build(pawn, pawn_id)
    mon = state.world_state["monument"]
    assert mon["wood"] == 5
    assert mon["stone"] == 5
    assert pawn["inventory"]["wood"] == 15
    assert pawn["inventory"]["stone"] == 15


def test_build_monument_requires_resources():
    _fortify()
    pawn_id, pawn = _pawn_with(False)
    _do_build(pawn, pawn_id)
    mon = state.world_state["monument"]
    assert mon["wood"] == 0
    assert pawn["inventory"]["stone"] == 0


def test_build_monument_completes_after_20_15():
    _fortify()
    pawn_id, pawn = _pawn_with(True)
    for _ in range(4):
        _do_build(pawn, pawn_id)
    mon = state.world_state["monument"]
    assert mon["done"] is True
    assert mon["wood"] == MONUMENT_WOOD_NEEDED
    assert mon["stone"] == MONUMENT_STONE_NEEDED
    assert state.pending_monument is True
    assert any(
        h["type"] == "monument_complete" for h in state.world_state["history"]
    )


def test_monument_stone_caps_at_needed():
    _fortify()
    pawn_id, pawn = _pawn_with(True)
    for _ in range(3):
        _do_build(pawn, pawn_id)
    mon = state.world_state["monument"]
    assert mon["wood"] == 15
    assert mon["stone"] == 15
    assert mon["done"] is False
    _do_build(pawn, pawn_id)
    assert mon["done"] is True


def test_monument_morale_floor():
    _fortify()
    pawn_id, pawn = _pawn_with(True)
    for _ in range(4):
        _do_build(pawn, pawn_id)
    pawn["vitals"]["morale"] = 5
    _metabolize(
        pawn,
        pawn_id,
        state.world_state["biome"],
        lit=False,
        day=True,
        result=[],
    )
    assert pawn["vitals"]["morale"] >= MONUMENT_MORALE_FLOOR


def test_monument_insulation_near_camp():
    _fortify()
    pawn_id, pawn = _pawn_with(True)
    for _ in range(4):
        _do_build(pawn, pawn_id)
    pawn["pos"] = [CAMP_POS[0], CAMP_POS[1]]
    pawn["vitals"]["warmth"] = 50
    _metabolize(
        pawn,
        pawn_id,
        state.world_state["biome"],
        lit=False,
        day=True,
        result=[],
    )
    assert pawn["vitals"]["warmth"] == _warmth_expected(pawn["pos"], 50)


def test_monument_insulation_only_near_camp():
    _fortify()
    pawn_id, pawn = _pawn_with(True)
    for _ in range(4):
        _do_build(pawn, pawn_id)
    far = [CAMP_POS[0] + CAMP_RANGE + 1, CAMP_POS[1]]
    pawn["pos"] = far
    pawn["vitals"]["warmth"] = 50
    _metabolize(
        pawn,
        pawn_id,
        state.world_state["biome"],
        lit=False,
        day=True,
        result=[],
    )
    assert pawn["vitals"]["warmth"] == _warmth_expected(far, 50)
    near = _warmth_expected([CAMP_POS[0], CAMP_POS[1]], 50)
    assert near - pawn["vitals"]["warmth"] == MONUMENT_INSULATION


def test_monument_no_insulation_before_complete():
    _fortify()
    pawn_id, pawn = _pawn_with(True)
    _do_build(pawn, pawn_id)
    pawn["pos"] = [CAMP_POS[0], CAMP_POS[1]]
    pawn["vitals"]["warmth"] = 50
    _metabolize(
        pawn,
        pawn_id,
        state.world_state["biome"],
        lit=False,
        day=True,
        result=[],
    )
    assert pawn["vitals"]["warmth"] == _warmth_expected(pawn["pos"], 50)


def test_monument_after_complete_build_falls_back():
    _fortify()
    pawn_id, pawn = _pawn_with(True)
    for _ in range(4):
        _do_build(pawn, pawn_id)
    assert state.world_state["monument"]["done"] is True
    _do_build(pawn, pawn_id)
    assert state.world_state["monument"]["wood"] == MONUMENT_WOOD_NEEDED


# --- Stage 6 Part 2: Agriculture / Farm Plots ---

MEADOW = (1, 1)


def _till(pawn_id, pawn):
    pawn["pos"] = [MEADOW[0], MEADOW[1]]
    pawn["vitals"]["energy"] = 100
    return engine._do_interact(pawn, pawn_id, "till soil")


def _harvest(pawn_id, pawn):
    pawn["pos"] = [MEADOW[0], MEADOW[1]]
    pawn["vitals"]["energy"] = 100
    return engine._do_interact(pawn, pawn_id, "harvest")


def test_till_converts_meadow_to_farm_plot():
    pawn_id, pawn = _pawn_with(True)
    _till(pawn_id, pawn)
    assert state.world_state["grid"][MEADOW[1]][MEADOW[0]] == engine.FARM_TILE
    entry = state.world_state["tiles"][f"{MEADOW[0]},{MEADOW[1]}"]
    assert entry["farm"] == 0


def test_till_requires_meadow():
    pawn_id, pawn = _pawn_with(True)
    pawn["pos"] = [2, 2]  # Camp tile
    ev = engine._do_interact(pawn, pawn_id, "till soil")
    assert state.world_state["grid"][2][2] != engine.FARM_TILE
    assert "no soil to farm here" in ev["description"]


def test_farm_grows_in_spring():
    pawn_id, pawn = _pawn_with(True)
    _till(pawn_id, pawn)
    biome = state.world_state["biome"]
    biome["season"] = "Spring"
    for _ in range(19):
        engine._grow_farms()
    entry = state.world_state["tiles"][f"{MEADOW[0]},{MEADOW[1]}"]
    assert entry["farm"] == 19
    engine._grow_farms()
    assert entry["farm"] == engine.FARM_GROW_TICKS
    assert any(
        h["type"] == "farm_ready" for h in state.world_state["history"]
    )


def test_farm_halts_in_winter():
    pawn_id, pawn = _pawn_with(True)
    _till(pawn_id, pawn)
    state.world_state["biome"]["season"] = "Winter"
    engine._grow_farms()
    entry = state.world_state["tiles"][f"{MEADOW[0]},{MEADOW[1]}"]
    assert entry["farm"] == 0


def test_farm_halts_in_autumn():
    pawn_id, pawn = _pawn_with(True)
    _till(pawn_id, pawn)
    state.world_state["biome"]["season"] = "Autumn"
    engine._grow_farms()
    entry = state.world_state["tiles"][f"{MEADOW[0]},{MEADOW[1]}"]
    assert entry["farm"] == 0


def test_harvest_ripe_plot_pays_without_depleting_stock():
    pawn_id, pawn = _pawn_with(True)
    _till(pawn_id, pawn)
    entry = state.world_state["tiles"][f"{MEADOW[0]},{MEADOW[1]}"]
    entry["farm"] = engine.FARM_GROW_TICKS
    food_before = pawn["inventory"]["food"]
    fiber_before = pawn["inventory"]["fiber"]
    stock_before = state.world_state["biome"]["food_stock"]
    ev = _harvest(pawn_id, pawn)
    assert pawn["inventory"]["food"] == food_before + engine.FARM_HARVEST_FOOD
    assert pawn["inventory"]["fiber"] == fiber_before + engine.FARM_HARVEST_FIBER
    assert state.world_state["biome"]["food_stock"] == stock_before
    assert entry["farm"] == 0
    assert ev["type"] == "harvest"


def test_harvest_unripe_plot_yields_nothing():
    pawn_id, pawn = _pawn_with(True)
    _till(pawn_id, pawn)
    entry = state.world_state["tiles"][f"{MEADOW[0]},{MEADOW[1]}"]
    entry["farm"] = 5
    food_before = pawn["inventory"]["food"]
    ev = _harvest(pawn_id, pawn)
    assert pawn["inventory"]["food"] == food_before
    assert "still growing" in ev["description"]


def test_harvest_crops_verb_works():
    pawn_id, pawn = _pawn_with(True)
    _till(pawn_id, pawn)
    entry = state.world_state["tiles"][f"{MEADOW[0]},{MEADOW[1]}"]
    entry["farm"] = engine.FARM_GROW_TICKS
    pawn["pos"] = [MEADOW[0], MEADOW[1]]
    pawn["vitals"]["energy"] = 100
    ev = engine._do_interact(pawn, pawn_id, "gather crops")
    assert ev["type"] == "harvest"


def test_plant_seeds_verb_tills():
    pawn_id, pawn = _pawn_with(True)
    pawn["pos"] = [MEADOW[0], MEADOW[1]]
    pawn["vitals"]["energy"] = 100
    engine._do_interact(pawn, pawn_id, "plant seeds")
    assert state.world_state["grid"][MEADOW[1]][MEADOW[0]] == engine.FARM_TILE


def test_farm_plot_render_shows_wheat():
    pawn_id, pawn = _pawn_with(True)
    _till(pawn_id, pawn)
    pawn["pos"] = [0, 0]
    assert engine.FARM_TILE in engine.render_grid()
