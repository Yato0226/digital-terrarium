import random

import pytest

import engine
import events
import schema
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


def visitor_by_id(vid):
    return next(v for v in state.world_state["visitors"] if v["id"] == vid)


def add_visiting_visitor(kind, pos=(2, 2), hp=None):
    v = state.make_visitor(kind, list(pos))
    v["state"] = "visiting"
    v["hp"] = hp if hp is not None else engine.VISITOR_TYPES[kind]["hp"]
    v["inventory"] = dict(engine.VISITOR_TYPES[kind]["stock"])
    state.world_state["visitors"].append(v)
    return v


def test_visitor_spawns_at_interval(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = engine.VISITOR_INTERVAL
    evs = engine.tick_environment()
    assert len(state.world_state["visitors"]) == 1
    v = state.world_state["visitors"][0]
    assert v["kind"] == "Merchant"
    assert v["state"] == "arriving"
    assert v["pos"] == [1, 0]  # spawned at the edge (0,0), then took one step toward camp
    assert v["hp"] == engine.VISITOR_TYPES["Merchant"]["hp"]
    assert v["inventory"] == {"stone": 10, "fiber": 10}
    assert any(
        e["type"] == "visitor" and e["data"].get("action") == "spawn" for e in evs
    )


def test_no_visitor_spawn_mid_interval(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    state.world_state["tick"] = engine.VISITOR_INTERVAL - 1
    engine.tick_environment()
    assert state.world_state["visitors"] == []


def test_no_second_visitor_while_one_present(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    state.world_state["tick"] = engine.VISITOR_INTERVAL
    engine.tick_environment()
    assert len(state.world_state["visitors"]) == 1
    # A later interval tick must not stack a second visitor.
    state.world_state["tick"] = engine.VISITOR_INTERVAL * 2
    engine.tick_environment()
    assert len(state.world_state["visitors"]) == 1


def test_visitor_ai_walks_camp_and_leaves(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(random, "randint", lambda a, b: 3)
    state.world_state["tick"] = engine.VISITOR_INTERVAL
    all_evs = []
    for _ in range(9):
        all_evs += engine.tick_environment()
        state.world_state["tick"] += 1
    assert state.world_state["visitors"] == []
    actions = [e["data"].get("action") for e in all_evs if e["type"] == "visitor"]
    assert "spawn" in actions
    assert "arrive" in actions
    assert "depart" in actions
    assert "left" in actions


def test_bard_performs_at_camp(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    state.world_state["biome"]["campfire"] = 0  # no lit-fire morale confound
    p1 = pawn("pawn_1")
    p2 = pawn("pawn_2")
    add_visiting_visitor("Merchant")  # non-performing control visitor
    c1 = p1["vitals"]["morale"]
    c2 = p2["vitals"]["morale"]
    engine.tick_environment()
    c1 = p1["vitals"]["morale"] - c1
    c2 = p2["vitals"]["morale"] - c2
    # Now the same pawns, but a Bard visits.
    state.world_state["visitors"] = []
    add_visiting_visitor("Bard")
    b1 = p1["vitals"]["morale"]
    b2 = p2["vitals"]["morale"]
    evs = engine.tick_environment()
    b1 = p1["vitals"]["morale"] - b1
    b2 = p2["vitals"]["morale"] - b2
    assert b1 - c1 == engine.VISITOR_BARD_MORALE
    assert b2 - c2 == engine.VISITOR_BARD_MORALE
    assert any(
        e["type"] == "visitor" and e["data"].get("action") == "perform" for e in evs
    )


def test_share_merchant_barters_stone():
    p = pawn("pawn_1")
    p["pos"] = [2, 2]
    p["inventory"]["food"] = 5
    add_visiting_visitor("Merchant")
    evs = engine.resolve_actions({"pawn_1": ("Share", "visit_1")})
    assert p["inventory"]["food"] == 3
    assert p["inventory"]["stone"] == engine.BARTER_STONE_GAIN
    assert any(e["type"] == "barter" for e in evs)


def test_share_wanderer_gives_fiber():
    p = pawn("pawn_2")
    p["pos"] = [2, 2]
    p["inventory"]["food"] = 5
    add_visiting_visitor("Wanderer")
    evs = engine.resolve_actions({"pawn_2": ("Share", "visit_1")})
    assert p["inventory"]["food"] == 3
    assert p["inventory"]["fiber"] == 2
    assert any(e["type"] == "barter" for e in evs)


def test_share_visitor_requires_visiting_and_adjacent():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    p["inventory"]["food"] = 5
    add_visiting_visitor("Merchant", pos=(2, 2))
    evs = engine.resolve_actions({"pawn_1": ("Share", "visit_1")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "too_far"


def test_share_visitor_needs_food():
    p = pawn("pawn_1")
    p["pos"] = [2, 2]
    p["inventory"]["food"] = 0
    add_visiting_visitor("Merchant")
    evs = engine.resolve_actions({"pawn_1": ("Share", "visit_1")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "need_food"


def test_recruit_via_interact(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    p = pawn("pawn_2")
    p["pos"] = [2, 2]
    p["vitals"]["energy"] = 100
    add_visiting_visitor("Wanderer")
    recruited_name = state.world_state["visitors"][0]["name"]
    evs = engine.resolve_actions({"pawn_2": ("Interact", None, "invite to stay")})
    assert any(e["type"] == "recruit" for e in evs)
    assert len(state.world_state["pawns"]) == 3
    recruit = state.world_state["pawns"]["pawn_3"]
    assert recruit["name"] == recruited_name
    assert state.world_state["visitors"] == []
    assert recruit["pos"] == [2, 2]
    # The recruiter and recruit grow close.
    assert recruit["relationships"]["pawn_2"] == 20
    assert p["relationships"]["pawn_3"] == 20


def test_recruit_via_mate(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    p = pawn("pawn_2")
    p["pos"] = [2, 2]
    p["vitals"]["energy"] = 100
    add_visiting_visitor("Merchant")
    evs = engine.resolve_actions({"pawn_2": ("Mate", "visit_1")})
    assert any(e["type"] == "recruit" for e in evs)
    assert len(state.world_state["pawns"]) == 3
    assert state.world_state["visitors"] == []


def test_recruit_requires_same_tile():
    p = pawn("pawn_2")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    add_visiting_visitor("Wanderer", pos=(2, 2))
    evs = engine.resolve_actions({"pawn_2": ("Mate", "visit_1")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "not_same_tile"


def test_recruit_respects_colony_cap(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    while len(state.world_state["pawns"]) < engine.MAX_PAWNS:
        new_id = state.next_pawn_id()
        state.world_state["pawns"][new_id] = state.make_pawn(new_id, "Extra")
    p = pawn("pawn_2")
    p["pos"] = [2, 2]
    p["vitals"]["energy"] = 100
    add_visiting_visitor("Wanderer")
    evs = engine.resolve_actions({"pawn_2": ("Interact", None, "recruit")})
    assert not any(e["type"] == "recruit" for e in evs)
    assert len(state.world_state["pawns"]) == engine.MAX_PAWNS
    assert len(state.world_state["visitors"]) == 1


def test_attack_visitor_plunders_and_feels_guilt():
    p = pawn("pawn_2")  # aggression 3 < threshold
    p["pos"] = [2, 2]
    p["vitals"]["energy"] = 100
    add_visiting_visitor("Merchant", hp=5)  # one shot
    evs = engine.resolve_actions({"pawn_2": ("Attack", "visit_1")})
    attack = next(e for e in evs if e["type"] == "attack")
    assert attack["data"]["guilt"] is True
    assert attack["data"]["plunder"] == ["10 stone", "10 fiber"]
    assert p["inventory"]["stone"] == 10
    assert p["inventory"]["fiber"] == 10
    assert state.world_state["visitors"] == []
    guilt = next(m for m in p["moodlets"] if m["name"] == "Guilt")
    assert guilt["delta"] == engine.GUILT_MOODLET_DELTA


def test_aggressive_pawn_feels_no_guilt():
    p = pawn("pawn_1")  # aggression 7 >= threshold
    p["pos"] = [2, 2]
    p["vitals"]["energy"] = 100
    add_visiting_visitor("Merchant", hp=5)
    evs = engine.resolve_actions({"pawn_1": ("Attack", "visit_1")})
    attack = next(e for e in evs if e["type"] == "attack")
    assert attack["data"]["guilt"] is False
    assert not any(m["name"] == "Guilt" for m in p["moodlets"])


def test_nonlethal_visitor_attack_makes_them_flee():
    p = pawn("pawn_2")
    p["pos"] = [2, 2]
    p["vitals"]["energy"] = 100
    v = add_visiting_visitor("Merchant", hp=60)
    evs = engine.resolve_actions({"pawn_2": ("Attack", "visit_1")})
    attack = next(e for e in evs if e["type"] == "attack")
    assert attack["data"]["guilt"] is True
    assert v["state"] == "leaving"
    assert len(state.world_state["visitors"]) == 1


def test_attack_visitor_requires_adjacency():
    p = pawn("pawn_2")
    p["pos"] = [0, 0]
    p["vitals"]["energy"] = 100
    add_visiting_visitor("Merchant", pos=(2, 2))
    evs = engine.resolve_actions({"pawn_2": ("Attack", "visit_1")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "too_far"


def test_pacifist_refuses_visitor_attack():
    p = pawn("pawn_2")
    p["pos"] = [2, 2]
    p["vitals"]["energy"] = 100
    p["traits"] = ["Pacifist"]
    add_visiting_visitor("Merchant")
    evs = engine.resolve_actions({"pawn_2": ("Attack", "visit_1")})
    assert evs[0]["type"] == "failed"
    assert evs[0]["data"]["reason"] == "pacifist"
    assert len(state.world_state["visitors"]) == 1


def test_render_grid_shows_visitor():
    add_visiting_visitor("Merchant", pos=(0, 0))
    view = engine.render_grid()
    assert view.split("\n")[0].startswith("[🧭]")


def test_schema_target_includes_visitor_ids():
    add_visiting_visitor("Wanderer")
    TickResponse = schema.build_models()
    data = TickResponse.model_validate_json(
        '{"world_event": "ok", '
        '"pawn_1": {"action": "Share", "narrative": "trades", "target": "visit_1"}, '
        '"pawn_2": {"action": "Rest", "narrative": "rests"}}'
    )
    assert data.pawn_1.target == "visit_1"
