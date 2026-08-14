import random

import events
import state

ACTION_COSTS = {"Chop": 10, "Scout": 15, "Attack": 20, "Rest": 0}
ACTIONS = tuple(ACTION_COSTS)
SKILL_MAX = 20
RECOVER_HEAL = 10


def _clamp(value, lo=0, hi=100):
    return max(lo, min(hi, value))


def _adjust_relationship(pawn, other_id, delta):
    rel = pawn["relationships"].get(other_id, 0)
    pawn["relationships"][other_id] = _clamp(rel + delta, -100, 100)


def _pay_cost(pawn, action):
    cost = ACTION_COSTS[action]
    if pawn["vitals"]["energy"] < cost:
        return False
    pawn["vitals"]["energy"] = _clamp(pawn["vitals"]["energy"] - cost)
    return True


def _gain_skill(pawn, skill):
    pawn["skills"][skill] = _clamp(pawn["skills"][skill] + 1, 0, SKILL_MAX)


def _do_rest(pawn, pawn_id):
    pawn["vitals"]["hp"] = _clamp(pawn["vitals"]["hp"] + 10)
    pawn["vitals"]["energy"] = _clamp(pawn["vitals"]["energy"] + 20)
    return events.add_event(
        "rest", actor=pawn_id, description=f"{pawn['name']} rests and recovers."
    )


def _do_chop(pawn, pawn_id):
    if not _pay_cost(pawn, "Chop"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to chop.",
        )
    wood = 3 + pawn["skills"]["woodcutting"] // 3 + random.choice([0, 1])
    pawn["inventory"]["wood"] += wood
    _gain_skill(pawn, "woodcutting")
    return events.add_event(
        "chop",
        actor=pawn_id,
        data={"wood": wood},
        description=f"{pawn['name']} chops wood, gathering {wood}.",
    )


def _do_scout(pawn, pawn_id):
    if not _pay_cost(pawn, "Scout"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to scout.",
        )
    skill = pawn["skills"]["scouting"]
    if random.random() < min(0.85, 0.4 + skill * 0.04):
        food = 2 + skill // 4 + random.choice([0, 1])
        pawn["inventory"]["food"] += food
        _gain_skill(pawn, "scouting")
        return events.add_event(
            "scout",
            actor=pawn_id,
            data={"food": food},
            description=f"{pawn['name']} scouts and finds {food} food.",
        )
    _gain_skill(pawn, "scouting")
    return events.add_event(
        "scout",
        actor=pawn_id,
        data={"food": 0},
        description=f"{pawn['name']} scouts but finds nothing.",
    )


def _do_attack(pawn, pawn_id, target):
    if not target:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "no_target"},
            description=f"{pawn['name']} swings at empty air.",
        )
    if target == pawn_id:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "self_target"},
            description=f"{pawn['name']} nearly strikes themself!",
        )
    tpawn = state.world_state["pawns"].get(target)
    if tpawn is None:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "unknown_target"},
            description=f"{pawn['name']} looks for a pawn that isn't there.",
        )
    if tpawn["status"] != "active":
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "target_down"},
            description=f"{pawn['name']} finds {tpawn['name']} already down.",
        )
    if not _pay_cost(pawn, "Attack"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to attack.",
        )

    damage = max(
        1,
        5 + pawn["skills"]["combat"] // 2 - tpawn["skills"]["combat"] // 4,
    )
    tpawn["vitals"]["hp"] = _clamp(tpawn["vitals"]["hp"] - damage)
    _gain_skill(pawn, "combat")
    _adjust_relationship(pawn, target, -10)
    _adjust_relationship(tpawn, pawn_id, -15)

    desc = f"{pawn['name']} attacks {tpawn['name']} for {damage} damage."
    if tpawn["vitals"]["hp"] <= 0:
        tpawn["vitals"]["hp"] = 0
        tpawn["status"] = "incapacitated"
        desc += f" {tpawn['name']} collapses!"
    return events.add_event(
        "attack",
        actor=pawn_id,
        target=target,
        data={"damage": damage},
        description=desc,
    )


def resolve_actions(intents):
    """intents: dict pawn_id -> (action, target). Applies deterministic effects."""
    resulting = []

    # Incapacitated pawns recover before anyone acts.
    for pawn_id, pawn in state.world_state["pawns"].items():
        if pawn["status"] != "active":
            pawn["vitals"]["hp"] = _clamp(pawn["vitals"]["hp"] + RECOVER_HEAL)
            if pawn["vitals"]["hp"] > 0:
                pawn["status"] = "active"
                resulting.append(
                    events.add_event(
                        "recover",
                        actor=pawn_id,
                        description=f"{pawn['name']} regains consciousness.",
                    )
                )
            else:
                resulting.append(
                    events.add_event(
                        "recover",
                        actor=pawn_id,
                        description=f"{pawn['name']} lies incapacitated.",
                    )
                )

    for pawn_id, (action, target) in intents.items():
        pawn = state.world_state["pawns"].get(pawn_id)
        if pawn is None or pawn["status"] != "active":
            continue
        if action == "Rest":
            resulting.append(_do_rest(pawn, pawn_id))
        elif action == "Chop":
            resulting.append(_do_chop(pawn, pawn_id))
        elif action == "Scout":
            resulting.append(_do_scout(pawn, pawn_id))
        elif action == "Attack":
            resulting.append(_do_attack(pawn, pawn_id, target))
        else:
            resulting.append(
                events.add_event(
                    "failed",
                    actor=pawn_id,
                    data={"reason": "unknown_action"},
                    description=f"{pawn['name']} hesitates, unsure what to do.",
                )
            )

    return resulting
