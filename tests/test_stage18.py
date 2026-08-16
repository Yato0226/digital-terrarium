"""Stage 18 tests: trophic cascades & food chain ecology (Phase 4, Step 15)."""

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


def clear_cut_grid():
    for row in state.world_state["grid"]:
        for i, t in enumerate(row):
            if t in engine.FOREST_TILES:
                row[i] = "🫐"


def seed_prey(n):
    state.world_state["wildlife"] = [
        state.make_animal("Deer", pos=[0, 0], hp=30) for _ in range(n)
    ]


def test_forest_count_default_grid():
    assert engine._forest_count() > engine.WINDBREAK_FOREST_MIN
    assert not engine._clear_cut()


def test_clear_cut_detection():
    clear_cut_grid()
    assert engine._forest_count() <= engine.WINDBREAK_FOREST_MIN
    assert engine._clear_cut()


def test_overpopulated_detection():
    seed_prey(3)
    assert not engine._overpopulated()
    seed_prey(4)
    assert engine._overpopulated()


def test_predators_do_not_count_as_prey():
    state.world_state["wildlife"] = [state.make_animal("Wolf", pos=[0, 0], hp=40)]
    assert not engine._overpopulated()


def test_graze_drains_food_stock():
    seed_prey(5)
    state.world_state["biome"]["food_stock"] = 10
    result = []
    engine._graze_tick(result)
    assert state.world_state["biome"]["food_stock"] == 10 - 2 * engine.GRAZE_DRAIN
    assert any(e["type"] == "grazed" for e in result)


def test_graze_eats_ripe_farm_plot(monkeypatch):
    seed_prey(5)
    state.world_state["tiles"]["1,1"] = {"farm": engine.FARM_GROW_TICKS}
    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    result = []
    engine._graze_tick(result)
    assert state.world_state["tiles"]["1,1"]["farm"] == 0
    assert any(e["type"] == "farm_eaten" for e in result)


def test_graze_noop_when_normal():
    seed_prey(3)
    state.world_state["biome"]["food_stock"] = 10
    result = []
    engine._graze_tick(result)
    assert state.world_state["biome"]["food_stock"] == 10
    assert not any(e["type"] == "grazed" for e in result)
    assert not any(e["type"] == "farm_eaten" for e in result)


def test_windbreak_cold_penalty():
    state.world_state["biome"]["season"] = "Winter"
    state.world_state["biome"]["weather"] = "Clear"
    biome = state.world_state["biome"]
    p = pawn("pawn_1")
    p["vitals"].update(hunger=100, energy=100, warmth=50, morale=50)
    p["inventory"]["food"] = 10
    engine._metabolize(p, "pawn_1", biome, False, True, [])
    warmth_normal = p["vitals"]["warmth"]
    p["vitals"]["warmth"] = 50
    clear_cut_grid()
    assert engine._clear_cut()
    engine._metabolize(p, "pawn_1", biome, False, True, [])
    assert p["vitals"]["warmth"] == warmth_normal - engine.WINDBREAK_COLD_PENALTY


def test_clear_cut_raises_flood_chance(monkeypatch):
    state.world_state["biome"]["weather"] = "Rain"
    clear_cut_grid()
    monkeypatch.setattr(engine.random, "random", lambda: 0.21)
    result = engine.tick_environment()
    assert any(e["type"] == "flood" for e in result)


def test_no_flood_under_normal_forests(monkeypatch):
    state.world_state["biome"]["weather"] = "Rain"
    monkeypatch.setattr(engine.random, "random", lambda: 0.21)
    result = engine.tick_environment()
    assert not any(e["type"] == "flood" for e in result)


def test_prey_exceeds_normal_cap_without_predators(monkeypatch):
    seed_prey(4)
    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    engine.tick_environment()
    assert len(engine._wild_prey()) >= 5
