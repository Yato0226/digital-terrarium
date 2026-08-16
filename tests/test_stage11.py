"""Stage 11 tests: generational handoffs & dynasties (Phase 2, Step 8)."""

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


def test_make_pawn_default_generation_1():
    p = state.make_pawn("p9", "Foundling")
    assert p["generation"] == 1


def test_make_pawn_custom_generation():
    p = state.make_pawn("p9", "Heir", generation=3)
    assert p["generation"] == 3


def test_birth_child_generation_is_parents_plus_one():
    mother = pawn("pawn_2")
    mother["generation"] = 2
    mother["partner_id"] = "pawn_1"
    mother["pregnant_ticks"] = 1
    result = []
    engine._give_birth(mother, "pawn_2", result)
    child = [p for p in state.world_state["pawns"].values() if p["mother_id"] == "pawn_2"]
    assert len(child) == 1
    assert child[0]["generation"] == 3


def test_kill_tombstone_records_generation():
    pawn("pawn_1")["generation"] = 4
    engine._kill("pawn_1", pawn("pawn_1"), "old age")
    tomb = state.world_state["graveyard"][-1]
    assert tomb["generation"] == 4


def test_migrate_pawn_backfills_generation():
    old = state.make_pawn("p9", "Old")
    old.pop("generation")
    migrated = state._migrate_pawn("p9", old)
    assert migrated["generation"] == 1


def test_migrate_pawn_preserves_generation():
    old = state.make_pawn("p9", "Old")
    old["generation"] = 5
    migrated = state._migrate_pawn("p9", old)
    assert migrated["generation"] == 5


def test_render_dynasty_living_only():
    txt = engine.render_dynasty()
    assert "Gen 1: Lumberjack, Scout" in txt


def test_render_dynasty_with_fallen():
    state.world_state["graveyard"].append(
        {
            "id": "p9",
            "name": "Willow",
            "generation": 2,
            "cause": "blizzard",
            "beloved": False,
        }
    )
    txt = engine.render_dynasty()
    assert "Gen 1: Lumberjack, Scout; Gen 2: Willow 🪦" in txt


def test_render_dynasty_defaults_generation_for_old_tombstones():
    state.world_state["graveyard"].append(
        {"id": "p9", "name": "Willow", "cause": "blizzard", "beloved": False}
    )
    txt = engine.render_dynasty()
    assert "Gen 1: Lumberjack, Scout, Willow 🪦" in txt


def test_prompt_mentions_generation_and_dynasty():
    text = prompts.build_prompt()
    assert ", Gen 1" in text
    assert "Dynasty: Gen 1: Lumberjack, Scout" in text


def test_prompt_fallen_line_includes_generation():
    state.world_state["graveyard"].append(
        {
            "id": "p9",
            "name": "Willow",
            "generation": 3,
            "cause": "blizzard",
            "beloved": True,
        }
    )
    text = prompts.build_prompt()
    assert "The fallen: Willow (Gen 3, blizzard) 💖" in text


def test_prompt_legacy_deeds_and_relics():
    state.world_state["traditions"]["trees_felled"] = 42
    state.world_state["heirlooms"].append(
        {
            "id": "h9",
            "name": "Grandfather's Axe",
            "stat_bonus": {"combat": 1},
            "moodlet_delta": 0,
            "source": "death of Lumberjack",
        }
    )
    text = prompts.build_prompt()
    assert "The colony's deeds: 42 trees felled" in text
    assert "Relics awaiting a bearer: Grandfather's Axe" in text
