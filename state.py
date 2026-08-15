import json
import os
import random

STATE_FILE = "terrarium_state.json"
LOG_FILE = "terrarium_log.jsonl"
MAX_HISTORY = 10

# Transient god effects (not persisted).
god_orders = {}    # pawn_id -> {"action": str, "target": str | None}
god_whispers = {}  # pawn_id -> str

# Transient director feedback (not persisted): pawn_id -> {"action", "reason", "count"}.
# Consecutive failed intents after a feasibility reason; prompts build_prompt into hints.
failed_intents = {}

MAX_CHRONICLE = 24  # keep the last N seasonal chronicle entries

# Transient seasonal-chronicle signal (not persisted): set by engine.tick_environment
# to the new season name when the season turns, consumed by core.run_tick after the
# tick lock is released. Cleared in reset_world.
pending_chronicle = None

# Transient monument signal (not persisted): set by engine._do_build when the
# Ancestral Monolith completes, consumed by core.run_tick (outside the lock) to
# write the inscription. Cleared in reset_world.
pending_monument = None

NAME_POOL = [
    "Willow", "Bramble", "Moss", "Fern", "Hazel", "Ash", "Rowan", "Ivy",
    "Thistle", "Clover", "Birch", "Cedar", "Ember", "Sable", "Onyx", "Rune",
    "Pip", "Mist", "Fable", "Wren", "Owl", "Cinder", "Nyx", "Rook",
]

JOB_POOL = [
    "Lumberjack", "Scout", "Forager", "Builder", "Hunter", "Fisher",
    "Herbalist", "Cook", "Watchman", "Smith", "Gatherer", "Tanner",
]

VISITOR_NAMES = {
    "Merchant": ["Bartering Bex", "Trading Tomas", "Silver Quill", "Haggling Hilda", "Peddler Pike"],
    "Wanderer": ["Lost Lila", "Wayfarer Wynn", "Roaming Rhea", "Stray Stellan", "Drifter Dara"],
    "Bard": ["Lark the Minstrel", "Singing Sable", "Fiddle Fen", "Chanter Cora", "Busk Bodhi"],
}

RAIDER_NAMES = ["Brigand", "Marauder", "Looter", "Cutpurse", "Highwayman", "Rustler"]

TRAITS = ("Night Owl", "Brawler", "Pyromaniac", "Pacifist", "Iron Stomach")

TRAIT_EMOJI = {
    "Night Owl": "🦉",
    "Brawler": "🥊",
    "Pyromaniac": "🔥",
    "Pacifist": "🕊️",
    "Iron Stomach": "🍽️",
}


def next_pawn_id():
    nums = [
        int(pid.split("_")[1])
        for pid in world_state["pawns"]
        if pid.startswith("pawn_")
    ]
    return f"pawn_{max(nums, default=0) + 1}"


def next_wild_id():
    nums = [
        int(w["id"].split("_")[1])
        for w in world_state["wildlife"]
        if w["id"].startswith("wild_")
    ]
    return f"wild_{max(nums, default=0) + 1}"


def next_visitor_id():
    nums = [
        int(v["id"].split("_")[1])
        for v in world_state.get("visitors", [])
        if v["id"].startswith("visit_")
    ]
    return f"visit_{max(nums, default=0) + 1}"


def next_raider_id():
    nums = [
        int(r["id"].split("_")[1])
        for r in world_state.get("raiders", [])
        if r["id"].startswith("scavenger_")
    ]
    return f"scavenger_{max(nums, default=0) + 1}"


def next_heirloom_id():
    nums = [
        int(h["id"].split("_")[1])
        for h in world_state["heirlooms"]
        if h["id"].startswith("heirloom_")
    ]
    return f"heirloom_{max(nums, default=0) + 1}"


def make_animal(species, pos=None, hp=100):
    """Non-pawn wildlife entity: prey flee, predators stalk, tamed pets stay at camp."""
    if pos is None:
        pos = [CAMP_POS[0], CAMP_POS[1]]
    return {
        "id": next_wild_id(),
        "species": species,
        "pos": [pos[0], pos[1]],
        "state": "wandering",  # wandering | tamed
        "hp": hp,
        "spawn_tick": world_state["tick"],
        "tamed_by": None,
    }


