import json
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


def grid():
    return state.world_state["grid"]


def any_burning():
    g = grid()
    return any(g[y][x] == engine.BURNING_TILE for y in range(len(g)) for x in range(len(g[y])))


# --- Ignition ---


def test_ignite_forest_and_no_double():
    assert engine._ignite(0, 0) is True
    assert grid()[0][0] == "🔥"
    entry = state.world_state["tiles"]["0,0"]
    assert entry["burn"] == engine.FIRE_TICKS
    assert engine._ignite(0, 0) is False
    assert engine._ignite(1, 1) is False  # Meadow is not flammable


def test_storm_lightning_ignites_forest(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = 1
    state.world_state["biome"]["weather"] = "Storm"
    engine.tick_environment()
    assert any_burning()
    assert any(e["type"] == "fire_start" for e in state.world_state["history"])


def test_clear_weather_no_fire(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = 1
    state.world_state["biome"]["weather"] = "Clear"
    engine.tick_environment()
    assert not any_burning()


def test_heatwave_ignites_when_wood_high(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = 100  # Summer
    state.world_state["biome"]["weather"] = "Heatwave"
    state.world_state["biome"]["wood_stock"] = 100
    engine.tick_environment()
    assert any_burning()


def test_heatwave_no_fire_when_wood_low(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = 100  # Summer
    state.world_state["biome"]["weather"] = "Heatwave"
    state.world_state["biome"]["wood_stock"] = 40
    engine.tick_environment()
    assert not any_burning()


def test_firesetter_break_ignites_forest():
    p = pawn("pawn_1")
    p["mental_break"] = "firesetter"
    p["break_ticks"] = 2
    p["pos"] = [1, 1]  # Meadow, adjacent to forest
    evs = engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert grid()[0][1] == "🔥"  # tile (1,0)
    assert "1,0" in state.world_state["tiles"]
    assert any(e["type"] == "break" and e["data"].get("action") == "ignite" for e in evs)


def test_firesetter_break_falls_back_to_douse_at_camp():
    p = pawn("pawn_1")
    p["mental_break"] = "firesetter"
    p["break_ticks"] = 2
    before = state.world_state["biome"]["campfire"]
    engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert state.world_state["biome"]["campfire"] == before - 10


# --- Tile lifecycle ---


def test_fire_burn_lifecycle_and_wood_drain(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 1.0)
    state.world_state["tick"] = 300  # Winter — no regrowth interference
    state.world_state["biome"]["season"] = "Winter"
    state.world_state["biome"]["weather"] = "Clear"
    grid()[0][0] = "🔥"
    state.world_state["tiles"]["0,0"] = {"burn": engine.FIRE_TICKS, "regrow_to": "🌲"}
    engine.tick_environment()
    assert state.world_state["biome"]["wood_stock"] == 90
    assert state.world_state["tiles"]["0,0"]["burn"] == engine.FIRE_TICKS - 1
    for _ in range(engine.FIRE_TICKS - 1):
        engine.tick_environment()
    assert grid()[0][0] == "🌫️"
    assert state.world_state["tiles"]["0,0"]["regrow_in"] == engine.REGROW_TICKS
    for _ in range(engine.REGROW_TICKS):
        engine.tick_environment()
    assert grid()[0][0] == "🌲"
    assert "0,0" not in state.world_state["tiles"]


def test_fire_damages_standing_pawn():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["vitals"]["hp"] = 3
    grid()[0][0] = "🔥"
    state.world_state["tiles"]["0,0"] = {"burn": engine.FIRE_TICKS, "regrow_to": "🌲"}
    engine.tick_environment()
    assert p["vitals"]["hp"] == 0
    assert p["status"] == "incapacitated"
    assert "pawn_1" in state.world_state["pawns"]  # fire incapacitates, never kills
    assert any(e["type"] == "fire_damage" for e in state.world_state["history"])


def test_fire_spreads_to_adjacent_forest(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = 300
    state.world_state["biome"]["season"] = "Winter"
    state.world_state["biome"]["weather"] = "Clear"
    grid()[0][0] = "🔥"
    state.world_state["tiles"]["0,0"] = {"burn": engine.FIRE_TICKS, "regrow_to": "🌲"}
    engine.tick_environment()
    assert grid()[0][1] == "🔥"
    assert grid()[1][0] == "🔥"
    assert "0,1" in state.world_state["tiles"]
    assert "1,0" in state.world_state["tiles"]
    assert any(e["type"] == "fire_spread" for e in state.world_state["history"])


def test_fire_spreads_to_camp(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = 300
    state.world_state["biome"]["season"] = "Winter"
    state.world_state["biome"]["weather"] = "Clear"
    grid()[1][2] = "🔥"  # (2,1) — make it a burning tile adjacent to Camp
    state.world_state["tiles"]["2,1"] = {"burn": engine.FIRE_TICKS, "regrow_to": "🌲"}
    engine.tick_environment()
    assert grid()[2][2] == "🔥"  # Camp caught fire
    assert state.world_state["tiles"]["2,2"]["regrow_to"] == "🏕️"


def test_camp_burns_then_restores():
    state.world_state["biome"]["campfire"] = 100
    state.world_state["biome"]["shelter"] = 100
    grid()[2][2] = "🔥"
    state.world_state["tiles"]["2,2"] = {"burn": engine.FIRE_TICKS, "regrow_to": "🏕️"}
    for _ in range(engine.FIRE_TICKS):
        engine.tick_environment()
    assert grid()[2][2] == "🏕️"
    assert "2,2" not in state.world_state["tiles"]
    assert state.world_state["biome"]["shelter"] < 100  # camp damage was real


# --- Firefighting ---


def test_interact_extinguishes_adjacent_fire():
    p = pawn("pawn_1")
    p["pos"] = [0, 1]
    p["vitals"]["energy"] = 100
    grid()[1][0] = "🔥"
    state.world_state["tiles"]["0,1"] = {"burn": 2, "regrow_to": "🌲"}
    evs = engine.resolve_actions({"pawn_1": ("Interact", None, "extinguish")})
    assert grid()[1][0] == "🌫️"
    entry = state.world_state["tiles"]["0,1"]
    assert "burn" not in entry
    assert entry["regrow_in"] == engine.REGROW_TICKS
    assert any("extinguishes" in (e.get("description") or "") for e in evs)


def test_interact_extinguish_no_fire_nearby():
    p = pawn("pawn_1")
    p["pos"] = [0, 1]
    p["vitals"]["energy"] = 100
    evs = engine.resolve_actions({"pawn_1": ("Interact", None, "douse")})
    assert grid()[1][0] == "🌲"  # untouched
    assert any("no fire nearby" in (e.get("description") or "") for e in evs)


def test_chop_creates_firebreak():
    p = pawn("pawn_1")
    p["pos"] = [0, 1]
    p["vitals"]["energy"] = 100
    grid()[0][0] = "🔥"
    state.world_state["tiles"]["0,0"] = {"burn": 2, "regrow_to": "🌲"}
    evs = engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert grid()[1][0] == "🫐"  # cleared strip
    assert any(e["type"] == "chop" and e["data"].get("firebreak") for e in evs)


# --- Rendering & prompts ---


def test_render_grid_shows_burning_and_ash():
    grid()[0][0] = "🔥"
    grid()[4][4] = "🌫️"
    lines = engine.render_grid().split("\n")
    assert lines[0].startswith("[🔥]")
    assert lines[4].endswith("[🌫️]")


def test_map_renderer_has_fire_colors():
    import map_renderer

    assert "🔥" in map_renderer.TILE_COLORS
    assert "🌫️" in map_renderer.TILE_COLORS
    grid()[0][0] = "🔥"
    png = map_renderer.render_png()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_prompt_mentions_active_fire():
    grid()[0][0] = "🔥"
    state.world_state["tiles"]["0,0"] = {"burn": 2, "regrow_to": "🌲"}
    assert "🔥 Fire" in prompts.build_prompt()


# --- Persistence ---


def test_tiles_persist_across_save_load(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "STATE_FILE", str(tmp_path / "state.json"))
    state.world_state["tiles"] = {"0,0": {"burn": 2, "regrow_to": "🌲"}}
    state.save_state()
    state.world_state["tiles"] = {}
    state.load_state()
    assert state.world_state["tiles"] == {"0,0": {"burn": 2, "regrow_to": "🌲"}}


def test_old_save_without_tiles_loads_cleanly(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "STATE_FILE", str(tmp_path / "state.json"))
    state.world_state["pawns"] = {"pawn_1": state.make_pawn("pawn_1", "Lumberjack")}
    state.world_state["tiles"] = {}
    data = json.loads(json.dumps(state.world_state))
    del data["tiles"]  # simulate a pre-Stage-4 save
    with open(str(tmp_path / "state.json"), "w", encoding="utf-8") as f:
        json.dump(data, f)
    state.world_state["tiles"] = {}
    state.load_state()
    assert state.world_state["tiles"] == {}
    assert "pawn_1" in state.world_state["pawns"]


# --- Seasonal disasters & anomalies (Stage 4 part 2) ---


def _set_tick_weather(season, weather, tick):
    state.world_state["tick"] = tick
    state.world_state["biome"]["season"] = season
    state.world_state["biome"]["weather"] = weather
    for p in state.world_state["pawns"].values():
        p["born_tick"] = tick


def test_flood_spring_rain_floods_meadows(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    _set_tick_weather("Spring", "Rain", 41)
    engine.tick_environment()
    assert state.world_state["biome"]["flood"] > 0
    assert grid()[3][1] == "🌊"  # Meadow (1,3) adjacent to the river flooded
    assert grid()[1][1] == "🫐"  # Meadow (1,1) untouched
    assert any(e["type"] == "flood" for e in state.world_state["history"])


def test_flood_recedes_and_deposits_food(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 1.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    _set_tick_weather("Spring", "Rain", 41)
    state.world_state["biome"]["food_stock"] = 40
    state.world_state["biome"]["flood"] = 1
    state.world_state["biome"]["flooded"] = [[1, 3]]
    grid()[3][1] = "🌊"
    engine.tick_environment()
    assert grid()[3][1] == "🫐"
    assert state.world_state["biome"]["flood"] == 0
    assert not state.world_state["biome"]["flooded"]
    assert state.world_state["biome"]["food_stock"] >= 40 + engine.FLOOD_FOOD_BONUS
    assert any(e["type"] == "flood_recedes" for e in state.world_state["history"])


def test_forage_blocked_during_flood():
    p = pawn("pawn_1")
    p["pos"] = [1, 3]
    p["vitals"]["energy"] = 100
    state.world_state["biome"]["flood"] = 2
    state.world_state["biome"]["flooded"] = [[1, 3]]
    grid()[3][1] = "🌊"
    evs = engine.resolve_actions({"pawn_1": ("Forage", None)})
    assert any(e["type"] == "failed" and e["data"].get("reason") == "flooded" for e in evs)


def test_forage_allowed_after_flood_recedes():
    p = pawn("pawn_1")
    p["pos"] = [1, 3]
    p["vitals"]["energy"] = 100
    state.world_state["biome"]["food_stock"] = 50
    grid()[3][1] = "🫐"
    evs = engine.resolve_actions({"pawn_1": ("Forage", None)})
    assert any(e["type"] == "forage" for e in evs)


def test_aurora_winter_night_lifts_morale(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    _set_tick_weather("Winter", "Clear", 315)  # 315 % 20 == 15 -> night
    for p in state.world_state["pawns"].values():
        p["vitals"]["morale"] = 50
    engine.tick_environment()
    assert state.world_state["biome"]["aurora"] is True
    for p in state.world_state["pawns"].values():
        assert p["vitals"]["morale"] >= 60
    assert any(e["type"] == "aurora" for e in state.world_state["history"])


def test_aurora_not_on_winter_day(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    _set_tick_weather("Winter", "Clear", 300)  # 300 % 20 == 0 -> day
    engine.tick_environment()
    assert state.world_state["biome"]["aurora"] is False


def test_prompt_reports_aurora():
    state.world_state["biome"]["aurora"] = True
    assert "Aurora" in prompts.build_prompt()


def test_miasma_autumn_hurts_unprotected_pawns(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    _set_tick_weather("Autumn", "Rain", 201)
    p = pawn("pawn_1")
    p["pos"] = [1, 2]  # Ruins (grid[2][1])
    p["vitals"]["hp"] = 50
    engine.tick_environment()
    assert state.world_state["biome"]["miasma"] > 0
    assert p["vitals"]["hp"] == 45
    assert any(e["type"] == "miasma_damage" for e in state.world_state["history"])


def test_miasma_warm_coat_protects():
    p = pawn("pawn_1")
    p["pos"] = [1, 2]  # Ruins (grid[2][1])
    p["vitals"]["hp"] = 50
    p["gear"]["body"] = "Warm Coat"
    state.world_state["biome"]["miasma"] = 1
    engine.tick_environment()
    assert p["vitals"]["hp"] == 50
    assert not any(e["type"] == "miasma_damage" for e in state.world_state["history"])


def test_miasma_clears_after_countdown(monkeypatch):
    monkeypatch.setattr(engine, "WEATHER_CHANGE_CHANCE", 0.0)
    monkeypatch.setattr(random, "random", lambda: 1.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    _set_tick_weather("Autumn", "Rain", 201)
    state.world_state["biome"]["miasma"] = 1
    engine.tick_environment()
    assert state.world_state["biome"]["miasma"] == 0
    assert any(e["type"] == "miasma_clear" for e in state.world_state["history"])


def test_disaster_biome_fields_survive_reload(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "STATE_FILE", str(tmp_path / "state.json"))
    state.world_state["biome"]["flood"] = 2
    state.world_state["biome"]["flooded"] = [[1, 3]]
    state.world_state["biome"]["miasma"] = 1
    state.world_state["biome"]["aurora"] = True
    state.save_state()
    state.world_state["biome"] = dict(state.DEFAULT_BIOME)
    state.load_state()
    assert state.world_state["biome"]["flood"] == 2
    assert state.world_state["biome"]["flooded"] == [[1, 3]]
    assert state.world_state["biome"]["miasma"] == 1
    assert state.world_state["biome"]["aurora"] is True


def test_old_save_without_disaster_biome_loads_cleanly(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "STATE_FILE", str(tmp_path / "state.json"))
    state.world_state["pawns"] = {"pawn_1": state.make_pawn("pawn_1", "Lumberjack")}
    data = json.loads(json.dumps(state.world_state))
    biome = data["biome"]
    for key in ("flood", "flooded", "miasma", "aurora"):
        biome.pop(key, None)
    with open(str(tmp_path / "state.json"), "w", encoding="utf-8") as f:
        json.dump(data, f)
    state.world_state["biome"] = dict(state.DEFAULT_BIOME)
    state.load_state()
    assert state.world_state["biome"]["flood"] == 0
    assert state.world_state["biome"]["flooded"] == []
    assert state.world_state["biome"]["miasma"] == 0
    assert state.world_state["biome"]["aurora"] is False
    assert "pawn_1" in state.world_state["pawns"]
