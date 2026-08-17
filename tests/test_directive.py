"""System-wide god directive: injected into the LLM system prompt.

A `!directive <text>` command sets a colony-wide instruction that steers the
LLM for every pawn each tick, until cleared. Distinct from `!say`, which
whispers to a single pawn.
"""

import pytest

import prompts
import state

pytestmark = pytest.mark.usefixtures("fresh_world")


@pytest.fixture(autouse=True)
def fresh_world():
    state.reset_world()
    state.god_directive = None
    yield


def test_directive_injected_into_prompt():
    state.god_directive = "The colony must never fight."
    text = prompts.build_prompt()
    assert "THE CREATOR'S DIRECTIVE" in text
    assert "The colony must never fight." in text


def test_directive_absent_by_default():
    state.god_directive = None
    assert "THE CREATOR'S DIRECTIVE" not in prompts.build_prompt()


def test_directive_independent_of_pawn_whispers():
    state.god_directive = "Be peaceful."
    state.god_whispers["pawn_1"] = "private note"
    text = prompts.build_prompt()
    # The system directive and the per-pawn whisper are separate channels.
    assert "THE CREATOR'S DIRECTIVE" in text
    assert "private note" in text
    assert "Be peaceful." in text
