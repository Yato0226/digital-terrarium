"""Stage 17 tests: annual camp council & colony mandates (Phase 3, Step 14)."""

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


def test_apply_council_sets_leader_and_mandate():
    record = engine.apply_council("pawn_1", "Fortify before the raiders return")
    assert record["leader_name"] == "Lumberjack"
    assert record["mandate"] == "Fortify before the raiders return"
    assert state.world_state["council"]["leader_id"] == "pawn_1"


def test_apply_council_rejects_unknown_leader():
    assert engine.apply_council("p999", "Fortify") is None
    assert state.world_state["council"] is None


def test_apply_council_rejects_down_leader():
    pawn("pawn_2")["status"] = "incapacitated"
    assert engine.apply_council("pawn_2", "Fortify") is None


def test_apply_council_rejects_long_mandate():
    assert engine.apply_council("pawn_1", "x" * 200) is None


def test_apply_council_rejects_empty_mandate():
    assert engine.apply_council("pawn_1", "   ") is None


def test_leader_morale_bonus_and_moodlet():
    before = pawn("pawn_1")["vitals"]["morale"]
    engine.apply_council("pawn_1", "Tame the beasts of the wood")
    assert pawn("pawn_1")["vitals"]["morale"] == before + engine.COUNCIL_LEADER_MORALE
    assert any(m["name"] == "Chosen" for m in pawn("pawn_1")["moodlets"])


def test_council_emits_event():
    engine.apply_council("pawn_1", "Carve the harvest from the cold earth")
    assert any(e["type"] == "council" for e in state.world_state["history"])


def test_council_cleared_on_reset():
    engine.apply_council("pawn_1", "Fortify")
    state.reset_world()
    assert state.world_state["council"] is None


def test_prompt_shows_council():
    engine.apply_council("pawn_1", "Fortify before the raiders return")
    text = prompts.build_prompt()
    assert "Lumberjack" in text
    assert "Fortify before the raiders return" in text


def test_resolve_leader():
    assert core._resolve_leader("Lumberjack") == "pawn_1"
    assert core._resolve_leader("Nobody") is None


def test_council_txt():
    engine.apply_council("pawn_1", "Tame the beasts of the wood")
    text = core.council_txt()
    assert "Lumberjack" in text
    assert "Tame the beasts of the wood" in text


def test_council_txt_empty():
    text = core.council_txt()
    assert "No council" in text