def make_visitor(kind, pos=None):
    """Transient wandering NPC: walks to camp, lingers, then walks off the grid."""
    if pos is None:
        pos = [CAMP_POS[0], CAMP_POS[1]]
    return {
        "id": next_visitor_id(),
        "kind": kind,
        "name": random.choice(VISITOR_NAMES.get(kind, ["Traveler"])),
        "pos": [pos[0], pos[1]],
        "hp": 60,
        "state": "arriving",  # arriving | visiting | leaving
        "ticks_left": 0,
        "inventory": {"stone": 0, "fiber": 0, "food": 0},
        "spawn_tick": world_state["tick"],
    }


def make_raider(pos=None):
    """Hostile scavenger: marches to the camp, steals food, and flees."""
    if pos is None:
        pos = [CAMP_POS[0], CAMP_POS[1]]
    return {
        "id": next_raider_id(),
        "kind": "Scavenger",
        "name": random.choice(RAIDER_NAMES),
        "pos": [pos[0], pos[1]],
        "hp": 45,
        "state": "marching",  # marching | fleeing
        "slowed": 0,
        "stolen": 0,
        "spawn_tick": world_state["tick"],
    }

DEFAULT_PERSONALITY = {"bravery": 5, "aggression": 5, "curiosity": 5, "sociability": 5}
DEFAULT_SKILLS = {"woodcutting": 5, "scouting": 5, "combat": 5}

DEFAULT_MODIFIERS = {"regrowth": 1.0, "cold": 1.0, "spawn": 1.0}

DEFAULT_BIOME = {
    "season": "Spring",
    "weather": "Clear",
    "day": 1,
    "campfire": 50,
    "shelter": 50,
    "wood_stock": 100,
    "food_stock": 100,
    "granary": False,
    "palisade": 0,
    "flood": 0,
    "flooded": [],
    "miasma": 0,
    "aurora": False,
    "modifiers": dict(DEFAULT_MODIFIERS),
}


