"""Stage 22 tests: dynamic colony identity & emergent taboos (Phase 5, Step 19)."""

import pytest

import core
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


# ---- Colony identity ----

def test_default_colony_name():
    assert state.world_state["colony"]["name"] == engine.DEFAULT_COLONY_NAME == "The Settlers"


def test_earn_fire_renames_to_ashen_kin():
    engine._ignite(0, 0)
    result = []
    engine._recompute_colony_name(result)
    assert state.world_state["colony"]["name"] == "The Ashen Kin"
    assert any(e["type"] == "colony_renamed" for e in result)


def test_name_priority_famine_over_fire():
    engine._earn_colony_flag("famine")
    engine._earn_colony_flag("fire")
    engine._recompute_colony_name([])
    assert state.world_state["colony"]["name"] == "The Famineborn"


def test_many_deaths_beats_all():
    engine._earn_colony_flag("fire")
    engine._earn_colony_flag("many_deaths")
    engine._recompute_colony_name([])
    assert state.world_state["colony"]["name"] == "The Undying"


def test_name_history_recorded():
    engine._earn_colony_flag("fire")
    engine._recompute_colony_name([])
    assert state.world_state["colony"]["history"] == ["The Settlers"]


def test_rename_fires_once():
    engine._earn_colony_flag("fire")
    engine._recompute_colony_name([])
    engine._recompute_colony_name([])
    renamed = sum(1 for e in state.world_state["history"] if e["type"] == "colony_renamed")
    assert renamed == 1


def test_cataclysm_end_earns_hearthfolk():
    state.world_state["biome"]["cataclysm"] = {
        "kind": "long_winter",
        "name": "The Long Winter",
        "started_tick": 1,
        "ends_tick": 1,
    }
    engine.tick_environment()
    assert state.world_state["colony"]["name"] == "The Hearthfolk"


def test_tradition_earns_hunters_name():
    state.world_state["traditions"]["predators_slain"] = 100
    engine._evaluate_tradition()
    engine._recompute_colony_name([])
    assert state.world_state["colony"]["name"] == "The Hunters"


def test_flood_earns_riverborn():
    engine._earn_colony_flag("flood")
    engine._recompute_colony_name([])
    assert state.world_state["colony"]["name"] == "The Riverborn"


def test_colony_txt():
    engine._earn_colony_flag("fire")
    engine._recompute_colony_name([])
    text = core.colony_txt()
    assert "The Ashen Kin" in text
    assert "wildfire" in text


# ---- Taboos ----

def test_no_taboo_by_default():
    assert state.world_state["taboos"] == []


def test_ruins_death_creates_taboo():
    p = pawn("pawn_1")
    p["pos"] = [1, 2]  # the ruins tile
    engine._kill("pawn_1", p, "starvation")
    taboos = state.world_state["taboos"]
    assert len(taboos) == 1
    assert taboos[0]["name"] == engine.TABOO_RUINS
    assert "learned to fear" in state.world_state["history"][-1]["description"] or any(
        e["type"] == "taboo" for e in state.world_state["history"]
    )


def test_camp_death_no_taboo():
    p = pawn("pawn_1")
    p["pos"] = [2, 2]  # camp
    engine._kill("pawn_1", p, "starvation")
    assert state.world_state["taboos"] == []


def test_low_bravery_refuses_ruins():
    state.world_state["taboos"].append(
        {"name": engine.TABOO_RUINS, "reason": "X died in the ruins", "since_tick": 1}
    )
    p = pawn("pawn_1")
    p["pos"] = [0, 2]
    p["skills"]["bravery"] = 1
    ev = engine._do_move(p, "pawn_1", "E")
    assert ev["type"] == "failed"
    assert ev["data"]["reason"] == "taboo"
    assert p["pos"] == [0, 2]


def test_brave_pawn_ignores_taboo():
    state.world_state["taboos"].append(
        {"name": engine.TABOO_RUINS, "reason": "X died in the ruins", "since_tick": 1}
    )
    p = pawn("pawn_1")
    p["pos"] = [0, 2]
    p["skills"]["bravery"] = 8
    ev = engine._do_move(p, "pawn_1", "E")
    assert ev["type"] == "move"
    assert p["pos"] == [1, 2]


def test_god_order_overrides_taboo():
    state.world_state["taboos"].append(
        {"name": engine.TABOO_RUINS, "reason": "X died in the ruins", "since_tick": 1}
    )
    p = pawn("pawn_1")
    p["pos"] = [0, 2]
    p["skills"]["bravery"] = 1
    ev = engine._do_move(p, "pawn_1", "E", god=True)
    assert ev["type"] == "move"
    assert p["pos"] == [1, 2]


def test_no_taboo_move_is_fine():
    p = pawn("pawn_1")
    p["pos"] = [0, 2]
    p["skills"]["bravery"] = 1
    ev = engine._do_move(p, "pawn_1", "E")
    assert ev["type"] == "move"
    assert p["pos"] == [1, 2]


def test_taboo_is_feasibility_reason():
    assert "taboo" in engine.FEASIBILITY_REASONS


def test_prompt_shows_colony_and_taboo():
    engine._earn_colony_flag("fire")
    engine._recompute_colony_name([])
    state.world_state["taboos"].append(
        {"name": engine.TABOO_RUINS, "reason": "Y died in the ruins", "since_tick": 1}
    )
    text = prompts.build_prompt()
    assert "The Ashen Kin" in text
    assert "Taboo:" in text


def test_taboo_txt():
    state.world_state["taboos"].append(
        {"name": engine.TABOO_RUINS, "reason": "Y died in the ruins", "since_tick": 1}
    )
    text = core.taboo_txt()
    assert "ruins" in text


def test_wild_ids_are_monotonic():
    """An escaped/despawned beast must not free its id for the next spawn."""
    w1 = state.make_animal("Wolf", pos=[0, 0])
    state.world_state["wildlife"].append(w1)
    state.world_state["wildlife"].remove(w1)
    w2 = state.make_animal("Deer", pos=[1, 1])
    state.world_state["wildlife"].append(w2)
    assert w2["id"] != w1["id"]
