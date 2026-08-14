import json
import os

STATE_FILE = "terrarium_state.json"
LOG_FILE = "terrarium_log.jsonl"
MAX_HISTORY = 10

# Transient god effects (not persisted).
god_orders = {}    # pawn_id -> {"action": str, "target": str | None}
god_whispers = {}  # pawn_id -> str

DEFAULT_PERSONALITY = {"bravery": 5, "aggression": 5, "curiosity": 5, "sociability": 5}
DEFAULT_SKILLS = {"woodcutting": 5, "scouting": 5, "combat": 5}

world_state = {"tick": 1, "history": [], "pawns": {}}


def make_pawn(pawn_id, name, hp=100, energy=80, personality=None, skills=None):
    return {
        "id": pawn_id,
        "name": name,
        "status": "active",  # active | incapacitated
        "vitals": {"hp": hp, "energy": energy},
        "personality": personality if personality is not None else dict(DEFAULT_PERSONALITY),
        "skills": skills if skills is not None else dict(DEFAULT_SKILLS),
        "inventory": {"wood": 0, "food": 0},
        "relationships": {},
    }


def reset_world():
    world_state["tick"] = 1
    world_state["history"] = []
    world_state["pawns"] = {
        "pawn_1": make_pawn(
            "pawn_1",
            "Lumberjack",
            hp=100,
            energy=80,
            personality={"bravery": 6, "aggression": 7, "curiosity": 3, "sociability": 4},
            skills={"woodcutting": 8, "scouting": 3, "combat": 6},
        ),
        "pawn_2": make_pawn(
            "pawn_2",
            "Scout",
            hp=90,
            energy=50,
            personality={"bravery": 4, "aggression": 3, "curiosity": 8, "sociability": 6},
            skills={"woodcutting": 3, "scouting": 8, "combat": 4},
        ),
    }


def _migrate_pawn(pawn_id, pawn):
    if "vitals" in pawn:
        return pawn
    return make_pawn(
        pawn_id,
        pawn.get("name", pawn_id),
        hp=pawn.get("hp", 100),
        energy=pawn.get("energy", 80),
    )


def _migrate_event(ev):
    if isinstance(ev, dict):
        return ev
    return {
        "tick": 0,
        "type": "legacy",
        "actor": None,
        "target": None,
        "data": {},
        "description": str(ev),
    }


def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(world_state, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"State save failed: {e}")


def load_state():
    if not os.path.exists(STATE_FILE):
        reset_world()
        return
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        world_state["tick"] = loaded.get("tick", 1)
        world_state["history"] = [
            _migrate_event(h) for h in loaded.get("history", [])
        ][-MAX_HISTORY:]
        world_state["pawns"] = {
            pid: _migrate_pawn(pid, p) for pid, p in loaded.get("pawns", {}).items()
        }
        if not world_state["pawns"]:
            reset_world()
        print(
            f"Resumed from {STATE_FILE}: tick {world_state['tick']}, "
            f"{len(world_state['pawns'])} pawns"
        )
    except (OSError, ValueError) as e:
        print(f"State load failed (starting fresh): {e}")
        reset_world()


def status_summary():
    parts = []
    for pid, pawn in world_state["pawns"].items():
        tag = " [down]" if pawn["status"] != "active" else ""
        v = pawn["vitals"]
        parts.append(f"{pawn['name']}: HP={v['hp']} E={v['energy']}{tag}")
    return " | ".join(parts)