def default_biome():
    """Fresh biome dict with its own modifiers (no shared nested-dict aliasing)."""
    biome = dict(DEFAULT_BIOME)
    biome["modifiers"] = dict(DEFAULT_MODIFIERS)
    return biome

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
    "biome": default_biome(),
    "graveyard": [],
    "grid": [row[:] for row in DEFAULT_GRID],
    "pawns": {},
    "wildlife": [],
    "chronicle": [],
    "heirlooms": [],
    "adoptions": {},
    "extinct": False,
    "tiles": {},
    "visitors": [],
    "raiders": [],
    "monument": {"wood": 0, "stone": 0, "done": False, "inscription": None},
    "traditions": {"tag": None, "predators_slain": 0, "trees_felled": 0, "rations_shared": 0},
    "custom_recipes": {},
    "active_quests": [],
    "patch_version": "v1.0",
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
    traits=None,
):
    if traits is None:
        traits = random.sample(TRAITS, k=random.choice((1, 2)))
    return {
        "id": pawn_id,
        "name": name,
        "job": job or "Wanderer",
        "sex": sex or random.choice(("M", "F")),
        "status": "active",  # active | incapacitated
        "traits": [t for t in traits if t in TRAITS],
        "moodlets": [],  # [{"name", "delta", "ticks_left"}] — episodic morale drains
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
    global pending_chronicle, pending_monument
    world_state["tick"] = 1
    world_state["history"] = []
    world_state["biome"] = default_biome()
    world_state["graveyard"] = []
    world_state["grid"] = [row[:] for row in DEFAULT_GRID]
    world_state["wildlife"] = []
    world_state["chronicle"] = []
    world_state["heirlooms"] = []
    world_state["adoptions"] = {}
    world_state["extinct"] = False
    world_state["tiles"] = {}
    world_state["visitors"] = []
    world_state["raiders"] = []
    world_state["monument"] = {"wood": 0, "stone": 0, "done": False, "inscription": None}
    world_state["traditions"] = {"tag": None, "predators_slain": 0, "trees_felled": 0, "rations_shared": 0}
    world_state["custom_recipes"] = {}
    world_state["active_quests"] = []
    world_state["patch_version"] = "v1.0"
    pending_chronicle = None
    pending_monument = None
    failed_intents.clear()
    world_state["pawns"] = {
        "pawn_1": make_pawn(
            "pawn_1",
            "Lumberjack",
            hp=100,
            energy=80,
            sex="M",
            personality={"bravery": 6, "aggression": 7, "curiosity": 3, "sociability": 4},
            skills={"woodcutting": 8, "scouting": 3, "combat": 6},
            traits=["Brawler"],
        ),
        "pawn_2": make_pawn(
            "pawn_2",
            "Scout",
            hp=90,
            energy=50,
            sex="F",
            personality={"bravery": 4, "aggression": 3, "curiosity": 8, "sociability": 6},
            skills={"woodcutting": 3, "scouting": 8, "combat": 4},
            traits=["Night Owl"],
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
    if isinstance(pawn.get("traits"), list):
        base["traits"] = [t for t in pawn["traits"] if t in TRAITS]
        if not base["traits"]:
            base["traits"] = random.sample(TRAITS, k=random.choice((1, 2)))
    if isinstance(pawn.get("moodlets"), list):
        base["moodlets"] = [
            {
                "name": m.get("name"),
                "delta": int(m.get("delta", 0)),
                "ticks_left": int(m.get("ticks_left", 0)),
            }
            for m in pawn["moodlets"]
            if isinstance(m, dict) and m.get("name")
        ]
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
        if "biome" in loaded:
            world_state["biome"] = loaded["biome"]
        else:
            world_state["biome"] = default_biome()
        world_state["biome"].setdefault("granary", False)
        world_state["biome"].setdefault("palisade", 0)
        world_state["biome"].setdefault("flood", 0)
        world_state["biome"].setdefault("flooded", [])
        world_state["biome"].setdefault("miasma", 0)
        world_state["biome"].setdefault("aurora", False)
        modifiers = world_state["biome"].setdefault("modifiers", {})
        for key in DEFAULT_MODIFIERS:
            modifiers.setdefault(key, DEFAULT_MODIFIERS[key])
        world_state.setdefault("graveyard", [])
        world_state.setdefault("grid", [row[:] for row in DEFAULT_GRID])
        world_state.setdefault("wildlife", [])
        if "chronicle" in loaded:
            world_state["chronicle"] = loaded["chronicle"][-MAX_CHRONICLE:]
        else:
            world_state.setdefault("chronicle", [])
        if "heirlooms" in loaded:
            world_state["heirlooms"] = loaded["heirlooms"]
        else:
            world_state.setdefault("heirlooms", [])
        if "adoptions" in loaded:
            world_state["adoptions"] = loaded["adoptions"]
        else:
            world_state.setdefault("adoptions", {})
        if "tiles" in loaded:
            world_state["tiles"] = loaded["tiles"]
        else:
            world_state.setdefault("tiles", {})
        world_state.setdefault("visitors", [])
        world_state.setdefault("raiders", [])
        world_state.setdefault("custom_recipes", {})
        world_state.setdefault("active_quests", [])
        world_state.setdefault("patch_version", "v1.0")
        monument = world_state.setdefault(
            "monument", {"wood": 0, "stone": 0, "done": False, "inscription": None}
        )
        monument.setdefault("wood", 0)
        monument.setdefault("stone", 0)
        monument.setdefault("done", False)
        monument.setdefault("inscription", None)
        traditions = world_state.setdefault(
            "traditions",
            {"tag": None, "predators_slain": 0, "trees_felled": 0, "rations_shared": 0},
        )
        traditions.setdefault("tag", None)
        traditions.setdefault("predators_slain", 0)
        traditions.setdefault("trees_felled", 0)
        traditions.setdefault("rations_shared", 0)
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
