import json
import os
import random

STATE_FILE = "terrarium_state.json"
LOG_FILE = "terrarium_log.jsonl"
MAX_HISTORY = 10

# Transient god effects (not persisted).
god_orders = {}    # pawn_id -> {"action": str, "target": str | None}
god_whispers = {}  # pawn_id -> str

NAME_POOL = [
    "Willow", "Bramble", "Moss", "Fern", "Hazel", "Ash", "Rowan", "Ivy",
    "Thistle", "Clover", "Birch", "Cedar", "Ember", "Sable", "Onyx", "Rune",
    "Pip", "Mist", "Fable", "Wren", "Owl", "Cinder", "Nyx", "Rook",
]

JOB_POOL = [
    "Lumberjack", "Scout", "Forager", "Builder", "Hunter", "Fisher",
    "Herbalist", "Cook", "Watchman", "Smith", "Gatherer", "Tanner",
]


def next_pawn_id():
    nums = [
        int(pid.split("_")[1])
        for pid in world_state["pawns"]
        if pid.startswith("pawn_")
    ]
    return f"pawn_{max(nums, default=0) + 1}"

DEFAULT_PERSONALITY = {"bravery": 5, "aggression": 5, "curiosity": 5, "sociability": 5}
DEFAULT_SKILLS = {"woodcutting": 5, "scouting": 5, "combat": 5}

DEFAULT_BIOME = {
    "season": "Spring",
    "weather": "Clear",
    "day": 1,
    "campfire": 50,
    "shelter": 50,
    "wood_stock": 100,
    "food_stock": 100,
}

GRID_SIZE = 5
CAMP_POS = (2, 2)
DEFAULT_GRID = [
    ["🌲", "🌲", "🌲", "🌲", "🌲"],
    ["🌲", "🫐", "🪨", "🌊", "🌲"],
    ["🌲", "💀", "🏕️", "🌊", "🌲"],
    ["🌲", "🫐", "🌊", "🌲", "🌲"],
    ["🌲", "🌲", "🌲", "🌲", "🌲"],
]

world_state = {
    "tick": 1,
    "history": [],
    "biome": dict(DEFAULT_BIOME),
    "graveyard": [],
    "grid": [row[:] for row in DEFAULT_GRID],
    "pawns": {},
    "extinct": False,
}


def make_pawn(
    pawn_id,
    name,
    hp=100,
    energy=80,
    hunger=80,
    warmth=100,
    morale=80,
    personality=None,
    skills=None,
    job=None,
    sex=None,
):
    return {
        "id": pawn_id,
        "name": name,
        "job": job or "Wanderer",
        "sex": sex or random.choice(("M", "F")),
        "status": "active",  # active | incapacitated
        "vitals": {
            "hp": hp,
            "energy": energy,
            "hunger": hunger,
            "warmth": warmth,
            "morale": morale,
        },
        "personality": personality if personality is not None else dict(DEFAULT_PERSONALITY),
        "skills": skills if skills is not None else dict(DEFAULT_SKILLS),
        "inventory": {"wood": 0, "food": 0, "stone": 0, "fiber": 0},
        "gear": {"main_hand": None, "body": None},
        "relationships": {},
        "mental_break": None,
        "break_ticks": 0,
        "pregnant_ticks": 0,
        "child_ticks": 0,
        "pos": [CAMP_POS[0], CAMP_POS[1]],
        "counters": {
            "trees_felled": 0,
            "attacks_won": 0,
            "rations_shared": 0,
            "blizzards_survived": 0,
            "damage_dealt": 0,
        },
        "title": None,
        "born_tick": world_state["tick"],
        "starving_ticks": 0,
        "goal": None,
        "mother_id": None,
        "father_id": None,
        "partner_id": None,
        "partners": [],
    }


