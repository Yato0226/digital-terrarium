import pytest

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
