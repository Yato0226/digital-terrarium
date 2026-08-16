"""Stage 16 tests: free-form dynamic roles with keyword bucketing (Phase 3, Step 13)."""

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


def test_make_pawn_has_title_fields():
    p = state.make_pawn("p9", "Foundling")
    assert p["custom_title"] is None
    assert p["title_role"] is None


def test_adopt_title_martial_bucket():
    adopted = engine._adopt_title(pawn("pawn_1"), "Fang-Breaker")
    assert adopted["role"] == "martial"
    assert pawn("pawn_1")["custom_title"] == "Fang-Breaker"
    assert pawn("pawn_1")["title_role"] == "martial"


def test_adopt_title_nurture_bucket():
    adopted = engine._adopt_title(pawn("pawn_1"), "Keeper of the Hearth")
    assert adopted["role"] == "nurture"


def test_adopt_title_spirit_bucket():
    adopted = engine._adopt_title(pawn("pawn_1"), "Seer of Whispers")
    assert adopted["role"] == "spirit"


def test_adopt_title_rejects_invalid():
    assert engine._adopt_title(pawn("pawn_1"), "x" * 40) is None
    assert engine._adopt_title(pawn("pawn_1"), "Fang_Breaker") is None
    assert pawn("pawn_1")["custom_title"] is None


def test_martial_defense_reduces_damage():
    p1 = pawn("pawn_1")
    pawn("pawn_2")["vitals"]["hp"] = 100
    engine._do_attack(p1, "pawn_1", "pawn_2")
    hp_without = pawn("pawn_2")["vitals"]["hp"]
    pawn("pawn_2")["vitals"]["hp"] = 100
    pawn("pawn_2")["title_role"] = "martial"
    engine._do_attack(p1, "pawn_1", "pawn_2")
    assert pawn("pawn_2")["vitals"]["hp"] == hp_without + engine.TITLE_MARTIAL_DEFENSE


def test_nurture_share_bonus():
    p1 = pawn("pawn_1")
    p1["inventory"]["food"] = 10
    p1["vitals"]["energy"] = 100
    p1["title_role"] = "nurture"
    engine._do_share(p1, "pawn_1", "pawn_2")
    assert pawn("pawn_2")["inventory"]["food"] == engine.SHARE_FOOD + engine.TITLE_NURTURE_SHARE


def test_spirit_grief_halved():
    pawn("pawn_1")["title_role"] = "spirit"
    engine._add_moodlet(pawn("pawn_1"), "Grief", -10, 10)
    engine._add_moodlet(pawn("pawn_2"), "Grief", -10, 10)
    assert pawn("pawn_1")["moodlets"][0]["ticks_left"] == 5
    assert pawn("pawn_2")["moodlets"][0]["ticks_left"] == 10


def test_resolve_actions_adopts_title():
    intents = {"pawn_1": ("Rest", None, None, None, "Fang-Breaker")}
    result = engine.resolve_actions(intents)
    assert pawn("pawn_1")["custom_title"] == "Fang-Breaker"
    assert pawn("pawn_1")["title_role"] == "martial"
    assert any(e["type"] == "role" for e in result)


def test_prompt_shows_custom_title():
    pawn("pawn_1")["custom_title"] = "Fang-Breaker"
    text = prompts.build_prompt()
    assert "Fang-Breaker" in text


def test_migrate_pawn_preserves_custom_title():
    old = state.make_pawn("p9", "Old")
    old["custom_title"] = "Keeper of the Hearth"
    old["title_role"] = "nurture"
    migrated = state._migrate_pawn("p9", old)
    assert migrated["custom_title"] == "Keeper of the Hearth"
    assert migrated["title_role"] == "nurture"