def reset_world():
    world_state["tick"] = 1
    world_state["history"] = []
    world_state["biome"] = dict(DEFAULT_BIOME)
    world_state["graveyard"] = []
    world_state["grid"] = [row[:] for row in DEFAULT_GRID]
    world_state["extinct"] = False
    world_state["pawns"] = {
        "pawn_1": make_pawn(
            "pawn_1",
            "Lumberjack",
            hp=100,
            energy=80,
            sex="M",
            personality={"bravery": 6, "aggression": 7, "curiosity": 3, "sociability": 4},
            skills={"woodcutting": 8, "scouting": 3, "combat": 6},
        ),
        "pawn_2": make_pawn(
            "pawn_2",
            "Scout",
            hp=90,
            energy=50,
            sex="F",
            personality={"bravery": 4, "aggression": 3, "curiosity": 8, "sociability": 6},
            skills={"woodcutting": 3, "scouting": 8, "combat": 4},
        ),
    }


def _migrate_pawn(pawn_id, pawn):
    base = make_pawn(pawn_id, pawn.get("name", pawn_id))
    if "vitals" in pawn:
        for key in base["vitals"]:
            if key in pawn["vitals"]:
                base["vitals"][key] = pawn["vitals"][key]
    for key in ("personality", "skills", "inventory", "relationships"):
        if isinstance(pawn.get(key), dict):
            base[key].update(pawn[key])
    if isinstance(pawn.get("counters"), dict):
        base["counters"].update(pawn["counters"])
    if isinstance(pawn.get("gear"), dict):
        base["gear"].update(pawn["gear"])
    if pawn.get("mental_break"):
        base["mental_break"] = pawn["mental_break"]
    if isinstance(pawn.get("break_ticks"), int):
        base["break_ticks"] = pawn["break_ticks"]
    if isinstance(pawn.get("pos"), list) and len(pawn["pos"]) == 2:
        base["pos"] = pawn["pos"]
    if isinstance(pawn.get("born_tick"), int):
        base["born_tick"] = pawn["born_tick"]
    if isinstance(pawn.get("starving_ticks"), int):
        base["starving_ticks"] = pawn["starving_ticks"]
    if pawn.get("title"):
        base["title"] = pawn["title"]
    if pawn.get("job"):
        base["job"] = pawn["job"]
    if pawn.get("sex") in ("M", "F"):
        base["sex"] = pawn["sex"]
    if isinstance(pawn.get("pregnant_ticks"), int):
        base["pregnant_ticks"] = pawn["pregnant_ticks"]
    if isinstance(pawn.get("child_ticks"), int):
        base["child_ticks"] = pawn["child_ticks"]
    if pawn.get("status") in ("active", "incapacitated"):
        base["status"] = pawn["status"]
    if isinstance(pawn.get("goal"), dict):
        base["goal"] = pawn["goal"]
    for key in ("mother_id", "father_id", "partner_id"):
        if pawn.get(key) in (None,) or isinstance(pawn.get(key), str):
            base[key] = pawn.get(key)
    if isinstance(pawn.get("partners"), list):
        base["partners"] = [p for p in pawn["partners"] if isinstance(p, str)]
    return base


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
        world_state["extinct"] = loaded.get("extinct", False)
        world_state["history"] = [
            _migrate_event(h) for h in loaded.get("history", [])
        ][-MAX_HISTORY:]
        world_state["pawns"] = {
            pid: _migrate_pawn(pid, p) for pid, p in loaded.get("pawns", {}).items()
        }
        world_state.setdefault("biome", dict(DEFAULT_BIOME))
        world_state.setdefault("graveyard", [])
        world_state.setdefault("grid", [row[:] for row in DEFAULT_GRID])
        if not world_state["pawns"]:
            if world_state["graveyard"]:
                # Real extinction: keep the dataset and stay paused.
                world_state["extinct"] = True
            else:
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
        parts.append(
            f"{pawn['name']}: HP={v['hp']} E={v['energy']} H={v['hunger']}{tag}"
        )
    return " | ".join(parts)
