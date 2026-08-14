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


def test_rest_regenerates():
    p = pawn("pawn_1")
    p["vitals"]["hp"] = 50
    p["vitals"]["energy"] = 10
    engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert p["vitals"]["hp"] == 60
    assert p["vitals"]["energy"] == 30


def test_chop_requires_energy():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 5
    before = p["inventory"]["wood"]
    evs = engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert evs[0]["type"] == "failed"
    assert p["inventory"]["wood"] == before
    assert p["vitals"]["energy"] == 5


def test_chop_gains_wood_and_skill():
    p = pawn("pawn_1")
    before_wood = p["inventory"]["wood"]
    before_skill = p["skills"]["woodcutting"]
    engine.resolve_actions({"pawn_1": ("Chop", None)})
    assert p["inventory"]["wood"] > before_wood
    assert p["skills"]["woodcutting"] >= before_skill


def test_attack_requires_target():
    evs = engine.resolve_actions({"pawn_1": ("Attack", None)})
    assert evs[0]["type"] == "failed"
    assert pawn("pawn_2")["vitals"]["hp"] == 90


def test_attack_self_rejected():
    evs = engine.resolve_actions({"pawn_1": ("Attack", "pawn_1")})
    assert evs[0]["type"] == "failed"
    assert pawn("pawn_1")["vitals"]["hp"] == 100


def test_attack_damages_target():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    t = pawn("pawn_2")
    t["skills"]["combat"] = 0
    before = t["vitals"]["hp"]
    engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert t["vitals"]["hp"] < before
    assert p["skills"]["combat"] > 6


def test_attack_energy_cost_enforced():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 15
    t = pawn("pawn_2")
    before = t["vitals"]["hp"]
    evs = engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert evs[0]["type"] == "failed"
    assert t["vitals"]["hp"] == before


def test_incapacitation_at_zero_hp():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    p["skills"]["combat"] = 20
    t = pawn("pawn_2")
    t["skills"]["combat"] = 0
    t["vitals"]["hp"] = 1
    engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert t["status"] == "incapacitated"
    assert t["vitals"]["hp"] == 0


def test_recovery_from_incapacitated():
    t = pawn("pawn_2")
    t["status"] = "incapacitated"
    t["vitals"]["hp"] = 0
    evs = engine.resolve_actions({"pawn_1": ("Rest", None)})
    assert any(e["type"] == "recover" for e in evs)
    assert t["status"] == "active"
    assert t["vitals"]["hp"] > 0


def test_relationship_changes_on_attack():
    p = pawn("pawn_1")
    p["vitals"]["energy"] = 100
    t = pawn("pawn_2")
    engine.resolve_actions({"pawn_1": ("Attack", "pawn_2")})
    assert p["relationships"]["pawn_2"] < 0
    assert t["relationships"]["pawn_1"] < 0
