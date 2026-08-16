"""Stage 14 tests: qualitative relational badges (Phase 3, Step 11)."""

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


def test_make_pawn_has_badge_fields():
    p = state.make_pawn("p9", "Foundling")
    assert p["badges"] == []
    assert p["rel_badges"] == {}


def test_share_grants_indebted():
    p1 = pawn("pawn_1")
    p1["inventory"]["food"] = 10
    p1["vitals"]["energy"] = 100
    engine._do_share(p1, "pawn_1", "pawn_2")
    assert "Indebted" in pawn("pawn_2")["rel_badges"]["pawn_1"]


def test_share_to_starving_grants_lifesaver():
    p1 = pawn("pawn_1")
    p1["inventory"]["food"] = 10
    p1["vitals"]["energy"] = 100
    pawn("pawn_2")["starving_ticks"] = 3
    engine._do_share(p1, "pawn_1", "pawn_2")
    badges = pawn("pawn_2")["rel_badges"]["pawn_1"]
    assert "Indebted" in badges
    assert "Lifesaver" in badges


def test_share_badges_deduplicated():
    p1 = pawn("pawn_1")
    p1["inventory"]["food"] = 10
    p1["vitals"]["energy"] = 100
    p1["vitals"]["hunger"] = 50
    for _ in range(3):
        engine._do_share(p1, "pawn_1", "pawn_2")
    assert pawn("pawn_2")["rel_badges"]["pawn_1"] == ["Indebted"]


def test_attack_bonded_friend_grants_betrayer():
    pawn("pawn_2")["relationships"]["pawn_1"] = 40
    engine._do_attack(pawn("pawn_1"), "pawn_1", "pawn_2")
    assert "Betrayer" in pawn("pawn_2")["rel_badges"]["pawn_1"]


def test_attack_stranger_no_betrayer():
    engine._do_attack(pawn("pawn_1"), "pawn_1", "pawn_2")
    assert "Betrayer" not in pawn("pawn_2").get("rel_badges", {}).get("pawn_1", [])


def test_teach_interact_grants_mentor():
    engine._do_interact(pawn("pawn_1"), "pawn_1", "teach the young one")
    assert "Mentor" in pawn("pawn_1")["rel_badges"]["pawn_2"]


def test_regular_social_no_mentor():
    engine._do_interact(pawn("pawn_1"), "pawn_1", "gossip by the fire")
    assert "Mentor" not in pawn("pawn_1").get("rel_badges", {}).get("pawn_2", [])


def test_kill_grants_widow_to_partner():
    pawn("pawn_2")["partners"] = ["pawn_1"]
    engine._kill("pawn_1", pawn("pawn_1"), "blizzard")
    assert "Widow" in pawn("pawn_2")["badges"]


def test_kill_no_widow_for_unpaired():
    engine._kill("pawn_1", pawn("pawn_1"), "blizzard")
    assert "Widow" not in pawn("pawn_2")["badges"]


def test_migrate_pawn_preserves_badges():
    old = state.make_pawn("p9", "Old")
    old["badges"] = ["Widow"]
    old["rel_badges"] = {"pawn_1": ["Lifesaver", "Indebted"]}
    migrated = state._migrate_pawn("p9", old)
    assert migrated["badges"] == ["Widow"]
    assert migrated["rel_badges"] == {"pawn_1": ["Lifesaver", "Indebted"]}


def test_prompt_shows_badges():
    pawn("pawn_2")["rel_badges"]["pawn_1"] = ["Lifesaver"]
    pawn("pawn_2")["badges"] = ["Widow"]
    text = prompts.build_prompt()
    assert "Lifesaver of Lumberjack" in text
    assert "Widow" in text
