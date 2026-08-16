"""Stage 15 tests: multigenerational blood feuds (Phase 3, Step 12)."""

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


def make_rivals(a_id, b_id):
    pawn(a_id)["relationships"][b_id] = -30
    pawn(b_id)["relationships"][a_id] = -30


def child_pawn():
    return list(state.world_state["pawns"].values())[-1]


def test_inherit_feuds_seeds_child_hostility():
    father = state.make_pawn("p9", "Bramble")
    state.world_state["pawns"]["p9"] = father
    make_rivals("pawn_1", "pawn_2")
    make_rivals("p9", "pawn_2")
    pawn("pawn_1")["partner_id"] = "p9"
    engine._give_birth(pawn("pawn_1"), "pawn_1", [])
    child = child_pawn()
    assert child["id"] != "pawn_1"
    assert child["relationships"].get("pawn_2") == engine.FEUD_INHERIT


def test_no_feud_without_parental_rivals():
    father = state.make_pawn("p9", "Bramble")
    state.world_state["pawns"]["p9"] = father
    pawn("pawn_1")["partner_id"] = "p9"
    engine._give_birth(pawn("pawn_1"), "pawn_1", [])
    child = child_pawn()
    assert child["id"] != "pawn_1"
    assert "pawn_2" not in child["relationships"]


def test_camp_brawl_between_mutual_rivals(monkeypatch):
    make_rivals("pawn_1", "pawn_2")
    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    result = []
    engine._camp_brawls(result)
    assert any(e["type"] == "brawl" for e in result)
    assert pawn("pawn_1")["vitals"]["hp"] == 100 - engine.BRAWL_DAMAGE
    assert pawn("pawn_2")["relationships"]["pawn_1"] <= -30 - engine.BRAWL_RELATIONSHIP_DROP


def test_no_brawl_for_non_rivals(monkeypatch):
    pawn("pawn_1")["relationships"]["pawn_2"] = -10
    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    result = []
    engine._camp_brawls(result)
    assert not any(e["type"] == "brawl" for e in result)


def test_no_brawl_outside_camp(monkeypatch):
    make_rivals("pawn_1", "pawn_2")
    pawn("pawn_2")["pos"] = [0, 0]
    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    result = []
    engine._camp_brawls(result)
    assert not any(e["type"] == "brawl" for e in result)


def test_feud_heals_by_sharing():
    father = state.make_pawn("p9", "Bramble")
    state.world_state["pawns"]["p9"] = father
    make_rivals("pawn_1", "pawn_2")
    pawn("pawn_1")["partner_id"] = "p9"
    engine._give_birth(pawn("pawn_1"), "pawn_1", [])
    child = child_pawn()
    assert child["relationships"]["pawn_2"] == engine.FEUD_INHERIT
    pawn("pawn_2")["inventory"]["food"] = 50
    pawn("pawn_2")["vitals"]["energy"] = 100
    child_id = child["id"]
    for _ in range(3):
        engine._do_share(pawn("pawn_2"), "pawn_2", child_id)
    assert child["relationships"]["pawn_2"] > engine.RIVAL_THRESHOLD
