import random
import re

import events
import state

ACTION_COSTS = {
    "Chop": 10,
    "Rest": 0,
    "Scout": 15,
    "Attack": 20,
    "Forage": 10,
    "Build": 15,
    "Share": 5,
    "Move": 5,
    "Mate": 10,
    "Interact": 5,
}
ACTIONS = tuple(ACTION_COSTS)
SKILL_MAX = 20
RECOVER_HEAL = 10

WILDLIFE = {
    "Deer": {"emoji": "🦌", "kind": "prey", "hp": 50, "food_yield": 15, "fiber_yield": 10, "bite_damage": 0},
    "Rabbit": {"emoji": "🐇", "kind": "prey", "hp": 30, "food_yield": 10, "fiber_yield": 5, "bite_damage": 0},
    "Wolf": {"emoji": "🐺", "kind": "predator", "hp": 80, "food_yield": 20, "fiber_yield": 5, "bite_damage": 8},
    "Bear": {"emoji": "🐻", "kind": "predator", "hp": 120, "food_yield": 35, "fiber_yield": 15, "bite_damage": 15},
}
PREY_SPECIES = ("Deer", "Rabbit")
PREDATOR_SPECIES = ("Wolf", "Bear")
WILDLIFE_MAX = 3
PALISADE_MAX = 3
PET_MORALE_BONUS = 2
PREY_DESPAWN_CHANCE = 0.1
FEASIBILITY_REASONS = {
    "low_energy",
    "need_wood",
    "wrong_tile",
    "forest_depleted",
    "food_depleted",
    "too_far",
    "target_down",
    "off_grid",
    "pacifist",
    "flooded",
}

GRID_SIZE = state.GRID_SIZE
CAMP_POS = state.CAMP_POS
CAMP_RANGE = 1
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
FOREST_TILES = {"🌲"}
FORAGE_TILES = {"🫐", "🌊"}
BUILD_TILE = "🏕️"
RUIN_TILE = "💀"
QUARRY_TILE = "🪨"

# Wildfire & dynamic tile lifecycle (Stage 4).
BURNING_TILE = "🔥"
ASH_TILE = "🌫️"
FIREBREAK_TILE = "🫐"
FIRE_TICKS = 3
REGROW_TICKS = 40
FIRE_WOOD_DRAIN = 10
FIRE_DAMAGE = 5
FIRE_SPREAD_CHANCE = 0.5
FIRE_CAMP_SPREAD_CHANCE = 0.25
LIGHTNING_CHANCE = 0.05
HEATWAVE_FIRE_CHANCE = 0.10
HIGH_WOOD = 60
CAMP_BURN_CAMPFIRE = 10
CAMP_BURN_SHELTER = 10

# Seasonal disasters & environmental anomalies (Stage 4 part 2).
RIVER_TILE = "🌊"
FLOOD_TICKS = 3
FLOOD_CHANCE = 0.15
FLOOD_FOOD_BONUS = 5
AURORA_CHANCE = 0.1
AURORA_MORALE = 10
MIASMA_TICKS = 2
MIASMA_CHANCE = 0.15
MIASMA_DAMAGE = 5

# Stage 5 visitors & wandering nomads.
VISITOR_INTERVAL = 150
VISITOR_TYPES = {
    "Merchant": {"emoji": "🧭", "hp": 60, "stock": {"stone": 10, "fiber": 10}},
    "Wanderer": {"emoji": "🥾", "hp": 40, "stock": {"fiber": 2, "food": 2}},
    "Bard": {"emoji": "🎻", "hp": 50, "stock": {}},
}
VISITOR_STAY_MIN = 3
VISITOR_STAY_MAX = 5
VISITOR_BARD_MORALE = 5
BARTER_FOOD_COST = 2
BARTER_STONE_GAIN = 3
RECRUIT_BASE_CHANCE = 0.3
RECRUIT_SOCIABILITY_FACTOR = 0.05
GUILT_MOODLET_DELTA = -5
GUILT_MOODLET_TICKS = 15
AGGRESSION_GUILT_THRESHOLD = 6

# Stage 6 monument (Ancestral Monolith).
MONUMENT_WOOD_NEEDED = 20
MONUMENT_STONE_NEEDED = 15
MONUMENT_WOOD_PER_BUILD = 5
MONUMENT_STONE_PER_BUILD = 5
MONUMENT_MORALE_FLOOR = 10
MONUMENT_INSULATION = 2

# Stage 9 (Phase 2) monolith oracle & rune archive.
MONUMENT_RUNE_MAX = 12
MONUMENT_PRAY_MORALE = 8
MONUMENT_PRAY_XP = 1
MONUMENT_WARMTH_BLESSING = 6
MONUMENT_WARMTH_MOODLET_DELTA = 2
MONUMENT_WARMTH_BLESSING_TICKS = 20

# Stage 10 (Phase 2) ancient pre-history: the Ruins as the Sunken Tribe's remnants.
SUNKEN_TRIBE = "The Sunken Tribe"
RUIN_DISCOVERY_CHANCE = 0.25
RUIN_WARNING_XP = 2
RUIN_WARNING_MORALE = 5
LORE_FRAGMENTS = (
    "A mosaic of a drowned city, its towers half-swallowed by black water.",
    "A cracked tablet reads: 'We were the Sunken Tribe, and the sea did not spare us.'",
    "Pottery stamped with a spiral wave-sign — the mark of the Sunken Tribe.",
    "A mural shows the Sunken Tribe raising a great wall against the rising tide.",
    "A bone whistle, salt-crusted, still holds the sea's breath.",
    "A child's half-finished toy boat carved from driftwood.",
    "A charred ledger lists offerings 'to the deep' that were never made.",
    "Rusting fishhooks the size of a hand, left in a stone jar.",
)
RUIN_WARNINGS = (
    "'When the river burns, flee to high ground' — a wall warning, faint but legible.",
    "'The floods come twice; the second flood takes what the first spared.'",
    "'Do not sleep beside the water in thaw' — carved in the old tongue.",
    "'The grey walkers come with the winter cold; keep the fire fed.'",
    "'Beware the drowned ones who rise at night' — a lintel carved in haste.",
)
RUIN_BLUEPRINTS = {
    "Sunken Harpoon": {
        "materials": {"wood": 4, "stone": 2},
        "slot": "main_hand",
        "tier": 4,
        "bonus": {"combat": 3},
    },
    "Tidal Shawl": {
        "materials": {"fiber": 6, "stone": 1},
        "slot": "body",
        "tier": 4,
        "bonus": {"scouting": 2, "fiber": 2},
    },
}

# Stage 11 (Phase 3) qualitative relational badges — durable labels earned by deeds.
BADGES = ("Lifesaver", "Betrayer", "Indebted", "Mentor", "Widow")
BETRAY_RELATIONSHIP = 25  # attacking someone bonded to you earns "Betrayer"

# Stage 12 (Phase 3) multigenerational blood feuds.
FEUD_INHERIT = -40     # children are seeded hostile to their parents' rivals
BRAWL_CHANCE = 0.2     # per tick, mutual rivals sharing the camp tile may brawl
BRAWL_DAMAGE = 3
BRAWL_RELATIONSHIP_DROP = 10
BRAWL_MORALE_DROP = 5

# Stage 13 (Phase 3) free-form dynamic roles — LLM-invented titles, keyword-bucketed perks.
TITLE_WORDS = {
    "martial": ("fang", "claw", "blade", "slayer", "breaker", "warrior", "warden", "guard", "hunter", "bane", "tooth", "iron"),
    "nurture": ("keeper", "hearth", "mother", "nurturer", "caretaker", "herder", "tender", "provider", "cook", "farmer", "gatherer"),
    "spirit": ("seer", "shaman", "spirit", "oracle", "rite", "mourner", "priest", "sage", "mystic", "waker", "whisper"),
}
TITLE_MAX_LEN = 28
TITLE_MARTIAL_DEFENSE = 2   # martial titles shave damage taken
TITLE_NURTURE_SHARE = 1     # nurturing titles share +1 food
TITLE_SPIRIT_GRIEF_DIV = 2  # spiritual titles halve Grief duration

# Stage 6 agriculture (Farm Plots on tilled Meadow tiles).
FARM_TILE = "🌾"
FARM_GROW_TICKS = 20
FARM_HARVEST_FOOD = 15
FARM_HARVEST_FIBER = 5
FARM_GROW_SEASONS = ("Spring", "Summer")

# Stage 7 emergent traditions (colony-wide culture tags).
HUNTERS_TAG = "Hunters of the North"
FORESTERS_TAG = "Children of the Forest"
KINDRED_TAG = "Kindred of the Hearth"
HUNTERS_THRESHOLD = 10      # predators slain
FORESTERS_THRESHOLD = 100   # trees felled
KINDRED_THRESHOLD = 20      # rations shared
HUNTERS_COMBAT_XP = 2       # hunting XP while hunting
HUNTERS_COLD_REDUCTION = 1  # cold-weather penalties reduced
FORESTERS_CHOP_BONUS = 1    # wood yield from Chop
KINDRED_SOCIAL_MORALE = 8   # social Interact morale (base 5)

# Stage 7 festivals & funerary rites.
FEAST_SEASONS = ("Winter", "Summer")
FEAST_FOOD_REQUIRED = 15    # camp food_stock must exceed this
FEAST_FOOD_COST = 5         # consumed from the colony stock
FEAST_MORALE = 15           # every active pawn
FESTIVE_MOODLET_DELTA = 5
FESTIVE_MOODLET_TICKS = 15
RITE_TILES = (BUILD_TILE, RUIN_TILE)  # Camp or Ruins
BELOVED_RELATIONSHIP = 25   # avg relationship to survivors for "beloved"

# Stage 8 scavenger raids.
RAID_SEASON = "Autumn"
RAID_INTERVAL = 100         # tick cadence; raid lands on Autumn's first tick
RAID_WEALTH_THRESHOLD = 30  # combined food+wood held by the colony
RAID_MAX = 2                # raiders in the world at once
RAID_HP = 45
RAID_STEAL = 5              # food stolen per raid before fleeing
RAID_DEFEND_DAMAGE = 4      # high-combat counter-strike at the camp
RAIDER_EMOJI = "🥷"

# Stage 9 autonomous world engine: dynamic synthesis & balance patches.
MODIFIER_MIN = 0.7           # strict Python-enforced clamp bounds
MODIFIER_MAX = 1.3
CUSTOM_RECIPE_TIER_MIN = 4   # synthesized blueprints sit above static tools
QUEST_MAX = 3                # concurrent world prophecies
QUEST_REWARD_MORALE = 15
QUEST_MORALE_CAP = 25        # upper bound an Architect may propose per quest

INSPIRED_MORALE = 80
BREAK_MORALE = 20
BREAK_TICKS = 3
BREAK_RECOVERY_MORALE = 20

RECIPES = {
    "Stone Axe": {"wood": 3, "stone": 2, "slot": "main_hand"},
    "Flint Spear": {"wood": 2, "stone": 1, "slot": "main_hand"},
    "Warm Coat": {"fiber": 5, "slot": "body"},
}
TOOL_TIER = {"Flint Spear": 3, "Stone Axe": 2, "Warm Coat": 1}
SPEAR_DAMAGE = 4
COAT_INSULATION = 4

# Heirlooms: relics dropped by titled pawns who die holding a tool.
HEIRLOOM_BONUS = {
    "Stone Axe": {"woodcutting": 1},
    "Flint Spear": {"combat": 1},
}
HEIRLOOM_MOODLET_DELTA = 5
HEIRLOOM_MOODLET_TICKS = 20

SEASON_TICKS = 100
DAY_CYCLE = 20
DAY_LENGTH = 10
TICKS_PER_DAY = DAY_CYCLE  # one full day/night cycle = 20 ticks
SEASONS = ("Spring", "Summer", "Autumn", "Winter")
WEATHER_OPTIONS = {
    "Spring": ("Clear", "Rain", "Clear", "Rain", "Clear"),
    "Summer": ("Clear", "Heatwave", "Clear", "Rain", "Clear"),
    "Autumn": ("Clear", "Rain", "Storm", "Clear", "Storm"),
    "Winter": ("Clear", "Snow", "Blizzard", "Clear", "Blizzard"),
}
WEATHER_COLD = {
    "Clear": 0,
    "Rain": 2,
    "Storm": 4,
    "Snow": 4,
    "Blizzard": 8,
    "Heatwave": 0,
}
SEASON_COLD = {"Spring": 0, "Summer": 0, "Autumn": 3, "Winter": 10}
WEATHER_CHANGE_CHANCE = 0.2

HUNGER_DRAIN = 2
EAT_THRESHOLD = 20
EAT_REPLENISH = 35
STARVE_HP = 5
STARVE_ENERGY = 5
WARMTH_RECOVERY = 5
CAMPFIRE_WARMTH = 8
SHELTER_WARMTH = 4
FROSTBITE_HP = 3
HEATWAVE_ENERGY = 3
CAMPFIRE_FUEL = 1
CAMPFIRE_FEED_GAIN = 2
CAMPFIRE_DECAY = 3
BUILD_WOOD_COST = 3
BUILD_GAIN = 8
SHARE_FOOD = 1
REGROWTH = 1
REGROWTH_SPRING = 2

MATE_RELATIONSHIP = 25
RIVAL_THRESHOLD = -25
RELATIONSHIP_DECAY = 5  # per ingame day: bonds drift toward 0 each dawn
CONCEPTION_CHANCE = 0.5
PREGNANCY_TICKS = TICKS_PER_DAY  # 1 day (20 ticks)
CHILD_MATURITY = 2 * TICKS_PER_DAY  # 2 days (40 ticks)
MAX_PAWNS = 10
NEWBORN_HP = 60
NEWBORN_ENERGY = 40

ELDER_AGE = 10 * TICKS_PER_DAY  # 10 days (200 ticks)
OLD_AGE_DEATH_CHANCE = 0.02
OLD_AGE_MAX = 16 * TICKS_PER_DAY  # 16 days (320 ticks)
ELDER_ENERGY_TAX = 1
ELDER_MORALE_TAX = 1
ELDER_REST_PENALTY = 5


def _clamp(value, lo=0, hi=100):
    return max(lo, min(hi, value))


def _record_feasibility(pawn_id, action, reason):
    info = state.failed_intents.get(pawn_id)
    if info and info.get("reason") == reason and info.get("action") == action:
        info["count"] += 1
    else:
        state.failed_intents[pawn_id] = {"action": action, "reason": reason, "count": 1}


def age_of(pawn):
    return state.world_state["tick"] - pawn.get("born_tick", state.world_state["tick"])


def is_elder(pawn):
    return age_of(pawn) >= ELDER_AGE


def _tick_moodlets(pawn):
    net = 0
    kept = []
    for m in pawn.get("moodlets", []):
        net += m["delta"]
        m["ticks_left"] -= 1
        if m["ticks_left"] > 0:
            kept.append(m)
    pawn["moodlets"] = kept
    return net


def _add_moodlet(pawn, name, delta, ticks_left):
    moodlets = pawn.setdefault("moodlets", [])
    if name == "Grief" and _title_role(pawn) == "spirit":
        ticks_left = max(1, ticks_left // TITLE_SPIRIT_GRIEF_DIV)
    for m in moodlets:
        if m["name"] == name:
            m["delta"] = delta
            m["ticks_left"] = max(m["ticks_left"], ticks_left)
            return
    moodlets.append({"name": name, "delta": delta, "ticks_left": ticks_left})


def _inherit_traits(mother, father):
    traits_m = mother.get("traits", [])
    traits_f = father.get("traits", [])
    child_traits = []
    if traits_m and random.random() < 0.5:
        child_traits.append(random.choice(traits_m))
    if traits_f and random.random() < 0.5:
        chosen = random.choice(traits_f)
        if chosen not in child_traits:
            child_traits.append(chosen)
    if not child_traits:
        if traits_m:
            child_traits.append(random.choice(traits_m))
        elif traits_f:
            child_traits.append(random.choice(traits_f))
    if not child_traits:
        child_traits.append(random.choice(state.TRAITS))
    return child_traits[:2]


def _inherit_feuds(child, mother, father):
    """Children are born carrying their parents' rivalries (multigenerational feuds)."""
    rivals = set()
    for parent in (mother, father):
        if parent is None:
            continue
        for oid, rel in parent["relationships"].items():
            other = state.world_state["pawns"].get(oid)
            if other is None:
                continue
            if (
                rel <= RIVAL_THRESHOLD
                and other["relationships"].get(parent["id"], 0) <= RIVAL_THRESHOLD
            ):
                rivals.add(oid)
    for oid in rivals:
        child["relationships"][oid] = FEUD_INHERIT


def _camp_brawls(result):
    """Mutual rivals sharing the camp tile may come to blows — feud escalation."""
    at_camp = [
        (pid, p)
        for pid, p in state.world_state["pawns"].items()
        if p["status"] == "active" and _tile_at(*p["pos"]) == BUILD_TILE
    ]
    involved = set()
    for i, (aid, a) in enumerate(at_camp):
        for bid, b in at_camp[i + 1 :]:
            if aid in involved and bid in involved:
                continue
            if (
                a["relationships"].get(bid, 0) <= RIVAL_THRESHOLD
                and b["relationships"].get(aid, 0) <= RIVAL_THRESHOLD
            ):
                if random.random() >= BRAWL_CHANCE:
                    continue
                involved.add(aid)
                involved.add(bid)
                for p in (a, b):
                    p["vitals"]["hp"] = _clamp(p["vitals"]["hp"] - BRAWL_DAMAGE)
                    p["vitals"]["morale"] = _clamp(p["vitals"]["morale"] - BRAWL_MORALE_DROP)
                _adjust_relationship(a, bid, -BRAWL_RELATIONSHIP_DROP)
                _adjust_relationship(b, aid, -BRAWL_RELATIONSHIP_DROP)
                result.append(
                    events.add_event(
                        "brawl",
                        actor=aid,
                        target=bid,
                        data={"damage": BRAWL_DAMAGE},
                        description=(
                            f"{a['name']} and {b['name']} come to blows at the camp — "
                            f"the old feud flares up ({BRAWL_DAMAGE} damage each)."
                        ),
                    )
                )


def _adjust_relationship(pawn, other_id, delta):
    rel = pawn["relationships"].get(other_id, 0)
    pawn["relationships"][other_id] = _clamp(rel + delta, -100, 100)


def _grant_badge(pawn, badge):
    """Personal badge (e.g. Widow) — deduped."""
    if badge not in pawn.setdefault("badges", []):
        pawn["badges"].append(badge)


def _grant_rel_badge(pawn, other_id, badge):
    """Directional badge pawn → other (Lifesaver/Betrayer/Indebted/Mentor) — deduped."""
    rel_badges = pawn.setdefault("rel_badges", {})
    lst = rel_badges.setdefault(other_id, [])
    if badge not in lst:
        lst.append(badge)


def _decay_relationships():
    """Once per ingame day, every relationship drifts one step toward 0."""
    for pawn in state.world_state["pawns"].values():
        rels = pawn["relationships"]
        for other, value in list(rels.items()):
            if value > 0:
                rels[other] = max(0, value - RELATIONSHIP_DECAY)
            elif value < 0:
                rels[other] = min(0, value + RELATIONSHIP_DECAY)
            else:
                rels.pop(other, None)


def _are_kin(a, b):
    """True if two pawns share a parent or one is the direct parent of the other."""
    if a["id"] == b["id"]:
        return True
    parents_a = {a.get("mother_id"), a.get("father_id")}
    parents_b = {b.get("mother_id"), b.get("father_id")}
    if (parents_a & parents_b) - {None}:
        return True
    if a["id"] in parents_b or b["id"] in parents_a:
        return True
    return False


def _pay_cost(pawn, action):
    cost = ACTION_COSTS[action]
    if "Night Owl" in pawn.get("traits", []) and not is_day():
        cost //= 2
    if pawn["vitals"]["energy"] < cost:
        return False
    pawn["vitals"]["energy"] = _clamp(pawn["vitals"]["energy"] - cost)
    return True


def _gain_skill(pawn, skill):
    pawn["skills"][skill] = _clamp(pawn["skills"][skill] + 1, 0, SKILL_MAX)


def _tradition():
    """The colony's current tradition tag, or None."""
    return state.world_state.setdefault("traditions", {}).get("tag")


def _traditions_inc(key, amount=1):
    """Accumulate a colony-wide historical counter (survives pawn deaths)."""
    traditions = state.world_state.setdefault(
        "traditions",
        {"tag": None, "predators_slain": 0, "trees_felled": 0, "rations_shared": 0},
    )
    traditions.setdefault(key, 0)
    traditions[key] += amount


def _shelter_damage(amount):
    """Children of the Forest: shelter degrades only half as fast."""
    if _tradition() == FORESTERS_TAG:
        return amount // 2
    return amount


def _inspire_bonus(pawn, amount):
    """Morale above 80 → +10% gather/craft yield (Inspiration)."""
    if pawn["vitals"]["morale"] > INSPIRED_MORALE:
        return amount + amount // 10
    return amount


INTERACT_WORDS = {
    "social": ("talk", "chat", "comfort", "gossip", "encourage", "teach", "groom",
               "dance", "sing", "laugh", "play", "greet", "joke", "discuss", "joke"),
    "relax": ("watch", "daydream", "sit", "nap", "bathe",
              "stargaze", "dream", "sunbathe"),
    "pray": ("pray", "worship", "revere", "venerate", "commune", "prayer",
             "oracle", "invoke", "meditat", "contemplate", "reflect"),
    "train": ("train", "practice", "spar", "exercise", "lift", "stretch", "drill"),
    "craft": ("carv", "craft", "mend", "repair", "weave", "whittle", "sew", "tend"),
    "recruit": ("invite", "recruit", "welcome", "hire", "persuade", "settle", "ask to stay", "stay"),
    "farm": ("till", "plant", "farm", "seed", "sow", "hoe", "plough", "plow", "cultivat", "harvest", "reap", "crop"),
    "gather": ("fish", "hunt", "gather", "pick", "collect", "dig", "search", "forage", "scavenge"),
    "heirloom": ("claim", "inherit", "bequeath", "receive"),
    "rite": ("bury", "mourn", "eulogiz", "grieve", "lament", "funeral", "wake", "honor", "remember"),
    "extinguish": ("extinguish", "quench", "douse"),
}

GOAL_MORALE = 15
GOAL_SKILLS = {
    ("gather", "wood"): "woodcutting",
    ("gather", "food"): "scouting",
    ("gather", "stone"): "scouting",
    ("gather", "fiber"): "scouting",
    ("build", None): "woodcutting",
}


def _goal_nudge(pawn, amount=1, **match):
    """Advance a pawn's personal goal when the tick's deeds match it."""
    goal = pawn.get("goal")
    if not goal or goal.get("progress", 0) >= goal.get("needed", 1):
        return
    for key, value in match.items():
        if goal.get(key) != value:
            return
    goal["progress"] = min(goal["needed"], goal["progress"] + amount)


def _complete_goal(pawn, pawn_id, goal, result):
    pawn["goal"] = None
    pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + GOAL_MORALE)
    skill = GOAL_SKILLS.get((goal.get("kind"), goal.get("resource")))
    if skill:
        _gain_skill(pawn, skill)
    result.append(
        events.add_event(
            "goal",
            actor=pawn_id,
            data={"goal": goal.get("text", "")},
            description=f"{pawn['name']} fulfills a personal goal: {goal.get('text', '')}!",
        )
    )


def _adopt_goal(pawn, text):
    """Parse an LLM goal wish into an engine-tracked goal. Ignored if unclear."""
    if pawn.get("goal"):
        return None
    t = (text or "").strip().lower().rstrip(".,!?")
    if not t:
        return None
    m = re.search(r"\d+", t)
    n = int(m.group(0)) if m else 5

    def make_goal(kind, **kw):
        return {"kind": kind, "needed": n, "progress": 0, "text": t, **kw}

    if any(w in t for w in ("survive", "endure", "grow old", " live")):
        return make_goal("survive", needed=n * TICKS_PER_DAY)
    if any(w in t for w in ("wood", "chop", "lumber", "firewood")):
        return make_goal("gather", resource="wood")
    if any(w in t for w in ("food", "forag", "berry", "fish", "meal", "provision")):
        return make_goal("gather", resource="food")
    if any(w in t for w in ("stone", "quarry")):
        return make_goal("gather", resource="stone")
    if any(w in t for w in ("fiber", "flax", "grass")):
        return make_goal("gather", resource="fiber")
    if any(w in t for w in ("build", "shelter", "craft", "campfire", "wall", "cabin")):
        return make_goal("build")
    if any(w in t for w in ("befriend", "friend", "bond", "comfort", "help")):
        return make_goal("social", target_id=_name_to_id(t))
    return None


def _title_role(pawn):
    return pawn.get("title_role")


def _adopt_title(pawn, text):
    """Bucket an LLM-invented title by keyword and attach subtle passive perks."""
    t = (text or "").strip().rstrip(".,!?")
    if not t or len(t) > TITLE_MAX_LEN or not re.match(r"^[A-Za-z0-9\- ]+$", t):
        return None
    lower = t.lower()
    role = None
    for kind, words in TITLE_WORDS.items():
        if any(w in lower for w in words):
            role = kind
            break
    pawn["custom_title"] = t
    pawn["title_role"] = role
    return {"title": t, "role": role}


def _title_defense(pawn):
    return TITLE_MARTIAL_DEFENSE if _title_role(pawn) == "martial" else 0


def _title_share_bonus(pawn):
    return TITLE_NURTURE_SHARE if _title_role(pawn) == "nurture" else 0


def _wild_predators():
    return [
        w
        for w in state.world_state["wildlife"]
        if WILDLIFE[w["species"]]["kind"] == "predator" and w["state"] != "tamed"
    ]


def _wild_prey():
    return [
        w
        for w in state.world_state["wildlife"]
        if WILDLIFE[w["species"]]["kind"] == "prey" and w["state"] != "tamed"
    ]


def _forest_count():
    """How many Forest tiles remain on the grid (windbreak coverage)."""
    return sum(
        1 for row in state.world_state["grid"] for t in row if t in FOREST_TILES
    )


def _overpopulated():
    """Herds count as overpopulated when wild prey exceed the normal cap."""
    return len(_wild_prey()) > WILDLIFE_MAX


def _clear_cut():
    """Windbreaks are gone when few Forest tiles remain."""
    return _forest_count() <= WINDBREAK_FOREST_MIN


def _graze_tick(result):
    """Overpopulated prey strip the wild forage and eat ripe farm plots."""
    prey = _wild_prey()
    if len(prey) <= WILDLIFE_MAX:
        return
    surplus = len(prey) - WILDLIFE_MAX
    biome = state.world_state["biome"]
    drained = min(biome["food_stock"], surplus * GRAZE_DRAIN)
    if drained > 0:
        biome["food_stock"] = _clamp(biome["food_stock"] - drained)
        result.append(
            events.add_event(
                "grazed",
                data={"food": drained},
                description=(
                    f"The overabundant herds strip the meadows of {drained} wild food."
                ),
            )
        )
    tiles = state.world_state.setdefault("tiles", {})
    for key, entry in list(tiles.items()):
        if entry.get("farm", 0) >= FARM_GROW_TICKS and random.random() < FARM_GRAZE_CHANCE:
            entry["farm"] = 0
            result.append(
                events.add_event(
                    "farm_eaten",
                    data={"tile": key},
                    description=(
                        f"A hungry herd breaks into the farm plot at ({key}) "
                        "and eats the crop before it can be gathered!"
                    ),
                )
            )


def _name_to_id(text):
    """Find a living active pawn whose name appears in the goal text."""
    for pid, pawn in state.world_state["pawns"].items():
        if pawn["status"] == "active" and pawn["name"].lower() in text:
            return pid
    return None


def _verb_phrase(name, verb):
    """Turn a free-form verb into a readable third-person sentence fragment."""
    verb = (verb or "").strip().lower().rstrip(".,!?")
    if not verb:
        return f"{name} idles quietly"
    if verb.endswith("ing"):
        return f"{name} spends the tick {verb}"
    if verb.endswith("e"):
        return f"{name} {verb.rstrip('e')}es"
    if verb.endswith(("s", "x", "z", "ch", "sh")):
        return f"{name} {verb}es"
    return f"{name} {verb}s"


def _tilemate(pawn, pawn_id):
    """Another active pawn sharing the same tile, or None."""
    for pid, other in state.world_state["pawns"].items():
        if pid != pawn_id and other["status"] == "active" and other["pos"] == pawn["pos"]:
            return other
    return None


def is_day():
    return (state.world_state["tick"] % DAY_CYCLE) < DAY_LENGTH


def _tile_at(x, y):
    grid = state.world_state["grid"]
    if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
        return grid[y][x]
    return None


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _ignite(x, y):
    """Set a Forest or Camp tile on fire. Returns True if it ignited."""
    grid = state.world_state["grid"]
    tile = grid[y][x]
    if tile == BURNING_TILE:
        return False
    if tile not in FOREST_TILES and tile != BUILD_TILE:
        return False
    if tile == BUILD_TILE:
        regrow_to = BUILD_TILE
    elif random.random() < 0.5:
        regrow_to = tile
    else:
        regrow_to = FIREBREAK_TILE
    grid[y][x] = BURNING_TILE
    state.world_state.setdefault("tiles", {})[f"{x},{y}"] = {
        "burn": FIRE_TICKS,
        "regrow_to": regrow_to,
    }
    return True


def _adjacent_to_fire(x, y):
    grid = state.world_state["grid"]
    for dx, dy in DIRS.values():
        nx, ny = x + dx, y + dy
        if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and grid[ny][nx] == BURNING_TILE:
            return True
    return False


def _nearest_burning_tile(x, y):
    """The nearest burning tile within Manhattan distance 1, or None."""
    grid = state.world_state["grid"]
    for dx, dy in ((0, 0), *DIRS.values()):
        nx, ny = x + dx, y + dy
        if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and grid[ny][nx] == BURNING_TILE:
            return (nx, ny)
    return None


def _is_flooded(x, y):
    biome = state.world_state["biome"]
    return biome.get("flood", 0) > 0 and [x, y] in biome.get("flooded", [])


def _trigger_flood():
    """Spring downpours swell the river; adjacent Meadow tiles flood for a few ticks."""
    grid = state.world_state["grid"]
    biome = state.world_state["biome"]
    flooded = []
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if grid[y][x] != RIVER_TILE:
                continue
            for dx, dy in DIRS.values():
                nx, ny = x + dx, y + dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and grid[ny][nx] == FIREBREAK_TILE:
                    if [nx, ny] not in flooded:
                        flooded.append([nx, ny])
                        grid[ny][nx] = RIVER_TILE
    biome["flood"] = FLOOD_TICKS
    biome["flooded"] = flooded
    return flooded


def _tick_miasma():
    """Toxic spores from the Ruins: -5 HP unless a Warm Coat covers the face."""
    result = []
    for pawn in state.world_state["pawns"].values():
        if pawn["status"] != "active" or _tile_at(*pawn["pos"]) != RUIN_TILE:
            continue
        if pawn["gear"]["body"] == "Warm Coat":
            continue
        pawn["vitals"]["hp"] = _clamp(pawn["vitals"]["hp"] - MIASMA_DAMAGE)
        desc = f"Toxic spores sting {pawn['name']} (-{MIASMA_DAMAGE} HP)!"
        if pawn["vitals"]["hp"] <= 0:
            pawn["vitals"]["hp"] = 0
            pawn["status"] = "incapacitated"
            desc += f" {pawn['name']} collapses!"
        result.append(
            events.add_event(
                "miasma_damage",
                actor=pawn["id"],
                data={"damage": MIASMA_DAMAGE},
                description=desc,
            )
        )
    return result


def _visitor_by_id(vid):
    return next(
        (v for v in state.world_state.get("visitors", []) if v["id"] == vid),
        None,
    )


def _on_edge(x, y):
    return x in (0, GRID_SIZE - 1) or y in (0, GRID_SIZE - 1)


def _walk_toward(pos, target):
    """One greedy Manhattan step toward target, preferring horizontal moves."""
    x, y = pos
    tx, ty = target
    if x < tx:
        x += 1
    elif x > tx:
        x -= 1
    elif y < ty:
        y += 1
    elif y > ty:
        y -= 1
    return [x, y]


def _spawn_visitor():
    """A wandering NPC steps onto the grid at a random edge tile."""
    edge = [
        [x, y]
        for y in range(GRID_SIZE)
        for x in range(GRID_SIZE)
        if _on_edge(x, y)
    ]
    pos = random.choice(edge)
    kind = random.choice(("Merchant", "Wanderer", "Bard"))
    visitor = state.make_visitor(kind, pos)
    visitor["hp"] = VISITOR_TYPES[kind]["hp"]
    visitor["inventory"] = dict(VISITOR_TYPES[kind]["stock"])
    state.world_state.setdefault("visitors", []).append(visitor)
    return visitor


def _step_visitors():
    """Visitor AI: walk to camp, linger 3-5 ticks, then walk off the grid."""
    result = []
    visitors = state.world_state.setdefault("visitors", [])
    for v in list(visitors):
        if v["state"] == "arriving":
            v["pos"] = _walk_toward(v["pos"], list(CAMP_POS))
            if v["pos"] == list(CAMP_POS):
                v["state"] = "visiting"
                v["ticks_left"] = random.randint(VISITOR_STAY_MIN, VISITOR_STAY_MAX)
                result.append(
                    events.add_event(
                        "visitor",
                        data={"id": v["id"], "action": "arrive", "kind": v["kind"]},
                        description=f"{v['name']}, the {v['kind']}, arrives at the campfire.",
                    )
                )
        elif v["state"] == "visiting":
            v["ticks_left"] -= 1
            if v["kind"] == "Bard":
                for pawn in state.world_state["pawns"].values():
                    if pawn["status"] == "active":
                        pawn["vitals"]["morale"] = _clamp(
                            pawn["vitals"]["morale"] + VISITOR_BARD_MORALE
                        )
                result.append(
                    events.add_event(
                        "visitor",
                        data={"id": v["id"], "action": "perform", "kind": v["kind"]},
                        description=f"{v['name']}, the Bard, plays a tune by the fire.",
                    )
                )
            if v["ticks_left"] <= 0:
                v["state"] = "leaving"
                result.append(
                    events.add_event(
                        "visitor",
                        data={"id": v["id"], "action": "depart", "kind": v["kind"]},
                        description=f"{v['name']}, the {v['kind']}, packs up and takes to the road.",
                    )
                )
        else:  # leaving
            if _on_edge(*v["pos"]):
                visitors.remove(v)
                result.append(
                    events.add_event(
                        "visitor",
                        data={"id": v["id"], "action": "left", "kind": v["kind"]},
                        description=f"{v['name']}, the {v['kind']}, wanders off the edge of the world.",
                    )
                )
                continue
            edge = [
                [x, y]
                for y in range(GRID_SIZE)
                for x in range(GRID_SIZE)
                if _on_edge(x, y)
            ]
            target = min(edge, key=lambda t: _manhattan(v["pos"], t))
            v["pos"] = _walk_toward(v["pos"], target)
            if _on_edge(*v["pos"]):
                visitors.remove(v)
                result.append(
                    events.add_event(
                        "visitor",
                        data={"id": v["id"], "action": "left", "kind": v["kind"]},
                        description=f"{v['name']}, the {v['kind']}, wanders off the edge of the world.",
                    )
                )
    return result


def _raider_by_id(rid):
    return next(
        (r for r in state.world_state.get("raiders", []) if r["id"] == rid),
        None,
    )


def _edge_tiles():
    return [
        [x, y]
        for y in range(GRID_SIZE)
        for x in range(GRID_SIZE)
        if _on_edge(x, y)
    ]


def _colony_wealth():
    """Food + wood currently held by the colony (stores plus rucksacks)."""
    biome = state.world_state["biome"]
    food = biome["food_stock"]
    wood = 0
    for p in state.world_state["pawns"].values():
        food += p["inventory"]["food"]
        wood += p["inventory"]["wood"]
    return food + wood


def _spawn_raid():
    """Autumn scavenger raid on a prosperous colony: 1-2 hostiles at the edge."""
    raiders = state.world_state.setdefault("raiders", [])
    out = []
    edge = _edge_tiles()
    for _ in range(random.randint(1, 2)):
        if len(raiders) >= RAID_MAX:
            break
        r = state.make_raider(random.choice(edge))
        raiders.append(r)
        out.append(
            events.add_event(
                "raid",
                data={"id": r["id"], "action": "arrive", "name": r["name"]},
                description=(
                    f"A {r['name']} appears at the edge of the world, "
                    f"eyeing the colony's stores!"
                ),
            )
        )
    return out


def _raid_steal(r, biome):
    """Steal from the granary stock first, then from pawn rucksacks."""
    amount = RAID_STEAL
    taken = 0
    take = min(amount, biome["food_stock"])
    biome["food_stock"] = _clamp(biome["food_stock"] - take)
    taken += take
    if taken < RAID_STEAL:
        for p in state.world_state["pawns"].values():
            avail = p["inventory"]["food"]
            take = min(RAID_STEAL - taken, avail)
            p["inventory"]["food"] -= take
            taken += take
            if taken >= RAID_STEAL:
                break
    return taken


def _raid_defense(r, result):
    """Tamed predators and high-combat pawns defend the stores at the camp."""
    damage = 0
    for w in state.world_state["wildlife"]:
        if w["state"] == "tamed" and WILDLIFE[w["species"]]["kind"] == "predator":
            damage += WILDLIFE[w["species"]]["bite_damage"]
    defenders = [
        p
        for p in state.world_state["pawns"].values()
        if p["status"] == "active" and p["pos"] == list(CAMP_POS)
    ]
    if defenders:
        best = max(defenders, key=lambda p: p["skills"]["combat"])
        damage += RAID_DEFEND_DAMAGE + best["skills"]["combat"] // 2
        if best["gear"]["main_hand"] == "Flint Spear":
            damage += SPEAR_DAMAGE
    if damage <= 0:
        return False
    r["hp"] -= damage
    if r["hp"] <= 0:
        state.world_state["raiders"].remove(r)
        result.append(
            events.add_event(
                "raid",
                data={"id": r["id"], "action": "repelled", "name": r["name"]},
                description=(
                    f"The {r['name']} is cut down at the camp "
                    f"by the colony's defenders!"
                ),
            )
        )
        return True
    r["state"] = "fleeing"
    result.append(
        events.add_event(
            "raid",
            data={"id": r["id"], "action": "repelled", "name": r["name"], "damage": damage},
            description=(
                f"The {r['name']} takes {damage} damage from the defenders "
                f"and turns to flee!"
            ),
        )
    )
    return True


def _step_raiders():
    """Raider AI: march to the camp, steal from the granary, then flee."""
    result = []
    raiders = state.world_state.setdefault("raiders", [])
    biome = state.world_state["biome"]
    for r in list(raiders):
        if r["state"] == "fleeing":
            if _on_edge(*r["pos"]):
                raiders.remove(r)
                result.append(
                    events.add_event(
                        "raid",
                        data={"id": r["id"], "action": "fled", "name": r["name"], "stolen": r["stolen"]},
                        description=(
                            f"The {r['name']} slips back into the wilds"
                            + (f" with {r['stolen']} food stolen" if r["stolen"] else "")
                            + "."
                        ),
                    )
                )
                continue
            target = min(_edge_tiles(), key=lambda t: _manhattan(r["pos"], t))
            r["pos"] = _walk_toward(r["pos"], target)
            if _on_edge(*r["pos"]):
                raiders.remove(r)
                result.append(
                    events.add_event(
                        "raid",
                        data={"id": r["id"], "action": "fled", "name": r["name"], "stolen": r["stolen"]},
                        description=(
                            f"The {r['name']} slips back into the wilds"
                            + (f" with {r['stolen']} food stolen" if r["stolen"] else "")
                            + "."
                        ),
                    )
                )
            continue
        if r["pos"] == list(CAMP_POS):
            if _raid_defense(r, result):
                continue
            stolen = _raid_steal(r, biome)
            r["stolen"] += stolen
            r["state"] = "fleeing"
            result.append(
                events.add_event(
                    "raid",
                    data={"id": r["id"], "action": "steal", "name": r["name"], "food": stolen},
                    description=(
                        f"The {r['name']} loots {stolen} food from the stores "
                        f"and makes off!"
                    ),
                )
            )
            continue
        if r["slowed"] > 0:
            r["slowed"] -= 1
            continue
        r["pos"] = _walk_toward(r["pos"], list(CAMP_POS))
        if biome.get("palisade", 0) >= 1:
            r["slowed"] = biome["palisade"]
    return result


def _clamp_modifier(v):
    """Clamp a balance multiplier within the strict Python-enforced bounds."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 1.0
    return max(MODIFIER_MIN, min(MODIFIER_MAX, v))


def _modifier(key):
    """Clamped balance multiplier from biome.modifiers (defensive vs bad saves)."""
    mods = state.world_state["biome"].get("modifiers") or {}
    return _clamp_modifier(mods.get(key, 1.0))


def _all_recipes():
    """Static + synthesized blueprints, normalised to {materials, slot, tier}."""
    out = {}
    for name, recipe in RECIPES.items():
        out[name] = {
            "materials": {res: cost for res, cost in recipe.items() if res != "slot"},
            "slot": recipe["slot"],
            "tier": TOOL_TIER[name],
        }
    for name, recipe in state.world_state.get("custom_recipes", {}).items():
        out[name] = {
            "materials": dict(recipe.get("materials", {})),
            "slot": recipe.get("slot", "main_hand"),
            "tier": int(recipe.get("tier", 1)),
        }
    return out


def _custom_tool_bonus(pawn, key):
    """Sum of a synthesized tool's bonus for key (combat/woodcutting/scouting/fiber)."""
    total = 0
    for item in (pawn["gear"]["main_hand"], pawn["gear"]["body"]):
        recipe = state.world_state.get("custom_recipes", {}).get(item)
        if recipe:
            total += recipe.get("bonus", {}).get(key, 0)
    return total


def _colony_resource(resource):
    """Total of a resource currently held in colonists' rucksacks."""
    return sum(
        p["inventory"].get(resource, 0)
        for p in state.world_state["pawns"].values()
        if p["status"] == "active"
    )


def _complete_quest(q, actor=None):
    """Pay a prophecy's reward (colony morale, optional title) and clear it."""
    quests = state.world_state.get("active_quests", [])
    if q in quests:
        quests.remove(q)
    morale = q.get("reward_morale", QUEST_REWARD_MORALE)
    for p in state.world_state["pawns"].values():
        if p["status"] == "active":
            p["vitals"]["morale"] = _clamp(p["vitals"]["morale"] + morale)
    title = q.get("reward_title")
    if title and actor:
        target = state.world_state["pawns"].get(actor)
        if target:
            target["title"] = title
    _carve_rune(
        f"Prophecy fulfilled: {q.get('title', 'the quest')}",
        f"The colony sees {q.get('title', 'the prophecy')} come to pass.",
    )
    return events.add_event(
        "quest_complete",
        actor=actor,
        data={"quest": q.get("id"), "title": q.get("title"), "reward_morale": morale},
        description=(
            f"The prophecy of {q.get('title', 'the quest')} comes to pass — "
            f"the colony is uplifted (+{morale} morale)."
        ),
    )


def _quest_progress(kind, actor=None, amount=1, **tags):
    """Advance matching quests; complete and emit any that reach their goal."""
    result = []
    for q in list(state.world_state.get("active_quests", [])):
        if q.get("kind") != kind:
            continue
        if kind == "hunt" and q.get("species") != tags.get("species"):
            continue
        q["progress"] = q.get("progress", 0) + amount
        if q["progress"] >= q.get("needed", 1):
            result.append(_complete_quest(q, actor))
    return result


def _check_quests():
    """Evaluate time/count-based prophecies each tick (survive, stockpile)."""
    result = []
    tick = state.world_state["tick"]
    for q in list(state.world_state.get("active_quests", [])):
        if q.get("kind") == "survive":
            created_day = q.get("created_tick", tick) // TICKS_PER_DAY
            q["progress"] = tick // TICKS_PER_DAY - created_day
        elif q.get("kind") == "stockpile":
            q["progress"] = _colony_resource(q.get("resource", "food"))
        if q["progress"] >= q.get("needed", 1):
            result.append(_complete_quest(q))
    return result


# Stage 9 Architect routine: annual balance review (LLM call lives in core).
PATCH_INTERVAL = 400           # one full year cycle (4 seasons x 100 ticks)
CUSTOM_RECIPE_LIMIT = 6        # max synthesized blueprints kept
CUSTOM_RECIPE_TIER_MAX = 10
RECIPE_BONUS_MAX = 5
RECIPE_RESOURCES = ("wood", "food", "stone", "fiber")
RECIPE_BONUS_KEYS = ("combat", "woodcutting", "scouting", "fiber")
QUEST_KINDS = ("hunt", "stockpile", "survive", "chop")
QUEST_NEEDED_MAX = 100

# Stage 14 (Phase 3) annual camp council & colony mandates.
COUNCIL_INTERVAL = PATCH_INTERVAL  # every year, alongside the Architect review
MANDATE_MAX_LEN = 120
COUNCIL_LEADER_MORALE = 5  # the recognized leader starts the year inspired

# Stage 15 (Phase 4) trophic cascades — predator pressure & windbreak ecology.
WILDLIFE_OVERPOP_MAX = 5      # prey may exceed the cap when no predator hunts them
PREY_SPAWN_OVERHUNT = 0.55    # prey spawn chance when no wild predator remains
GRAZE_DRAIN = 2               # each surplus prey eats wild forage (food_stock) per tick
FARM_GRAZE_CHANCE = 0.2       # per ripe plot per tick, an overabundant herd may eat it
WINDBREAK_FOREST_MIN = 6      # forest tiles at or below this = clear-cut (windbreaks gone)
WINDBREAK_COLD_PENALTY = 2    # extra Winter cold when the windbreak is gone
WINDBREAK_FLOOD_BONUS = 0.15  # extra Spring flood chance when the windbreak is gone


def apply_council(leader_pid, mandate):
    """The annual council names a leader and issues a one-sentence Colony Mandate.

    Returns the council record, or None if the leader is unknown/down or the
    mandate is empty or over-long (the previous council then stands).
    """
    mandate = (mandate or "").strip().rstrip(".,!?")
    if not mandate or len(mandate) > MANDATE_MAX_LEN:
        return None
    leader = state.world_state["pawns"].get(leader_pid)
    if leader is None or leader["status"] != "active":
        return None
    leader["vitals"]["morale"] = _clamp(leader["vitals"]["morale"] + COUNCIL_LEADER_MORALE)
    _add_moodlet(leader, "Chosen", 5, COUNCIL_INTERVAL)
    state.world_state["council"] = {
        "leader_id": leader_pid,
        "leader_name": leader["name"],
        "mandate": mandate,
        "day": state.world_state["tick"] // TICKS_PER_DAY,
        "tick": state.world_state["tick"],
    }
    events.add_event(
        "council",
        actor=leader_pid,
        data={"mandate": mandate},
        description=(
            f"🏛️ The council names {leader['name']} as leader for the year "
            f"with a Colony Mandate: “{mandate}”."
        ),
    )
    return state.world_state["council"]


def bump_patch_version():
    """'v1.0' -> 'v1.1' ... -> 'v1.9' -> 'v2.0'. Sets and returns the new version."""
    current = state.world_state.get("patch_version", "v1.0")
    try:
        core = current.lstrip("vV")
        parts = core.split(".") if "." in core else (core, "0")
        major, minor = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        major, minor = 1, 0
    minor += 1
    if minor > 9:
        major += 1
        minor = 0
    state.world_state["patch_version"] = f"v{major}.{minor}"
    return state.world_state["patch_version"]


def apply_patch(deltas):
    """Apply strictly-clamped balance deltas to biome.modifiers.

    Net multipliers are clamped within [MODIFIER_MIN, MODIFIER_MAX] regardless
    of what the LLM proposed. Returns (old, new) clamped modifier dicts.
    """
    mods = state.world_state["biome"].setdefault("modifiers", {})
    keys = ("regrowth", "cold", "spawn")
    old = {k: _clamp_modifier(mods.get(k, 1.0)) for k in keys}
    for key in keys:
        try:
            delta = float(deltas.get(key, 0.0))
        except (TypeError, ValueError, AttributeError):
            delta = 0.0
        mods[key] = _clamp_modifier(old[key] + delta)
    new = {k: _clamp_modifier(mods.get(k, 1.0)) for k in keys}
    return old, new


def validate_new_recipe(raw):
    """Coerce an LLM-synthesized blueprint into a safe recipe dict, or None."""
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip().title()[:40]
    if not name or not all(c.isalnum() or c.isspace() for c in name):
        return None
    materials = {}
    for res, cost in (raw.get("materials") or {}).items():
        if res not in RECIPE_RESOURCES:
            continue
        try:
            cost = max(1, int(float(cost)))
        except (TypeError, ValueError):
            cost = 1
        materials[res] = min(cost, 20)
    if not materials:
        return None
    slot = raw.get("slot", "main_hand")
    if slot not in ("main_hand", "body"):
        slot = "main_hand"
    try:
        tier = int(float(raw.get("tier", CUSTOM_RECIPE_TIER_MIN)))
    except (TypeError, ValueError):
        tier = CUSTOM_RECIPE_TIER_MIN
    tier = max(CUSTOM_RECIPE_TIER_MIN, min(tier, CUSTOM_RECIPE_TIER_MAX))
    bonus = {}
    for key, val in (raw.get("bonus") or {}).items():
        if key not in RECIPE_BONUS_KEYS:
            continue
        try:
            val = max(0, int(float(val)))
        except (TypeError, ValueError):
            val = 0
        bonus[key] = min(val, RECIPE_BONUS_MAX)
    return {"name": name, "materials": materials, "slot": slot, "tier": tier, "bonus": bonus}


def validate_new_quest(raw):
    """Coerce an LLM world-prophecy into a safe quest dict, or None."""
    if not isinstance(raw, dict):
        return None
    kind = raw.get("kind")
    if kind not in QUEST_KINDS:
        return None
    title = str(raw.get("title", "")).strip()[:80]
    if not title:
        title = "The Unwritten Prophecy"
    quests = state.world_state.get("active_quests", [])
    if any(q.get("title", "").strip().lower() == title.lower() for q in quests):
        return None
    try:
        needed = max(1, int(float(raw.get("needed", 1))))
    except (TypeError, ValueError):
        needed = 1
    needed = min(needed, QUEST_NEEDED_MAX)
    try:
        morale = int(float(raw.get("reward_morale", QUEST_REWARD_MORALE)))
    except (TypeError, ValueError):
        morale = QUEST_REWARD_MORALE
    morale = max(0, min(morale, QUEST_MORALE_CAP))
    quest = {
        "id": f"quest_{state.world_state['tick']}_{len(quests) + 1}",
        "title": title,
        "text": str(raw.get("text", "")).strip()[:300],
        "kind": kind,
        "needed": needed,
        "progress": 0,
        "reward_morale": morale,
        "reward_title": str(raw.get("reward_title") or "").strip()[:40] or None,
        "created_tick": state.world_state["tick"],
    }
    if kind == "hunt":
        species = raw.get("species")
        if species not in WILDLIFE:
            return None
        quest["species"] = species
    elif kind == "stockpile":
        resource = raw.get("resource", "food")
        if resource not in RECIPE_RESOURCES:
            return None
        quest["resource"] = resource
    return quest


def _tick_fires():
    """Burn down each active fire, damage occupants, and regrow scorched earth."""
    result = []
    biome = state.world_state["biome"]
    grid = state.world_state["grid"]
    tiles = state.world_state.setdefault("tiles", {})
    for key, entry in list(tiles.items()):
        x, y = (int(p) for p in key.split(","))
        if "burn" in entry:
            if entry["regrow_to"] == BUILD_TILE:
                biome["campfire"] = _clamp(biome["campfire"] - CAMP_BURN_CAMPFIRE)
                biome["shelter"] = _clamp(biome["shelter"] - _shelter_damage(CAMP_BURN_SHELTER))
            else:
                biome["wood_stock"] = _clamp(biome["wood_stock"] - FIRE_WOOD_DRAIN)
            for pawn in state.world_state["pawns"].values():
                if pawn["status"] == "active" and pawn["pos"] == [x, y]:
                    pawn["vitals"]["hp"] = _clamp(pawn["vitals"]["hp"] - FIRE_DAMAGE)
                    desc = f"{pawn['name']} is caught in the flames (-{FIRE_DAMAGE} HP)!"
                    if pawn["vitals"]["hp"] <= 0:
                        pawn["vitals"]["hp"] = 0
                        pawn["status"] = "incapacitated"
                        desc += f" {pawn['name']} collapses!"
                    result.append(
                        events.add_event(
                            "fire_damage",
                            actor=pawn["id"],
                            data={"damage": FIRE_DAMAGE},
                            description=desc,
                        )
                    )
            entry["burn"] -= 1
            if entry["burn"] <= 0:
                if entry["regrow_to"] == BUILD_TILE:
                    grid[y][x] = BUILD_TILE
                    del tiles[key]
                else:
                    grid[y][x] = ASH_TILE
                    entry.pop("burn", None)
                    entry["regrow_in"] = REGROW_TICKS
                    result.append(
                        events.add_event(
                            "fire_out",
                            data={"pos": [x, y]},
                            description=f"The fire at ({x},{y}) burns out, leaving scorched earth.",
                        )
                    )
        elif "regrow_in" in entry:
            entry["regrow_in"] -= 1
            if entry["regrow_in"] <= 0:
                grid[y][x] = entry["regrow_to"]
                del tiles[key]
                result.append(
                    events.add_event(
                        "regrowth",
                        data={"pos": [x, y], "tile": grid[y][x]},
                        description=f"Scorched earth at ({x},{y}) regrows as {grid[y][x]}.",
                    )
                )
    return result


def _grow_farms():
    """Farm plots ripen over FARM_GROW_TICKS, but only in Spring/Summer."""
    result = []
    growing = state.world_state["biome"]["season"] in FARM_GROW_SEASONS
    tiles = state.world_state.setdefault("tiles", {})
    for key, entry in list(tiles.items()):
        if "farm" not in entry:
            continue
        if growing and entry["farm"] < FARM_GROW_TICKS:
            entry["farm"] += 1
            if entry["farm"] == FARM_GROW_TICKS:
                result.append(
                    events.add_event(
                        "farm_ready",
                        data={"pos": [int(p) for p in key.split(",")]},
                        description=f"The farm plot at ({key}) is ripe for harvest.",
                    )
                )
    return result


def _spread_fire():
    """Burning tiles may ignite adjacent Forest or Camp tiles."""
    result = []
    grid = state.world_state["grid"]
    tiles = state.world_state.setdefault("tiles", {})
    for key, entry in list(tiles.items()):
        if "burn" not in entry:
            continue
        x, y = (int(p) for p in key.split(","))
        for dx, dy in DIRS.values():
            nx, ny = x + dx, y + dy
            if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
                continue
            cell = grid[ny][nx]
            if cell in FOREST_TILES:
                chance = FIRE_SPREAD_CHANCE
            elif cell == BUILD_TILE:
                chance = FIRE_CAMP_SPREAD_CHANCE
            else:
                continue
            if random.random() < chance and _ignite(nx, ny):
                result.append(
                    events.add_event(
                        "fire_spread",
                        data={"pos": [nx, ny]},
                        description=f"The fire spreads to ({nx},{ny})!",
                    )
                )
    return result


def render_grid():
    """ASCII/emoji codeblock view of the 5x5 map with pawns and wildlife on it."""
    grid = state.world_state["grid"]
    occupants = {}
    for pawn in state.world_state["pawns"].values():
        if pawn["status"] != "active":
            continue
        x, y = pawn["pos"]
        occupants.setdefault((x, y), {"pawns": 0, "animals": []})
        occupants[(x, y)]["pawns"] += 1
    for w in state.world_state["wildlife"]:
        x, y = w["pos"]
        occupants.setdefault((x, y), {"pawns": 0, "animals": []})
        occupants[(x, y)]["animals"].append(WILDLIFE[w["species"]]["emoji"])
    for v in state.world_state.get("visitors", []):
        x, y = v["pos"]
        occupants.setdefault((x, y), {"pawns": 0, "animals": []})
        occupants[(x, y)]["animals"].append(VISITOR_TYPES[v["kind"]]["emoji"])
    for r in state.world_state.get("raiders", []):
        x, y = r["pos"]
        occupants.setdefault((x, y), {"pawns": 0, "animals": []})
        occupants[(x, y)]["animals"].append(RAIDER_EMOJI)
    lines = []
    for y in range(len(grid)):
        cells = []
        for x in range(len(grid[y])):
            occ = occupants.get((x, y))
            if not occ:
                cells.append(f"[{grid[y][x]}]")
            else:
                p_count = occ["pawns"]
                animals = occ["animals"]
                symbols = []
                if p_count > 1:
                    symbols.append("👥")
                elif p_count == 1:
                    symbols.append("🧙")
                symbols.extend(animals)
                cells.append("[" + "".join(symbols) + "]")
        lines.append("".join(cells))
    return "\n".join(lines)


def _pawn_by_id(pid):
    """Living pawn or graveyard tombstone by id, else None."""
    pawn = state.world_state["pawns"].get(pid)
    if pawn:
        return pawn
    for g in state.world_state["graveyard"]:
        if g["id"] == pid:
            return g
    return None


def find_pawn_ref(s):
    """Match a living pawn or graveyard tombstone by `pawn_N` id or display name.

    Returns (pawn_or_tombstone, None) on success or (None, error_message).
    """
    p = _pawn_by_id(s)
    if p:
        return p, None
    hits = [
        e
        for e in list(state.world_state["pawns"].values())
        + list(state.world_state["graveyard"])
        if e["name"].lower() == s.lower()
    ]
    if len(hits) == 1:
        return hits[0], None
    if len(hits) > 1:
        return None, f"several pawns share the name **{s}**; target one by id instead"
    return None, f"no pawn or fallen ancestor named `{s}`"


def lineage_label(pawn):
    """'child of Mother & Father' for pawns with known parents, else ''."""
    parents = []
    for key in ("mother_id", "father_id"):
        p = _pawn_by_id(pawn.get(key))
        if p:
            parents.append(p["name"])
    if not parents:
        return ""
    return "child of " + " & ".join(parents)


def render_family_tree():
    """Emoji view of the colony's couples, kinship, and rivalries."""
    living = state.world_state["pawns"]
    ids = list(living.keys())

    def name_of(pid):
        p = _pawn_by_id(pid)
        if not p:
            return "?"
        return f"{p['name']} 🪦" if pid not in living else p["name"]

    couples, bonded, rivals = [], [], []
    for i, aid in enumerate(ids):
        for bid in ids[i + 1 :]:
            a, b = living[aid], living[bid]
            mutual = min(a["relationships"].get(bid, 0), b["relationships"].get(aid, 0))
            partners = aid in b.get("partners", []) and bid in a.get("partners", [])
            shares_kids = any(
                {p.get("mother_id"), p.get("father_id")} == {aid, bid}
                for p in living.values()
            )
            if partners or shares_kids:
                couples.append((aid, bid))
            elif mutual >= MATE_RELATIONSHIP:
                bonded.append((aid, bid))
            elif mutual <= RIVAL_THRESHOLD:
                rivals.append((aid, bid))

    lines = ["🌳 **Family & Bonds**"]
    if couples:
        for aid, bid in couples:
            a, b = living[aid], living[bid]
            kids = [
                name_of(kid)
                for kid, p in living.items()
                if {p.get("mother_id"), p.get("father_id")} == {aid, bid}
            ]
            kids_txt = f" — kids: {', '.join(kids)}" if kids else ""
            lines.append(f"💞 **{a['name']}** ⇄ **{b['name']}**{kids_txt}")
    if bonded:
        lines.append("\n🤝 **Bonded:**")
        for aid, bid in bonded:
            lines.append(f"- **{living[aid]['name']}** ⇄ **{living[bid]['name']}**")
    kin = [
        (p, lineage_label(p))
        for p in living.values()
        if lineage_label(p)
    ]
    if kin:
        lines.append("\n👪 **Kin:**")
        for p, label in sorted(kin, key=lambda t: t[0]["born_tick"]):
            lines.append(f"- {p['name']}: {label}")
    if rivals:
        lines.append("\n💢 **Rivals:**")
        for aid, bid in rivals:
            lines.append(f"- **{living[aid]['name']}** ⇄ **{living[bid]['name']}**")
    if not couples and not bonded and not kin and not rivals:
        lines.append("No bonds or lineage yet — a lonely terrarium.")
    return "\n".join(lines)


def render_dynasty():
    """Compact generational roll-up: 'Gen 1: Lumberjack 🪦, Scout; Gen 2: Willow'.

    Living pawns and graveyard tombstones are grouped by generation so the
    prompt always knows which generation carries the colony (ancestors
    permanently referenced, never forgotten).
    """
    living = state.world_state["pawns"]
    gens = {}
    for pid, p in living.items():
        gens.setdefault(p.get("generation", 1), []).append(f"{p['name']}")
    for g in state.world_state["graveyard"]:
        gens.setdefault(g.get("generation", 1), []).append(f"{g['name']} 🪦")
    if not gens:
        return ""
    return "Dynasty: " + "; ".join(
        f"Gen {g}: {', '.join(sorted(names))}" for g, names in sorted(gens.items())
    )


def _do_rest(pawn, pawn_id):
    heal = RECOVER_HEAL - (ELDER_REST_PENALTY if is_elder(pawn) else 0)
    pawn["vitals"]["hp"] = _clamp(pawn["vitals"]["hp"] + heal)
    pawn["vitals"]["energy"] = _clamp(pawn["vitals"]["energy"] + 20)
    return events.add_event(
        "rest", actor=pawn_id, description=f"{pawn['name']} rests and recovers."
    )


def _do_move(pawn, pawn_id, direction):
    if not direction or direction not in DIRS:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "need_direction"},
            description=f"{pawn['name']} hesitates, unsure which way to go.",
        )
    if not _pay_cost(pawn, "Move"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to move.",
        )
    dx, dy = DIRS[direction]
    x, y = pawn["pos"]
    nx, ny = x + dx, y + dy
    if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "off_grid", "direction": direction},
            description=f"{pawn['name']} finds the edge of the world and stops.",
        )
    pawn["pos"] = [nx, ny]
    return events.add_event(
        "move",
        actor=pawn_id,
        data={"direction": direction, "pos": pawn["pos"]},
        description=f"{pawn['name']} moves {direction} to ({nx},{ny}).",
    )


def _do_chop(pawn, pawn_id):
    if not _pay_cost(pawn, "Chop"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to chop.",
        )
    if _tile_at(*pawn["pos"]) not in FOREST_TILES:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "wrong_tile"},
            description=f"{pawn['name']} is not in the forest and finds nothing to cut.",
        )
    biome = state.world_state["biome"]
    if biome["wood_stock"] <= 0:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "forest_depleted"},
            description=f"{pawn['name']} finds the forest bare.",
        )
    wood = 3 + pawn["skills"]["woodcutting"] // 3 + random.choice([0, 1])
    if pawn["gear"]["main_hand"] == "Stone Axe":
        wood *= 2
    wood += _custom_tool_bonus(pawn, "woodcutting")
    if _tradition() == FORESTERS_TAG:
        wood += FORESTERS_CHOP_BONUS
    wood = _inspire_bonus(pawn, wood)
    wood = min(biome["wood_stock"], wood)
    biome["wood_stock"] -= wood
    pawn["inventory"]["wood"] += wood
    _goal_nudge(pawn, wood, resource="wood")
    pawn["counters"]["trees_felled"] += 1
    _traditions_inc("trees_felled", 1)
    _gain_skill(pawn, "woodcutting")
    _quest_progress("chop", actor=pawn_id)
    if _adjacent_to_fire(*pawn["pos"]):
        x, y = pawn["pos"]
        state.world_state["grid"][y][x] = FIREBREAK_TILE
        return events.add_event(
            "chop",
            actor=pawn_id,
            data={"wood": wood, "firebreak": True},
            description=f"{pawn['name']} chops a firebreak, gathering {wood} wood.",
        )
    return events.add_event(
        "chop",
        actor=pawn_id,
        data={"wood": wood},
        description=f"{pawn['name']} chops wood, gathering {wood}.",
    )


def _ruin_discovery(pawn, pawn_id):
    """A scout at the Sunken Tribe's ruins uncovers lore, a blueprint, or a warning.

    Returns the discovery event, or None if nothing new remains to be found.
    """
    lore = state.world_state.setdefault("lore", [])
    kind = random.choice(("lore", "blueprint", "warning"))
    if kind == "blueprint":
        fresh = [
            name
            for name in RUIN_BLUEPRINTS
            if name not in state.world_state.setdefault("custom_recipes", {})
        ]
        if fresh:
            name = random.choice(fresh)
            state.world_state["custom_recipes"][name] = dict(RUIN_BLUEPRINTS[name])
            return events.add_event(
                "discovery",
                actor=pawn_id,
                data={"kind": "blueprint", "item": name},
                description=f"{pawn['name']} unearths an ancient blueprint among the ruins: **{name}**.",
            )
        kind = "lore"
    if kind == "lore":
        text = random.choice(LORE_FRAGMENTS)
        lore.append({"tick": state.world_state["tick"], "text": text})
        del lore[:-state.MAX_LORE]
        return events.add_event(
            "discovery",
            actor=pawn_id,
            data={"kind": "lore", "text": text},
            description=(
                f"{pawn['name']} unearths a fragment of forgotten history: {text}"
            ),
        )
    text = random.choice(RUIN_WARNINGS)
    lore.append({"tick": state.world_state["tick"], "text": text})
    del lore[:-state.MAX_LORE]
    for _ in range(RUIN_WARNING_XP):
        _gain_skill(pawn, "scouting")
    for p in state.world_state["pawns"].values():
        if p["status"] == "active":
            p["vitals"]["morale"] = _clamp(p["vitals"]["morale"] + RUIN_WARNING_MORALE)
    return events.add_event(
        "discovery",
        actor=pawn_id,
        data={"kind": "warning", "text": text},
        description=(
            f"{pawn['name']} reads a carved warning among the ruins: {text} "
            f"the colony heeds it (+{RUIN_WARNING_MORALE} morale)."
        ),
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
    if _tile_at(*pawn["pos"]) == QUARRY_TILE:
        _gain_skill(pawn, "scouting")
        stone = 1 + skill // 5 + random.choice([0, 1])
        pawn["inventory"]["stone"] += stone
        _goal_nudge(pawn, stone, resource="stone")
        return events.add_event(
            "scout",
            actor=pawn_id,
            data={"stone": stone, "tile": "quarry"},
            description=f"{pawn['name']} quarries stone at the dig site ({stone}).",
        )
    if _tile_at(*pawn["pos"]) == RUIN_TILE:
        _gain_skill(pawn, "scouting")
        if random.random() < 0.2:
            pawn["vitals"]["hp"] = _clamp(pawn["vitals"]["hp"] - 3)
            return events.add_event(
                "scout",
                actor=pawn_id,
                data={"food": 0, "tile": "ruins", "damage": 3},
                description=f"{pawn['name']} disturbs something in the ruins and takes 3 damage.",
            )
        if random.random() < RUIN_DISCOVERY_CHANCE:
            discovery = _ruin_discovery(pawn, pawn_id)
            if discovery:
                return discovery
        food = 4 + skill // 3 + random.choice([0, 1])
        pawn["inventory"]["food"] += food
        _goal_nudge(pawn, food, resource="food")
        return events.add_event(
            "scout",
            actor=pawn_id,
            data={"food": food, "tile": "ruins"},
            description=f"{pawn['name']} scavenges the ruins and finds {food} food.",
        )
    if random.random() < min(0.85, 0.4 + skill * 0.04):
        food = 2 + skill // 4 + random.choice([0, 1])
        pawn["inventory"]["food"] += food
        _goal_nudge(pawn, food, resource="food")
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


def _do_forage(pawn, pawn_id):
    if not _pay_cost(pawn, "Forage"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to forage.",
        )
    if _tile_at(*pawn["pos"]) not in FORAGE_TILES:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "wrong_tile"},
            description=f"{pawn['name']} finds nothing edible here.",
        )
    if _is_flooded(*pawn["pos"]):
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "flooded"},
            description=f"{pawn['name']} wades through floodwater and finds nothing to forage.",
        )
    biome = state.world_state["biome"]
    if biome["food_stock"] <= 0:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "food_depleted"},
            description=f"{pawn['name']} finds the undergrowth picked bare.",
        )
    skill = pawn["skills"]["scouting"]
    food = 2 + skill // 4 + random.choice([0, 1])
    food += _custom_tool_bonus(pawn, "scouting")
    if "Pacifist" in pawn.get("traits", []):
        food += 2
    food = _inspire_bonus(pawn, food)
    food = min(biome["food_stock"], food)
    biome["food_stock"] -= food
    pawn["inventory"]["food"] += food
    _goal_nudge(pawn, food, resource="food")
    fiber_gain = 0
    if _tile_at(*pawn["pos"]) == "🫐" and random.random() < 0.35:
        fiber_gain = 1 + _custom_tool_bonus(pawn, "fiber")
        pawn["inventory"]["fiber"] += fiber_gain
        _goal_nudge(pawn, 1, resource="fiber")
    _gain_skill(pawn, "scouting")
    desc = f"{pawn['name']} forages, finding {food} food."
    if fiber_gain:
        desc += f" Also gathers {fiber_gain} fiber."
    return events.add_event(
        "forage",
        actor=pawn_id,
        data={"food": food, "fiber": fiber_gain},
        description=desc,
    )


def _try_craft(pawn, pawn_id):
    """Auto-craft the highest-tier affordable tool (static or synthesized) not yet owned."""
    inv = pawn["inventory"]
    gear = pawn["gear"]
    candidates = []
    for name, recipe in _all_recipes().items():
        slot = recipe["slot"]
        if gear[slot] is not None:
            continue
        if all(
            inv.get(res, 0) >= cost
            for res, cost in recipe["materials"].items()
        ):
            candidates.append((name, recipe["tier"]))
    if not candidates:
        return None
    best, _ = max(candidates, key=lambda c: c[1])
    recipe = _all_recipes()[best]
    for res, cost in recipe["materials"].items():
        inv[res] -= cost
    gear[recipe["slot"]] = best
    return best


def _do_build(pawn, pawn_id):
    if not _pay_cost(pawn, "Build"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to build.",
        )
    if _tile_at(*pawn["pos"]) != BUILD_TILE:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "wrong_tile"},
            description=f"{pawn['name']} can only build at the camp.",
        )
    crafted = _try_craft(pawn, pawn_id)
    if crafted:
        _gain_skill(pawn, "woodcutting")
        _goal_nudge(pawn, 1, kind="build")
        return events.add_event(
            "craft",
            actor=pawn_id,
            data={"item": crafted},
            description=f"{pawn['name']} crafts a {crafted}.",
        )
    biome = state.world_state["biome"]
    if biome["shelter"] < 100:
        if pawn["inventory"]["wood"] < BUILD_WOOD_COST:
            return events.add_event(
                "failed",
                actor=pawn_id,
                data={"reason": "need_wood"},
                description=f"{pawn['name']} doesn't have enough wood to build.",
            )
        pawn["inventory"]["wood"] -= BUILD_WOOD_COST
        biome["shelter"] = _clamp(biome["shelter"] + BUILD_GAIN)
        _gain_skill(pawn, "woodcutting")
        _goal_nudge(pawn, 1, kind="build")
        return events.add_event(
            "build",
            actor=pawn_id,
            data={"structure": "shelter", "level": biome["shelter"]},
            description=f"{pawn['name']} reinforces the shelter.",
        )
    if biome["campfire"] < 100:
        if pawn["inventory"]["wood"] < BUILD_WOOD_COST:
            return events.add_event(
                "failed",
                actor=pawn_id,
                data={"reason": "need_wood"},
                description=f"{pawn['name']} doesn't have enough wood to build.",
            )
        pawn["inventory"]["wood"] -= BUILD_WOOD_COST
        biome["campfire"] = _clamp(biome["campfire"] + BUILD_GAIN)
        _gain_skill(pawn, "woodcutting")
        _goal_nudge(pawn, 1, kind="build")
        return events.add_event(
            "build",
            actor=pawn_id,
            data={"structure": "campfire", "level": biome["campfire"]},
            description=f"{pawn['name']} rebuilds the campfire.",
        )
    if not biome.get("granary"):
        if pawn["inventory"]["wood"] < 5:
            return events.add_event(
                "failed",
                actor=pawn_id,
                data={"reason": "need_wood"},
                description=f"{pawn['name']} doesn't have enough wood to build the granary.",
            )
        pawn["inventory"]["wood"] -= 5
        biome["granary"] = True
        _gain_skill(pawn, "woodcutting")
        _goal_nudge(pawn, 1, kind="build")
        return events.add_event(
            "build",
            actor=pawn_id,
            data={"structure": "granary"},
            description=f"{pawn['name']} builds a granary to store food.",
        )
    if biome.get("palisade", 0) < PALISADE_MAX:
        if pawn["inventory"]["wood"] < 5:
            return events.add_event(
                "failed",
                actor=pawn_id,
                data={"reason": "need_wood"},
                description=f"{pawn['name']} doesn't have enough wood for the palisade.",
            )
        pawn["inventory"]["wood"] -= 5
        biome["palisade"] = biome.get("palisade", 0) + 1
        _gain_skill(pawn, "woodcutting")
        _goal_nudge(pawn, 1, kind="build")
        return events.add_event(
            "build",
            actor=pawn_id,
            data={"structure": "palisade", "level": biome["palisade"]},
            description=f"{pawn['name']} fortifies the palisade (level {biome['palisade']}).",
        )
    # The camp is fully fortified (shelter/fire/granary/palisade all done):
    # Build now raises the Ancestral Monolith, 5 wood + 5 stone per action.
    monument = state.world_state.setdefault(
        "monument", {"wood": 0, "stone": 0, "done": False, "inscription": None}
    )
    if not monument["done"]:
        if (
            pawn["inventory"]["wood"] < MONUMENT_WOOD_PER_BUILD
            or pawn["inventory"]["stone"] < MONUMENT_STONE_PER_BUILD
        ):
            return events.add_event(
                "failed",
                actor=pawn_id,
                data={"reason": "need_resources"},
                description=(
                    f"{pawn['name']} lacks the wood and stone for the Ancestral Monolith."
                ),
            )
        pawn["inventory"]["wood"] -= MONUMENT_WOOD_PER_BUILD
        pawn["inventory"]["stone"] -= MONUMENT_STONE_PER_BUILD
        monument["wood"] = min(MONUMENT_WOOD_NEEDED, monument["wood"] + MONUMENT_WOOD_PER_BUILD)
        monument["stone"] = min(
            MONUMENT_STONE_NEEDED, monument["stone"] + MONUMENT_STONE_PER_BUILD
        )
        _gain_skill(pawn, "woodcutting")
        _goal_nudge(pawn, 1, kind="build")
        if (
            monument["wood"] >= MONUMENT_WOOD_NEEDED
            and monument["stone"] >= MONUMENT_STONE_NEEDED
        ):
            monument["done"] = True
            state.pending_monument = True
            _carve_rune(
                "The Monolith Rises",
                "The colony raised the Ancestral Monolith with wood and stone and blood.",
            )
            return events.add_event(
                "monument_complete",
                actor=pawn_id,
                description=(
                    f"The Ancestral Monolith stands complete — "
                    f"{pawn['name']} carves the final runes!"
                ),
            )
        return events.add_event(
            "build",
            actor=pawn_id,
            data={"structure": "monument", "wood": monument["wood"], "stone": monument["stone"]},
            description=(
                f"{pawn['name']} raises the Ancestral Monolith "
                f"({monument['wood']}/{MONUMENT_WOOD_NEEDED} wood, "
                f"{monument['stone']}/{MONUMENT_STONE_NEEDED} stone)."
            ),
        )
    if pawn["inventory"]["wood"] < BUILD_WOOD_COST:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "need_wood"},
            description=f"{pawn['name']} doesn't have enough wood to build.",
        )
    pawn["inventory"]["wood"] -= BUILD_WOOD_COST
    biome["campfire"] = _clamp(biome["campfire"] + BUILD_GAIN)
    _gain_skill(pawn, "woodcutting")
    _goal_nudge(pawn, 1, kind="build")
    return events.add_event(
        "build",
        actor=pawn_id,
        data={"structure": "campfire", "level": biome["campfire"]},
        description=f"{pawn['name']} rebuilds the campfire.",
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
    if target.startswith("wild_"):
        animal = next((w for w in state.world_state["wildlife"] if w["id"] == target), None)
        if animal is None:
            return events.add_event(
                "failed",
                actor=pawn_id,
                target=target,
                data={"reason": "unknown_target"},
                description=f"{pawn['name']} looks for a beast that isn't there.",
            )
        if _manhattan(pawn["pos"], animal["pos"]) > 1:
            return events.add_event(
                "failed",
                actor=pawn_id,
                target=target,
                data={"reason": "too_far"},
                description=f"{pawn['name']} is too far from the {animal['species']} to strike.",
            )
        if "Pacifist" in pawn.get("traits", []):
            return events.add_event(
                "failed",
                actor=pawn_id,
                target=target,
                data={"reason": "pacifist"},
                description=f"{pawn['name']} is a pacifist and refuses to hunt.",
            )
        if not _pay_cost(pawn, "Attack"):
            return events.add_event(
                "failed",
                actor=pawn_id,
                target=target,
                data={"reason": "low_energy"},
                description=f"{pawn['name']} is too exhausted to attack.",
            )
        spec = WILDLIFE[animal["species"]]
        damage = max(
            1,
            5
            + pawn["skills"]["combat"] // 2
            + (SPEAR_DAMAGE if pawn["gear"]["main_hand"] == "Flint Spear" else 0)
            + _custom_tool_bonus(pawn, "combat")
            + (3 if "Brawler" in pawn.get("traits", []) and pawn["gear"]["main_hand"] is None else 0),
        )
        animal["hp"] -= damage
        pawn["counters"]["damage_dealt"] += damage
        if _tradition() == HUNTERS_TAG:
            for _ in range(HUNTERS_COMBAT_XP):
                _gain_skill(pawn, "combat")
        else:
            _gain_skill(pawn, "combat")
        if animal["hp"] <= 0:
            state.world_state["wildlife"].remove(animal)
            if spec["kind"] == "predator":
                before = state.world_state["traditions"].get("predators_slain", 0)
                _traditions_inc("predators_slain", 1)
                if before == 0:
                    _carve_rune(
                        "The First Predator Falls",
                        f"{pawn['name']} slew the first great predator to threaten the colony.",
                    )
            pawn["inventory"]["food"] += spec["food_yield"]
            pawn["inventory"]["fiber"] += spec["fiber_yield"]
            _goal_nudge(pawn, spec["food_yield"], resource="food")
            _quest_progress("hunt", actor=pawn_id, species=animal["species"])
            return events.add_event(
                "hunt",
                actor=pawn_id,
                target=target,
                data={"species": animal["species"], "food": spec["food_yield"], "fiber": spec["fiber_yield"]},
                description=f"{pawn['name']} hunts and slays the {animal['species']}, gathering {spec['food_yield']} food and {spec['fiber_yield']} fiber.",
            )
        else:
            desc = f"{pawn['name']} attacks the {animal['species']} for {damage} damage."
            if spec["kind"] == "prey":
                x, y = animal["pos"]
                best_pos, max_d = animal["pos"], _manhattan(animal["pos"], pawn["pos"])
                for dx, dy in DIRS.values():
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                        d = _manhattan([nx, ny], pawn["pos"])
                        if d > max_d:
                            max_d = d
                            best_pos = [nx, ny]
                animal["pos"] = best_pos
                desc += f" The {animal['species']} flees!"
            else:
                bite = spec["bite_damage"]
                pawn["vitals"]["hp"] = _clamp(pawn["vitals"]["hp"] - bite)
                desc += f" The {animal['species']} retaliates, biting for {bite} damage!"
                if pawn["vitals"]["hp"] <= 0:
                    pawn["vitals"]["hp"] = 0
                    pawn["status"] = "incapacitated"
                    desc += f" {pawn['name']} collapses!"
            return events.add_event(
                "attack",
                actor=pawn_id,
                target=target,
                data={"damage": damage, "species": animal["species"], "bite": spec["kind"] == "predator"},
                description=desc,
            )

    raider = _raider_by_id(target)
    if raider is not None:
        if _manhattan(pawn["pos"], raider["pos"]) > 1:
            return events.add_event(
                "failed",
                actor=pawn_id,
                target=target,
                data={"reason": "too_far"},
                description=f"{pawn['name']} is too far from the {raider['name']} to strike.",
            )
        if not _pay_cost(pawn, "Attack"):
            return events.add_event(
                "failed",
                actor=pawn_id,
                target=target,
                data={"reason": "low_energy"},
                description=f"{pawn['name']} is too exhausted to fight the {raider['name']}.",
            )
        damage = max(
            1,
            5
            + pawn["skills"]["combat"] // 2
            + (SPEAR_DAMAGE if pawn["gear"]["main_hand"] == "Flint Spear" else 0)
            + _custom_tool_bonus(pawn, "combat")
            + (3 if "Brawler" in pawn.get("traits", []) and pawn["gear"]["main_hand"] is None else 0),
        )
        raider["hp"] -= damage
        pawn["counters"]["damage_dealt"] += damage
        _gain_skill(pawn, "combat")
        if raider["hp"] <= 0:
            state.world_state["raiders"].remove(raider)
            return events.add_event(
                "raid",
                actor=pawn_id,
                target=target,
                data={"id": target, "action": "slain", "name": raider["name"], "damage": damage},
                description=f"{pawn['name']} cuts down the {raider['name']} with {damage} damage!",
            )
        raider["state"] = "fleeing"
        return events.add_event(
            "attack",
            actor=pawn_id,
            target=target,
            data={"damage": damage, "raider": raider["name"]},
            description=(
                f"{pawn['name']} wounds the {raider['name']} for {damage} damage "
                f"— it turns and flees!"
            ),
        )

    tvis = _visitor_by_id(target)
    if tvis is not None:
        return _attack_visitor(pawn, pawn_id, tvis)

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
    if _manhattan(pawn["pos"], tpawn["pos"]) > 1:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "too_far"},
            description=f"{pawn['name']} is too far from {tpawn['name']} to strike.",
        )
    if "Pacifist" in pawn.get("traits", []):
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "pacifist"},
            description=f"{pawn['name']} is a pacifist and refuses to fight.",
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
        5
        + pawn["skills"]["combat"] // 2
        - tpawn["skills"]["combat"] // 4
        + (SPEAR_DAMAGE if pawn["gear"]["main_hand"] == "Flint Spear" else 0)
        + _custom_tool_bonus(pawn, "combat")
        + (3 if "Brawler" in pawn.get("traits", []) and pawn["gear"]["main_hand"] is None else 0),
    )
    damage = max(1, damage - _title_defense(tpawn))
    tpawn["vitals"]["hp"] = _clamp(tpawn["vitals"]["hp"] - damage)
    pawn["counters"]["attacks_won"] += 1
    pawn["counters"]["damage_dealt"] += damage
    if tpawn["relationships"].get(pawn_id, 0) >= BETRAY_RELATIONSHIP:
        _grant_rel_badge(tpawn, pawn_id, "Betrayer")
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


def _attack_visitor(pawn, pawn_id, visitor):
    """Attack a visitor: plunder their goods; gentle pawns feel Guilt."""
    if _manhattan(pawn["pos"], visitor["pos"]) > 1:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=visitor["id"],
            data={"reason": "too_far"},
            description=f"{pawn['name']} is too far from {visitor['name']} to strike.",
        )
    if "Pacifist" in pawn.get("traits", []):
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=visitor["id"],
            data={"reason": "pacifist"},
            description=f"{pawn['name']} is a pacifist and refuses to fight.",
        )
    if not _pay_cost(pawn, "Attack"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=visitor["id"],
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to attack.",
        )
    damage = max(
        1,
        5
        + pawn["skills"]["combat"] // 2
        + (SPEAR_DAMAGE if pawn["gear"]["main_hand"] == "Flint Spear" else 0)
        + _custom_tool_bonus(pawn, "combat")
        + (3 if "Brawler" in pawn.get("traits", []) and pawn["gear"]["main_hand"] is None else 0),
    )
    visitor["hp"] -= damage
    pawn["counters"]["damage_dealt"] += damage
    _gain_skill(pawn, "combat")
    gentle = pawn["personality"].get("aggression", 5) < AGGRESSION_GUILT_THRESHOLD
    if gentle:
        _add_moodlet(pawn, "Guilt", GUILT_MOODLET_DELTA, GUILT_MOODLET_TICKS)
    desc = f"{pawn['name']} attacks {visitor['name']}, the {visitor['kind']}, for {damage} damage."
    if visitor["hp"] <= 0:
        plunder = []
        for res in ("stone", "fiber", "food"):
            if visitor["inventory"].get(res, 0) > 0:
                pawn["inventory"][res] += visitor["inventory"][res]
                plunder.append(f"{visitor['inventory'][res]} {res}")
                visitor["inventory"][res] = 0
        state.world_state.get("visitors", []).remove(visitor)
        if plunder:
            desc += f" {pawn['name']} plunders {', '.join(plunder)}."
        if gentle:
            desc += " A shadow of guilt falls over them."
        return events.add_event(
            "attack",
            actor=pawn_id,
            target=visitor["id"],
            data={"damage": damage, "plunder": plunder, "guilt": gentle},
            description=desc,
        )
    visitor["state"] = "leaving"
    if gentle:
        desc += " A shadow of guilt falls over them."
    return events.add_event(
        "attack",
        actor=pawn_id,
        target=visitor["id"],
        data={"damage": damage, "guilt": gentle},
        description=desc,
    )


def _recruit_visitor(visitor, recruiter_id):
    """Turn a visiting traveler into a permanent colonist, respecting MAX_PAWNS."""
    if len(state.world_state["pawns"]) >= MAX_PAWNS:
        return None
    pawn_id = state.next_pawn_id()
    pawn = state.make_pawn(
        pawn_id,
        visitor["name"],
        hp=visitor["hp"],
        energy=60,
        personality=dict(state.DEFAULT_PERSONALITY),
    )
    pawn["job"] = "Wanderer"
    pawn["pos"] = list(visitor["pos"])
    state.world_state["pawns"][pawn_id] = pawn
    state.world_state.get("visitors", []).remove(visitor)
    recruiter = state.world_state["pawns"].get(recruiter_id)
    if recruiter:
        _adjust_relationship(pawn, recruiter_id, 20)
        _adjust_relationship(recruiter, pawn_id, 20)
    return pawn


def _court_visitor(pawn, pawn_id, visitor):
    """Mate targeting a visitor is a courtship — a sociable pawn may recruit them."""
    if visitor["state"] != "visiting" or _manhattan(pawn["pos"], visitor["pos"]) > 0:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=visitor["id"],
            data={"reason": "not_same_tile"},
            description=f"{pawn['name']} wants to court {visitor['name']}, but they are apart.",
        )
    if len(state.world_state["pawns"]) >= MAX_PAWNS:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=visitor["id"],
            data={"reason": "colony_full"},
            description=f"{visitor['name']} would stay, but the colony is already at capacity.",
        )
    if not _pay_cost(pawn, "Mate"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=visitor["id"],
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to court.",
        )
    chance = _clamp(
        RECRUIT_BASE_CHANCE + pawn["personality"]["sociability"] * RECRUIT_SOCIABILITY_FACTOR,
        0.1,
        0.95,
    )
    if random.random() < chance:
        recruit = _recruit_visitor(visitor, pawn_id)
        if recruit is None:
            return events.add_event(
                "failed",
                actor=pawn_id,
                target=visitor["id"],
                data={"reason": "colony_full"},
                description=f"{visitor['name']} would stay, but the colony is already at capacity.",
            )
        return events.add_event(
            "recruit",
            actor=pawn_id,
            target=visitor["id"],
            data={"name": recruit["name"]},
            description=(
                f"{pawn['name']} courts {visitor['name']}, who decides to stay and join the colony!"
            ),
        )
    return events.add_event(
        "failed",
        actor=pawn_id,
        target=visitor["id"],
        data={"reason": "declined"},
        description=f"{visitor['name']} kindly declines {pawn['name']}'s invitation.",
    )


def _do_share(pawn, pawn_id, target):
    if not target:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "no_target"},
            description=f"{pawn['name']} reaches out to share with no one.",
        )
    if target == pawn_id:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "self_target"},
            description=f"{pawn['name']} tries to share with themself.",
        )
    tpawn = state.world_state["pawns"].get(target)
    if tpawn is None:
        tvis = _visitor_by_id(target)
        if tvis is not None:
            return _share_with_visitor(pawn, pawn_id, tvis)
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
            description=f"{pawn['name']} cannot reach {tpawn['name']}.",
        )
    if _manhattan(pawn["pos"], tpawn["pos"]) > 1:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "too_far"},
            description=f"{pawn['name']} is too far from {tpawn['name']} to share.",
        )
    given = SHARE_FOOD + _title_share_bonus(pawn)
    if pawn["inventory"]["food"] < given:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "need_food"},
            description=f"{pawn['name']} has nothing to share.",
        )
    if not _pay_cost(pawn, "Share"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to share.",
        )
    pawn["inventory"]["food"] -= given
    tpawn["inventory"]["food"] += given
    pawn["counters"]["rations_shared"] += 1
    _traditions_inc("rations_shared", 1)
    _goal_nudge(pawn, 1, kind="social", target_id=target)
    _adjust_relationship(pawn, target, 25)
    _adjust_relationship(tpawn, pawn_id, 25)
    pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + 5)
    tpawn["vitals"]["morale"] = _clamp(tpawn["vitals"]["morale"] + 5)
    _grant_rel_badge(tpawn, pawn_id, "Indebted")
    if tpawn.get("starving_ticks", 0) > 0:
        _grant_rel_badge(tpawn, pawn_id, "Lifesaver")
    return events.add_event(
        "share",
        actor=pawn_id,
        target=target,
        data={"food": given},
        description=f"{pawn['name']} shares food with {tpawn['name']}.",
    )


def _share_with_visitor(pawn, pawn_id, visitor):
    """Share food to a visitor: the Merchant barters stone; others trade a keepsake."""
    if visitor["state"] != "visiting" or _manhattan(pawn["pos"], visitor["pos"]) > 1:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=visitor["id"],
            data={"reason": "too_far"},
            description=f"{pawn['name']} cannot reach {visitor['name']}, the {visitor['kind']}.",
        )
    if pawn["inventory"]["food"] < BARTER_FOOD_COST:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=visitor["id"],
            data={"reason": "need_food"},
            description=f"{pawn['name']} has nothing to trade.",
        )
    if not _pay_cost(pawn, "Share"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=visitor["id"],
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to trade.",
        )
    pawn["inventory"]["food"] -= BARTER_FOOD_COST
    pawn["counters"]["rations_shared"] += BARTER_FOOD_COST
    _traditions_inc("rations_shared", BARTER_FOOD_COST)
    pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + 5)
    gains = []
    if visitor["kind"] == "Merchant":
        stone = min(BARTER_STONE_GAIN, visitor["inventory"].get("stone", 0))
        visitor["inventory"]["stone"] -= stone
        pawn["inventory"]["stone"] += stone
        gains.append(f"{stone} stone")
    elif visitor["kind"] == "Wanderer":
        fiber = min(2, visitor["inventory"].get("fiber", 0))
        visitor["inventory"]["fiber"] -= fiber
        pawn["inventory"]["fiber"] += fiber
        gains.append(f"{fiber} fiber")
    gain_txt = ", ".join(gains) if gains else "a grateful smile"
    return events.add_event(
        "barter",
        actor=pawn_id,
        target=visitor["id"],
        data={"food": BARTER_FOOD_COST, "gains": gains, "kind": visitor["kind"]},
        description=(
            f"{pawn['name']} shares {BARTER_FOOD_COST} food with {visitor['name']}, "
            f"the {visitor['kind']}, and receives {gain_txt} in return."
        ),
    )


def _do_pray(pawn, pawn_id):
    """Pray at the completed monolith: divine inspiration and, in the cold, a weather blessing.

    Returns None when prayer has no oracle to answer (monolith unfinished or the
    pawn is not at Camp), letting _do_interact fall back to a quiet meditation.
    """
    monument = state.world_state.setdefault(
        "monument", {"wood": 0, "stone": 0, "done": False, "inscription": None}
    )
    if not monument.get("done"):
        return None
    if _tile_at(*pawn["pos"]) != BUILD_TILE:
        return None
    effects = []
    pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + MONUMENT_PRAY_MORALE)
    effects.append(f"+{MONUMENT_PRAY_MORALE} morale (divine inspiration)")
    weakest = min(pawn["skills"], key=pawn["skills"].get)
    for _ in range(MONUMENT_PRAY_XP):
        _gain_skill(pawn, weakest)
    effects.append(f"+{MONUMENT_PRAY_XP} {weakest} XP")
    biome = state.world_state["biome"]
    cold = SEASON_COLD[biome["season"]] + (0 if is_day() else 3) + WEATHER_COLD[biome["weather"]]
    if cold > 0:
        _add_moodlet(
            pawn,
            "Divine Warmth",
            MONUMENT_WARMTH_MOODLET_DELTA,
            MONUMENT_WARMTH_BLESSING_TICKS,
        )
        effects.append("a vision warns of the cold — Divine Warmth shields you")
    return events.add_event(
        "pray",
        actor=pawn_id,
        data={"effects": effects},
        description=f"{pawn['name']} prays at the monolith. ({', '.join(effects)})",
    )


def _do_interact(pawn, pawn_id, flavor):
    """Free-form Interact: engine buckets any verb into safe, context effects."""
    if not _pay_cost(pawn, "Interact"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted for {flavor or 'anything'}.",
        )
    verb = (flavor or "").strip().lower().rstrip(".,!?")
    effects = []
    desc = _verb_phrase(pawn["name"], verb)
    if _in_words(verb, INTERACT_WORDS["social"]):
        social_morale = KINDRED_SOCIAL_MORALE if _tradition() == KINDRED_TAG else 5
        pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + social_morale)
        effects.append(f"+{social_morale} morale")
        partner = _tilemate(pawn, pawn_id)
        if partner:
            _adjust_relationship(pawn, partner["id"], 10)
            _adjust_relationship(partner, pawn_id, 10)
            _goal_nudge(pawn, 1, kind="social", target_id=partner["id"])
            if "teach" in verb:
                _grant_rel_badge(pawn, partner["id"], "Mentor")
            effects.append(f"closer to {partner['name']}")
    elif _in_words(verb, INTERACT_WORDS["farm"]):
        tile = _tile_at(*pawn["pos"])
        key = f"{pawn['pos'][0]},{pawn['pos'][1]}"
        entry = state.world_state.setdefault("tiles", {}).get(key)
        if tile == FARM_TILE and entry and "farm" in entry:
            if entry["farm"] >= FARM_GROW_TICKS:
                pawn["inventory"]["food"] += FARM_HARVEST_FOOD
                pawn["inventory"]["fiber"] += FARM_HARVEST_FIBER
                entry["farm"] = 0
                _goal_nudge(pawn, FARM_HARVEST_FOOD, resource="food")
                _goal_nudge(pawn, FARM_HARVEST_FIBER, resource="fiber")
                _gain_skill(pawn, "scouting")
                return events.add_event(
                    "harvest",
                    actor=pawn_id,
                    data={"food": FARM_HARVEST_FOOD, "fiber": FARM_HARVEST_FIBER},
                    description=(
                        f"{pawn['name']} harvests the farm plot "
                        f"(+{FARM_HARVEST_FOOD} food, +{FARM_HARVEST_FIBER} fiber)."
                    ),
                )
            effects.append(f"the farm plot is still growing ({entry['farm']}/{FARM_GROW_TICKS})")
        elif tile == "🫐":
            state.world_state["grid"][pawn["pos"][1]][pawn["pos"][0]] = FARM_TILE
            state.world_state.setdefault("tiles", {})[key] = {"farm": 0}
            _gain_skill(pawn, "scouting")
            effects.append("tills a farm plot 🌾")
        else:
            effects.append("no soil to farm here")
    elif _in_words(verb, INTERACT_WORDS["gather"]):
        tile = _tile_at(*pawn["pos"])
        if tile in FORAGE_TILES:
            yield_ = 1 + pawn["skills"]["scouting"] // 6 + random.choice([0, 1])
            if "Pacifist" in pawn.get("traits", []):
                yield_ += 2
            stock = state.world_state["biome"]["food_stock"]
            yield_ = min(stock, yield_)
            state.world_state["biome"]["food_stock"] -= yield_
            pawn["inventory"]["food"] += yield_
            _goal_nudge(pawn, yield_, resource="food")
            if tile == "🫐" and random.random() < 0.3:
                pawn["inventory"]["fiber"] += 1
                _goal_nudge(pawn, 1, resource="fiber")
                effects.append(f"+{yield_} food, +1 fiber")
            else:
                effects.append(f"+{yield_} food")
        elif tile in FOREST_TILES:
            yield_ = 1 + random.choice([0, 1])
            stock = state.world_state["biome"]["wood_stock"]
            yield_ = min(stock, yield_)
            state.world_state["biome"]["wood_stock"] -= yield_
            pawn["inventory"]["wood"] += yield_
            _goal_nudge(pawn, yield_, resource="wood")
            effects.append(f"+{yield_} wood")
        elif tile in (RUIN_TILE, QUARRY_TILE):
            yield_ = 1 + random.choice([0, 1])
            pawn["inventory"]["stone"] += yield_
            _goal_nudge(pawn, yield_, resource="stone")
            effects.append(f"+{yield_} stone")
        else:
            effects.append("finds little here")
        _gain_skill(pawn, "scouting")
    elif _in_words(verb, INTERACT_WORDS["craft"]):
        if _tile_at(*pawn["pos"]) == BUILD_TILE and state.world_state["biome"]["shelter"] < 100:
            state.world_state["biome"]["shelter"] = _clamp(
                state.world_state["biome"]["shelter"] + 3
            )
            _goal_nudge(pawn, 1, kind="build")
            effects.append("+3 shelter")
        else:
            pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + 5)
            effects.append("+5 morale")
        _gain_skill(pawn, "woodcutting")
    elif _in_words(verb, INTERACT_WORDS["train"]):
        _gain_skill(pawn, "combat")
        effects.append("+1 combat XP")
    elif _in_words(verb, INTERACT_WORDS["pray"]):
        prayed = _do_pray(pawn, pawn_id)
        if prayed is not None:
            return prayed
        pawn["vitals"]["energy"] = _clamp(pawn["vitals"]["energy"] + 10)
        pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + 3)
        effects.append("+10 energy, +3 morale (a quiet meditation)")
    elif _in_words(verb, INTERACT_WORDS["relax"]):
        pawn["vitals"]["energy"] = _clamp(pawn["vitals"]["energy"] + 10)
        pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + 3)
        effects.append("+10 energy, +3 morale")
    elif "tame" in verb or "feed" in verb:
        animal = next((w for w in state.world_state["wildlife"] if w["pos"] == pawn["pos"] and w["state"] == "wandering"), None)
        if animal and animal["state"] == "wandering":
            chance = _clamp(0.5 + pawn["skills"]["scouting"] * 0.02, 0.1, 0.95)
            if random.random() < chance:
                animal["state"] = "tamed"
                animal["tamed_by"] = pawn_id
                animal["pos"] = list(CAMP_POS)
                pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + 5)
                effects.append(f"tamed {animal['species']}")
                return events.add_event(
                    "tame",
                    actor=pawn_id,
                    data={"species": animal["species"]},
                    description=f"{pawn['name']} successfully tames the {animal['species']} as a camp pet!",
                )
            else:
                effects.append("taming attempt failed")
        else:
            effects.append("no wild animal here to tame")
    elif _in_words(verb, INTERACT_WORDS["recruit"]):
        visitor = next(
            (v for v in state.world_state.get("visitors", []) if v["pos"] == pawn["pos"]),
            None,
        )
        if visitor is None:
            effects.append("no traveler here to invite")
        elif len(state.world_state["pawns"]) >= MAX_PAWNS:
            effects.append("the colony is already full")
        else:
            chance = _clamp(
                RECRUIT_BASE_CHANCE + pawn["personality"]["sociability"] * RECRUIT_SOCIABILITY_FACTOR,
                0.1,
                0.95,
            )
            if random.random() < chance:
                recruit = _recruit_visitor(visitor, pawn_id)
                effects.append(f"recruits {recruit['name']}")
                return events.add_event(
                    "recruit",
                    actor=pawn_id,
                    target=visitor["id"],
                    data={"name": recruit["name"]},
                    description=(
                        f"{pawn['name']} invites {recruit['name']} to stay — "
                        f"and {recruit['name']} joins the colony!"
                    ),
                )
            effects.append(f"{visitor['name']} politely declines")
    elif _in_words(verb, INTERACT_WORDS["rite"]):
        return _do_funerary_rite(pawn, pawn_id, verb)
    elif _in_words(verb, INTERACT_WORDS["heirloom"]):
        claimed = _claim_heirloom(pawn, pawn_id, verb)
        if claimed:
            effects.append(f"claims {claimed['name']} (+{claimed.get('moodlet_delta', 5)} morale)")
        else:
            effects.append("no heirloom to claim")
    elif _in_words(verb, INTERACT_WORDS["extinguish"]):
        near = _nearest_burning_tile(*pawn["pos"])
        if near:
            key = f"{near[0]},{near[1]}"
            entry = state.world_state.setdefault("tiles", {})[key]
            state.world_state["grid"][near[1]][near[0]] = ASH_TILE
            entry.pop("burn", None)
            entry["regrow_in"] = REGROW_TICKS
            effects.append(f"extinguishes the fire at ({near[0]},{near[1]})")
        else:
            effects.append("no fire nearby to extinguish")
    else:
        pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + 3)
        effects.append("+3 morale")
    return events.add_event(
        "interact",
        actor=pawn_id,
        data={"flavor": flavor or "", "effects": effects},
        description=f"{desc}. ({', '.join(effects)})",
    )


def _in_words(verb, words):
    return any(w in verb for w in words)


def _claim_heirloom(pawn, pawn_id, verb):
    """Claim an unclaimed heirloom: grant its skill bonus and a proud moodlet."""
    heirlooms = state.world_state["heirlooms"]
    unclaimed = [h for h in heirlooms if not h.get("owner")]
    if not unclaimed:
        return None
    target = unclaimed[0]
    for h in unclaimed:
        if h["name"].lower() in verb:
            target = h
            break
    target["owner"] = pawn_id
    for skill, bonus in (target.get("stat_bonus") or {}).items():
        pawn["skills"][skill] = _clamp(pawn["skills"][skill] + bonus, 0, SKILL_MAX)
    _add_moodlet(pawn, "Proud", target.get("moodlet_delta", HEIRLOOM_MOODLET_DELTA), HEIRLOOM_MOODLET_TICKS)
    return target


def _do_funerary_rite(pawn, pawn_id, verb):
    """Hold a rite for a beloved fallen pawn: halve Grief for same-tile survivors."""
    tile = _tile_at(*pawn["pos"])
    if tile not in RITE_TILES:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "wrong_tile"},
            description=f"{pawn['name']} must hold the rite at the Camp or the Ruins.",
        )
    beloved = next(
        (g for g in reversed(state.world_state["graveyard"]) if g.get("beloved")),
        None,
    )
    if beloved is None:
        pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + 3)
        return events.add_event(
            "interact",
            actor=pawn_id,
            data={"flavor": verb, "effects": ["+3 morale"]},
            description=(
                f"{pawn['name']} {_verb_phrase(pawn['name'], verb)} — "
                f"but no one beloved is remembered."
            ),
        )
    halved = 0
    for other in state.world_state["pawns"].values():
        if other["status"] != "active" or other["pos"] != pawn["pos"]:
            continue
        for m in other.get("moodlets", []):
            if m["name"] == "Grief" and m["ticks_left"] > 0:
                m["ticks_left"] = max(1, m["ticks_left"] // 2)
                halved += 1
    return events.add_event(
        "rite",
        actor=pawn_id,
        data={"verb": verb, "beloved": beloved["name"], "grief_halved": halved},
        description=(
            f"{pawn['name']} holds a {verb} rite for {beloved['name']} — "
            f"grief eases for those who mourn."
        ),
    )


def _do_mate(pawn, pawn_id, target):
    if not target:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "no_target"},
            description=f"{pawn['name']} looks for a partner and finds none.",
        )
    if target == pawn_id:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "self_target"},
            description=f"{pawn['name']} courts themself — nothing happens.",
        )
    tpawn = state.world_state["pawns"].get(target)
    if tpawn is None:
        tvis = _visitor_by_id(target)
        if tvis is not None:
            return _court_visitor(pawn, pawn_id, tvis)
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "unknown_target"},
            description=f"{pawn['name']} seeks a partner that isn't there.",
        )
    if tpawn["status"] != "active":
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "target_down"},
            description=f"{pawn['name']} finds {tpawn['name']} unavailable.",
        )
    if _manhattan(pawn["pos"], tpawn["pos"]) > 0:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "not_same_tile"},
            description=f"{pawn['name']} wants to court {tpawn['name']}, but they are apart.",
        )
    if pawn.get("child_ticks", 0) > 0 or tpawn.get("child_ticks", 0) > 0:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "too_young"},
            description=f"{pawn['name']} and {tpawn['name']} are too young to court.",
        )
    if pawn["sex"] == tpawn["sex"]:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "same_sex"},
            description=f"{pawn['name']} and {tpawn['name']} share a moment as friends.",
        )
    if _are_kin(pawn, tpawn):
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "too_close_kin"},
            description=f"{pawn['name']} and {tpawn['name']} are too closely related.",
        )
    partners = target in pawn.get("partners", []) and pawn_id in tpawn.get("partners", [])
    if not partners and (
        pawn["relationships"].get(target, 0) < MATE_RELATIONSHIP
        or tpawn["relationships"].get(pawn_id, 0) < MATE_RELATIONSHIP
    ):
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "relationship_too_low"},
            description=f"{pawn['name']} courts {tpawn['name']}, who isn't ready.",
        )
    if len(state.world_state["pawns"]) >= MAX_PAWNS:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "population_cap"},
            description="The colony is large enough — no new life is welcomed.",
        )
    female = pawn if pawn["sex"] == "F" else tpawn
    if female.get("starving_ticks", 0) > 0:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "mother_starving"},
            description=f"{female['name']} is too famished to conceive.",
        )
    if female.get("pregnant_ticks", 0) > 0:
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "already_pregnant"},
            description=f"{female['name']} is already with child.",
        )
    if not _pay_cost(pawn, "Mate"):
        return events.add_event(
            "failed",
            actor=pawn_id,
            target=target,
            data={"reason": "low_energy"},
            description=f"{pawn['name']} is too exhausted to court.",
        )
    _adjust_relationship(pawn, target, 10)
    _adjust_relationship(tpawn, pawn_id, 10)
    if target not in pawn.get("partners", []):
        pawn["partners"].append(target)
    if pawn_id not in tpawn.get("partners", []):
        tpawn["partners"].append(pawn_id)
    if random.random() < CONCEPTION_CHANCE:
        female["pregnant_ticks"] = PREGNANCY_TICKS
        female["partner_id"] = pawn_id
        return events.add_event(
            "mate",
            actor=pawn_id,
            target=target,
            data={"conceived": True},
            description=f"{pawn['name']} and {tpawn['name']} become partners — "
            f"{female['name']} is expecting!",
        )
    return events.add_event(
        "mate",
        actor=pawn_id,
        target=target,
        data={"conceived": False},
        description=f"{pawn['name']} and {tpawn['name']} become partners.",
    )


def _give_birth(mother, mother_id, result):
    if len(state.world_state["pawns"]) >= MAX_PAWNS:
        mother["pregnant_ticks"] = PREGNANCY_TICKS
        result.append(
            events.add_event(
                "birth",
                actor=mother_id,
                data={"delivered": False},
                description=f"{mother['name']} is due, but the colony is full — the birth is delayed.",
            )
        )
        return
    child_id = state.next_pawn_id()
    used = {p["name"].lower() for p in state.world_state["pawns"].values()}
    name = next(
        (n for n in state.NAME_POOL if n.lower() not in used),
        f"Child_{len(state.world_state['pawns']) + 1}",
    )
    father = _pawn_by_id(mother.get("partner_id"))
    traits = _inherit_traits(mother, father) if father else _inherit_traits(mother, mother)
    child = state.make_pawn(
        child_id,
        name,
        hp=NEWBORN_HP,
        energy=NEWBORN_ENERGY,
        job=random.choice(state.JOB_POOL),
        traits=traits,
        generation=max(
            mother.get("generation", 1),
            (father or {}).get("generation", 1),
        )
        + 1,
    )
    child["pos"] = list(mother["pos"])
    child["child_ticks"] = CHILD_MATURITY
    child["mother_id"] = mother_id
    child["father_id"] = mother.get("partner_id")
    first_second_gen = child.get("generation", 1) >= 2 and not any(
        e.get("generation", 1) >= 2
        for e in list(state.world_state["pawns"].values())
        + list(state.world_state["graveyard"])
    )
    mother["partner_id"] = None
    state.world_state["pawns"][child_id] = child
    _inherit_feuds(child, mother, father)
    if first_second_gen:
        _carve_rune(
            "The Second Generation Rises",
            f"{name} is the first child of a new generation to inherit the colony.",
        )
    result.append(
        events.add_event(
            "birth",
            actor=mother_id,
            data={"child": child_id, "name": name, "sex": child["sex"]},
            description=f"{mother['name']} gives birth to {name} ({child['sex']})! "
            "The colony grows.",
        )
    )


def _feed_campfire():
    biome = state.world_state["biome"]
    if biome["campfire"] <= 0:
        return False
    for pawn_id, pawn in state.world_state["pawns"].items():
        if pawn["inventory"]["wood"] >= CAMPFIRE_FUEL:
            pawn["inventory"]["wood"] -= CAMPFIRE_FUEL
            biome["campfire"] = _clamp(biome["campfire"] + CAMPFIRE_FEED_GAIN)
            return True
    biome["campfire"] = _clamp(biome["campfire"] - CAMPFIRE_DECAY)
    return biome["campfire"] > 0


def _metabolize(pawn, pawn_id, biome, lit, day, result):
    v = pawn["vitals"]
    before_hunger = v["hunger"]
    hunger_drain = 1 if "Iron Stomach" in pawn.get("traits", []) else HUNGER_DRAIN
    v["hunger"] = _clamp(v["hunger"] - hunger_drain)
    if v["hunger"] <= EAT_THRESHOLD and pawn["inventory"]["food"] >= 1:
        pawn["inventory"]["food"] -= 1
        v["hunger"] = _clamp(v["hunger"] + EAT_REPLENISH)
        v["morale"] = _clamp(v["morale"] + 3)
        result.append(
            events.add_event(
                "eat", actor=pawn_id, description=f"{pawn['name']} eats a ration."
            )
        )
    if v["hunger"] <= 0:
        v["hunger"] = 0
        v["hp"] = _clamp(v["hp"] - STARVE_HP)
        v["energy"] = _clamp(v["energy"] - STARVE_ENERGY)
        v["morale"] = _clamp(v["morale"] - 5)
        pawn["starving_ticks"] = pawn.get("starving_ticks", 0) + 1
        if before_hunger > 0:
            result.append(
                events.add_event(
                    "starving",
                    actor=pawn_id,
                    description=f"{pawn['name']} is starving!",
                )
            )
    else:
        pawn["starving_ticks"] = 0

    cold = (
        SEASON_COLD[biome["season"]]
        + (0 if day else 3)
        + WEATHER_COLD[biome["weather"]]
    )
    cold = round(cold * _modifier("cold"))
    if biome["season"] == "Winter" and _clear_cut():
        cold += WINDBREAK_COLD_PENALTY
    if pawn["gear"]["body"] == "Warm Coat":
        cold = max(0, cold - COAT_INSULATION)
    if _tradition() == HUNTERS_TAG:
        cold = max(0, cold - HUNTERS_COLD_REDUCTION)
    if any(m["name"] == "Divine Warmth" for m in pawn.get("moodlets", [])):
        cold = max(0, cold - MONUMENT_WARMTH_BLESSING)
    near_camp = _manhattan(pawn["pos"], CAMP_POS) <= CAMP_RANGE
    near_fire = lit and near_camp
    monument = state.world_state.setdefault(
        "monument", {"wood": 0, "stone": 0, "done": False, "inscription": None}
    )
    recovery = (
        WARMTH_RECOVERY
        + (CAMPFIRE_WARMTH if near_fire else 0)
        + (SHELTER_WARMTH if biome["shelter"] > 50 else 0)
        + (MONUMENT_INSULATION if monument.get("done") and near_camp else 0)
    )
    delta = recovery - cold
    if delta < 0 and v["warmth"] > 0:
        v["warmth"] = _clamp(v["warmth"] + delta)
        if v["warmth"] <= 0:
            v["warmth"] = 0
            _add_moodlet(pawn, "Frostbitten", -5, 10)
            result.append(
                events.add_event(
                    "frostbite",
                    actor=pawn_id,
                    description=f"{pawn['name']} suffers frostbite!",
                )
            )
    else:
        v["warmth"] = _clamp(v["warmth"] + delta)
    if v["warmth"] <= 0 and delta < 0:
        v["hp"] = _clamp(v["hp"] - FROSTBITE_HP)

    if biome["season"] == "Summer" and biome["weather"] == "Heatwave":
        v["energy"] = _clamp(v["energy"] - HEATWAVE_ENERGY)

    if is_elder(pawn):
        v["energy"] = _clamp(v["energy"] - ELDER_ENERGY_TAX)
        v["morale"] = _clamp(v["morale"] - ELDER_MORALE_TAX)

    morale = 0
    if biome["shelter"] > 50:
        morale += 1
    if near_fire:
        morale += 2
    if v["warmth"] > 50:
        morale += 1
    elif v["warmth"] < 30:
        morale -= 2
    if v["hunger"] > 50:
        morale += 1
    elif v["hunger"] < 30:
        morale -= 2
    v["morale"] = _clamp(v["morale"] + morale)

    net_mood = _tick_moodlets(pawn)
    if net_mood != 0:
        v["morale"] = _clamp(v["morale"] + net_mood)

    traits = pawn.get("traits", [])
    if "Night Owl" in traits:
        v["morale"] = _clamp(v["morale"] + (2 if not day else -2))
    if "Brawler" in traits:
        tool = pawn["gear"].get("main_hand")
        if tool and tool != "Flint Spear" and _custom_tool_bonus(pawn, "combat") <= 0:
            v["morale"] = _clamp(v["morale"] - 5)
    if "Pyromaniac" in traits and near_fire:
        v["morale"] = _clamp(v["morale"] + 5)

    has_pet = any(w["state"] == "tamed" for w in state.world_state["wildlife"])
    if has_pet:
        v["morale"] = _clamp(v["morale"] + PET_MORALE_BONUS)

    if monument.get("done"):
        # The Ancestral Monolith anchors colony morale: it never dips below 10.
        v["morale"] = max(v["morale"], MONUMENT_MORALE_FLOOR)

    if v["morale"] <= 0 and not pawn.get("mental_break"):
        pawn["mental_break"] = _break_archetype(pawn)
        pawn["break_ticks"] = BREAK_TICKS
        result.append(
            events.add_event(
                "break",
                actor=pawn_id,
                data={"break": pawn["mental_break"]},
                description=f"{pawn['name']} has a mental break: {pawn['mental_break']}!",
            )
        )


def _break_archetype(pawn):
    if "Pyromaniac" in pawn.get("traits", []):
        return "firesetter"
    pers = pawn["personality"]
    defaults = state.DEFAULT_PERSONALITY
    if pers.get("aggression", defaults["aggression"]) >= 6:
        return "berserk"
    if pers.get("bravery", defaults["bravery"]) <= 3:
        return "paranoid"
    return "apathetic"


def _nearest_pawn(pawn, pawn_id):
    best, best_dist = None, None
    for other_id, other in state.world_state["pawns"].items():
        if other_id == pawn_id or other["status"] != "active":
            continue
        dist = _manhattan(pawn["pos"], other["pos"])
        if best_dist is None or dist < best_dist:
            best, best_dist = other_id, dist
    return best


def _wander_from_camp(pawn):
    x, y = pawn["pos"]
    cur = _manhattan(pawn["pos"], CAMP_POS)
    for direction, (dx, dy) in DIRS.items():
        nx, ny = x + dx, y + dy
        if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
            continue
        if _manhattan([nx, ny], CAMP_POS) > cur:
            pawn["pos"] = [nx, ny]
            return True
    return False


def _resolve_break(pawn, pawn_id):
    kind = pawn["mental_break"]
    if kind == "berserk":
        target = _nearest_pawn(pawn, pawn_id)
        if target:
            tpawn = state.world_state["pawns"][target]
            damage = 8 + pawn["skills"]["combat"] // 2
            tpawn["vitals"]["hp"] = _clamp(tpawn["vitals"]["hp"] - damage)
            pawn["counters"]["damage_dealt"] += damage
            _adjust_relationship(pawn, target, -10)
            _adjust_relationship(tpawn, pawn_id, -15)
            desc = f"{pawn['name']} snaps and attacks {tpawn['name']} for {damage} damage!"
            if tpawn["vitals"]["hp"] <= 0:
                tpawn["vitals"]["hp"] = 0
                tpawn["status"] = "incapacitated"
                desc += f" {tpawn['name']} collapses!"
            return events.add_event(
                "break",
                actor=pawn_id,
                target=target,
                data={"break": "berserk", "damage": damage},
                description=desc,
            )
        biome = state.world_state["biome"]
        biome["shelter"] = _clamp(biome["shelter"] - _shelter_damage(5))
        return events.add_event(
            "break",
            actor=pawn_id,
            data={"break": "berserk"},
            description=f"{pawn['name']} rages and tears at the shelter (-5).",
        )
    if kind == "paranoid":
        if pawn["inventory"]["food"] >= 2:
            pawn["inventory"]["food"] -= 2
        return events.add_event(
            "break",
            actor=pawn_id,
            data={"break": "paranoid"},
            description=f"{pawn['name']} hides in the shadows, hoarding food.",
        )
    if kind == "firesetter":
        grid = state.world_state["grid"]
        x, y = pawn["pos"]
        for dx, dy in ((0, 0), *DIRS.values()):
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and grid[ny][nx] in FOREST_TILES:
                if _ignite(nx, ny):
                    return events.add_event(
                        "break",
                        actor=pawn_id,
                        data={"break": "firesetter", "action": "ignite", "pos": [nx, ny]},
                        description=f"{pawn['name']} maniacally sets the forest alight at ({nx},{ny})!",
                    )
        biome = state.world_state["biome"]
        if biome["campfire"] > 0:
            biome["campfire"] = _clamp(biome["campfire"] - 10)
            return events.add_event(
                "break",
                actor=pawn_id,
                data={"break": "firesetter", "action": "douse_fire"},
                description=f"{pawn['name']} maniacally douses the campfire (-10)!",
            )
        elif pawn["inventory"]["wood"] >= 2:
            pawn["inventory"]["wood"] -= 2
            return events.add_event(
                "break",
                actor=pawn_id,
                data={"break": "firesetter", "action": "burn_wood"},
                description=f"{pawn['name']} burns 2 stocks of wood in a manic frenzy!",
            )
        else:
            biome["shelter"] = _clamp(biome["shelter"] - _shelter_damage(5))
            return events.add_event(
                "break",
                actor=pawn_id,
                data={"break": "firesetter", "action": "damage_shelter"},
                description=f"{pawn['name']} sets a wild fire, damaging the shelter (-5)!",
            )
    moved = _wander_from_camp(pawn)
    return events.add_event(
        "break",
        actor=pawn_id,
        data={"break": "apathetic"},
        description=(
            f"{pawn['name']} wanders listlessly into the cold."
            if moved
            else f"{pawn['name']} stares blankly at the campfire."
        ),
    )


def _update_titles():
    """Recompute each living pawn's epithet from its lifetime counters."""
    for pawn in state.world_state["pawns"].values():
        if is_elder(pawn):
            pawn["title"] = "the Ancient"
            continue
        c = pawn["counters"]
        if c["damage_dealt"] >= 100:
            pawn["title"] = "the Scarred"
        elif c["trees_felled"] >= 50:
            pawn["title"] = "the Clear-Cutter"
        elif c["attacks_won"] >= 3:
            pawn["title"] = "the Bloodstained"
        elif c["rations_shared"] >= 10:
            pawn["title"] = "the Generous"
        elif c["blizzards_survived"] >= 3:
            pawn["title"] = "the Frost-Bitten"
        else:
            pawn["title"] = None


def _death_cause(pawn, biome):
    """Environmental permadeath only — combat stays incapacitation."""
    if biome["weather"] == "Blizzard" and pawn["vitals"]["warmth"] <= 0:
        return "froze in a blizzard"
    if pawn.get("starving_ticks", 0) > 5:
        return "starvation"
    if is_elder(pawn):
        if age_of(pawn) >= OLD_AGE_MAX or random.random() < OLD_AGE_DEATH_CHANCE:
            return "old age"
    return None


def _is_beloved(pawn_id, pawn):
    """The fallen are beloved when survivors hold high average regard for them."""
    vals = [
        rel
        for pid, rel in pawn["relationships"].items()
        if pid != pawn_id and pid in state.world_state["pawns"]
    ]
    if not vals:
        return False
    return sum(vals) / len(vals) >= BELOVED_RELATIONSHIP


def _kill(pawn_id, pawn, cause):
    """Remove a pawn and enshrine a snapshot in the graveyard."""
    entry = {
        "id": pawn_id,
        "name": pawn["name"],
        "title": pawn.get("title"),
        "cause": cause,
        "died_tick": state.world_state["tick"],
        "born_tick": pawn.get("born_tick", 0),
        "generation": pawn.get("generation", 1),
        "epitaph": f"Here lies {pawn['name']}, taken by {cause}.",
        "beloved": _is_beloved(pawn_id, pawn),
    }
    state.world_state["graveyard"].append(entry)
    for h in state.world_state["heirlooms"]:
        if h.get("owner") == pawn_id:
            h.pop("owner", None)
    if pawn.get("title") and pawn["gear"]["main_hand"]:
        tool = pawn["gear"]["main_hand"]
        state.world_state["heirlooms"].append({
            "id": state.next_heirloom_id(),
            "name": f"{pawn['name']}'s {tool}",
            "stat_bonus": HEIRLOOM_BONUS.get(tool, {"combat": 1}),
            "moodlet_delta": HEIRLOOM_MOODLET_DELTA,
            "source": f"death of {pawn['name']}",
        })
    for other in state.world_state["pawns"].values():
        if pawn_id in other.get("partners", []):
            if other["status"] in ("active", "incapacitated"):
                _grant_badge(other, "Widow")
            other["partners"].remove(pawn_id)
        if other["status"] in ("active", "incapacitated"):
            _add_moodlet(other, "Grief", -10, 10)
    pawn["status"] = "dead"
    pawn["vitals"]["hp"] = 0
    del state.world_state["pawns"][pawn_id]
    return events.add_event(
        "death",
        actor=pawn_id,
        data={"cause": cause},
        description=f"{pawn['name']} has fallen — {cause}.",
    )


def _seasonal_feast():
    """Winter/Summer solstice feast: consume camp food for colony-wide morale."""
    biome = state.world_state["biome"]
    if biome["food_stock"] <= FEAST_FOOD_REQUIRED:
        return None
    biome["food_stock"] = _clamp(biome["food_stock"] - FEAST_FOOD_COST)
    fed = 0
    for pawn in state.world_state["pawns"].values():
        if pawn["status"] != "active":
            continue
        pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + FEAST_MORALE)
        _add_moodlet(pawn, "Festive", FESTIVE_MOODLET_DELTA, FESTIVE_MOODLET_TICKS)
        fed += 1
    return events.add_event(
        "feast",
        data={"season": biome["season"], "food": FEAST_FOOD_COST, "fed": fed},
        description=(
            f"The colony gathers for a {biome['season']} Solstice Feast "
            f"(-{FEAST_FOOD_COST} camp food): everyone is Festive "
            f"(+{FEAST_MORALE} morale)."
        ),
    )


def _carve_rune(title, detail):
    """Record a permanent achievement rune on the monolith (capped archive).

    Only possible once the monolith stands. The rune event is staged on
    state.pending_runes so resolve_actions/tick_environment surface it in the
    Discord feed. Returns the event, or None if the monolith is unfinished.
    """
    monument = state.world_state.setdefault(
        "monument", {"wood": 0, "stone": 0, "done": False, "inscription": None}
    )
    if not monument.get("done"):
        return None
    runes = monument.setdefault("runes", [])
    runes.append({"tick": state.world_state["tick"], "title": title, "text": detail})
    del runes[:-MONUMENT_RUNE_MAX]
    ev = events.add_event(
        "rune",
        data={"title": title},
        description=f"A new rune is carved into the monolith: {title}.",
    )
    state.pending_runes.append(ev)
    return ev


def _drain_runes():
    evs = list(state.pending_runes)
    state.pending_runes.clear()
    return evs


def _evaluate_tradition():
    """Assign the colony's first tradition tag once its history crosses a threshold."""
    traditions = state.world_state.setdefault(
        "traditions",
        {"tag": None, "predators_slain": 0, "trees_felled": 0, "rations_shared": 0},
    )
    if traditions.get("tag"):
        return None
    if traditions.get("predators_slain", 0) > HUNTERS_THRESHOLD:
        tag = HUNTERS_TAG
    elif traditions.get("trees_felled", 0) > FORESTERS_THRESHOLD:
        tag = FORESTERS_TAG
    elif traditions.get("rations_shared", 0) > KINDRED_THRESHOLD:
        tag = KINDRED_TAG
    else:
        return None
    traditions["tag"] = tag
    _carve_rune(f"The {tag} tradition is born", f"The colony's way of life is sealed: {tag}.")
    return events.add_event(
        "tradition",
        data={"tag": tag},
        description=f"The colony has found its way of life: {tag}.",
    )


def tick_environment():
    result = []
    biome = state.world_state["biome"]
    tick = state.world_state["tick"]

    day = 1 if is_day() else 0
    prev_day = biome["day"]
    biome["day"] = day

    new_season = SEASONS[(tick // SEASON_TICKS) % len(SEASONS)]
    prev_season = biome["season"]
    if new_season != biome["season"]:
        state.pending_chronicle = new_season
        result.append(
            events.add_event(
                "season",
                data={"season": new_season},
                description=f"The {biome['season']} gives way to {new_season}.",
            )
        )
        if biome["season"] == "Winter" and new_season == "Spring":
            for pawn in state.world_state["pawns"].values():
                pawn["counters"]["blizzards_survived"] += 1
        new_wild = []
        for w in state.world_state["wildlife"]:
            if w["state"] == "tamed" or WILDLIFE[w["species"]]["kind"] != "predator":
                new_wild.append(w)
            else:
                result.append(events.add_event("wildlife_despawn", data={"species": w["species"]}, description=f"The {w['species']} retreats into the wilderness."))
        state.world_state["wildlife"] = new_wild

    biome["season"] = new_season

    if new_season != prev_season:
        tradition_event = _evaluate_tradition()
        if tradition_event:
            result.append(tradition_event)
        if new_season in FEAST_SEASONS:
            feast_event = _seasonal_feast()
            if feast_event:
                result.append(feast_event)

    if new_season == "Summer" and not biome.get("granary"):
        biome["food_stock"] = _clamp(biome["food_stock"] - 2)

    ws = state.world_state["wildlife"]
    spawn_mod = _modifier("spawn")
    overhunted = not _wild_predators()
    wild_cap = WILDLIFE_OVERPOP_MAX if overhunted else WILDLIFE_MAX
    if len(ws) < wild_cap and random.random() < 0.3 * spawn_mod:
        palisade_lvl = biome.get("palisade", 0)
        if new_season in ("Winter", "Autumn"):
            pred_chance = 0.25 * (1 - palisade_lvl * 0.3) * spawn_mod
            if random.random() < pred_chance:
                species = random.choice(PREDATOR_SPECIES)
                ws.append(state.make_animal(species, pos=[0, 0], hp=WILDLIFE[species]["hp"]))
                result.append(events.add_event("wildlife", data={"species": species}, description=f"A wild {species} appears."))
        else:
            prey_chance = PREY_SPAWN_OVERHUNT if overhunted else 0.3
            if random.random() < prey_chance * spawn_mod:
                species = random.choice(PREY_SPECIES)
                ws.append(state.make_animal(species, pos=[0, 0], hp=WILDLIFE[species]["hp"]))
                result.append(events.add_event("wildlife", data={"species": species}, description=f"A wild {species} appears."))

    active_pawns = [p for p in state.world_state["pawns"].values() if p["status"] == "active"]
    gone = []
    for w in list(ws):
        if w["state"] == "tamed":
            w["pos"] = list(CAMP_POS)
            continue
        spec = WILDLIFE[w["species"]]
        if spec["kind"] == "prey" and w.get("spawn_tick") != state.world_state["tick"] and random.random() < PREY_DESPAWN_CHANCE:
            gone.append(w["id"])
            result.append(events.add_event("wildlife_despawn", data={"species": w["species"]}, description=f"The {w['species']} bounds away into the brush."))
            continue
        if spec["kind"] == "prey" and active_pawns:
            nearest = min(active_pawns, key=lambda p: _manhattan(w["pos"], p["pos"]))
            if _manhattan(w["pos"], nearest["pos"]) <= 2:
                x, y = w["pos"]
                best_pos, max_d = w["pos"], _manhattan(w["pos"], nearest["pos"])
                for dx, dy in DIRS.values():
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                        d = _manhattan([nx, ny], nearest["pos"])
                        if d > max_d:
                            max_d = d
                            best_pos = [nx, ny]
                w["pos"] = best_pos
        elif spec["kind"] == "predator" and active_pawns:
            furthest = max(active_pawns, key=lambda p: _manhattan(p["pos"], CAMP_POS))
            x, y = w["pos"]
            best_pos, min_d = w["pos"], _manhattan(w["pos"], furthest["pos"])
            for dx, dy in DIRS.values():
                nx, ny = x + dx, y + dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                    d = _manhattan([nx, ny], furthest["pos"])
                    if d < min_d:
                        min_d = d
                        best_pos = [nx, ny]
            w["pos"] = best_pos

        if spec["kind"] == "predator":
            for pid, p in state.world_state["pawns"].items():
                if p["status"] == "active" and p["pos"] == w["pos"]:
                    bite = spec["bite_damage"]
                    p["vitals"]["hp"] = _clamp(p["vitals"]["hp"] - bite)
                    desc = f"The {w['species']} bites {p['name']} for {bite} damage!"
                    if p["vitals"]["hp"] <= 0:
                        p["vitals"]["hp"] = 0
                        p["status"] = "incapacitated"
                        desc += f" {p['name']} collapses!"
                    result.append(events.add_event("bite", actor=pid, data={"species": w["species"], "damage": bite}, description=desc))

    if gone:
        state.world_state["wildlife"] = [w for w in ws if w["id"] not in gone]

    if not state.world_state["pawns"]:
        state.world_state["wildlife"] = []

    _graze_tick(result)

    if random.random() < WEATHER_CHANGE_CHANCE:
        new_weather = random.choice(WEATHER_OPTIONS[new_season])
        if new_weather != biome["weather"]:
            result.append(
                events.add_event(
                    "weather",
                    data={"weather": new_weather},
                    description=f"The sky shifts: {new_weather}.",
                )
            )
        biome["weather"] = new_weather

    # Wildfire lifecycle: burn existing fires, spread to neighbours, then ignite.
    result += _tick_fires()
    result += _spread_fire()
    grid = state.world_state["grid"]
    if biome["weather"] == "Storm":
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if grid[y][x] in FOREST_TILES and random.random() < LIGHTNING_CHANCE:
                    if _ignite(x, y):
                        result.append(
                            events.add_event(
                                "fire_start",
                                data={"pos": [x, y], "cause": "lightning"},
                                description=f"Lightning strikes the forest at ({x},{y}) — fire!",
                            )
                        )
    if biome["weather"] == "Heatwave" and biome["wood_stock"] >= HIGH_WOOD:
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if grid[y][x] in FOREST_TILES and random.random() < HEATWAVE_FIRE_CHANCE:
                    if _ignite(x, y):
                        result.append(
                            events.add_event(
                                "fire_start",
                                data={"pos": [x, y], "cause": "heatwave"},
                                description=f"The Summer heatwave sets the forest ablaze at ({x},{y})!",
                            )
                        )

    # Seasonal disasters (Stage 4 part 2): flash floods, aurora, toxic miasma.
    biome["aurora"] = False
    flood_chance = FLOOD_CHANCE + (WINDBREAK_FLOOD_BONUS if _clear_cut() else 0)
    if (
        new_season == "Spring"
        and biome["weather"] == "Rain"
        and not biome.get("flood")
        and random.random() < flood_chance
    ):
        flooded = _trigger_flood()
        result.append(
            events.add_event(
                "flood",
                data={"flooded": flooded},
                description="The river bursts its banks and floods the low meadows!",
            )
        )
    if (
        new_season == "Winter"
        and biome["weather"] == "Clear"
        and not day
        and random.random() < AURORA_CHANCE
    ):
        biome["aurora"] = True
        for pawn in state.world_state["pawns"].values():
            if pawn["status"] == "active":
                pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + AURORA_MORALE)
        result.append(
            events.add_event(
                "aurora",
                description="Aurora Borealis dances across the clear winter sky, lifting every heart.",
            )
        )
    if (
        new_season == "Autumn"
        and biome["weather"] in ("Rain", "Storm")
        and not biome.get("miasma")
        and random.random() < MIASMA_CHANCE
    ):
        biome["miasma"] = MIASMA_TICKS
        result.append(
            events.add_event(
                "miasma",
                data={"ticks": MIASMA_TICKS},
                description="Toxic spores bloom from the ruins and seep across the map.",
            )
        )
    if biome.get("flood", 0) > 0:
        biome["flood"] -= 1
        if biome["flood"] <= 0:
            for x, y in biome.get("flooded", []):
                if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE and grid[y][x] == RIVER_TILE:
                    grid[y][x] = FIREBREAK_TILE
            biome["flooded"] = []
            biome["food_stock"] = _clamp(biome["food_stock"] + FLOOD_FOOD_BONUS)
            result.append(
                events.add_event(
                    "flood_recedes",
                    description=(
                        f"The floodwaters recede, leaving behind wild food "
                        f"(+{FLOOD_FOOD_BONUS} stock)."
                    ),
                )
            )
    if biome.get("miasma", 0) > 0:
        result += _tick_miasma()
        biome["miasma"] -= 1
        if biome["miasma"] <= 0:
            result.append(
                events.add_event("miasma_clear", description="The toxic spores disperse.")
            )

    # Visitors (Stage 5): a wandering NPC may step onto the grid edge.
    if len(state.world_state.get("visitors", [])) == 0 and tick % VISITOR_INTERVAL == 0:
        v = _spawn_visitor()
        result.append(
            events.add_event(
                "visitor",
                data={"id": v["id"], "action": "spawn", "kind": v["kind"]},
                description=f"A {v['kind']} named {v['name']} appears at the edge of the world.",
            )
        )
    result += _step_visitors()

    # Raiders (Stage 8): prosperous colonies attract Autumn scavenger raids.
    if (
        new_season == RAID_SEASON
        and tick % RAID_INTERVAL == 0
        and not state.world_state.get("raiders")
        and _colony_wealth() >= RAID_WEALTH_THRESHOLD
    ):
        result += _spawn_raid()
    result += _step_raiders()
    result += _check_quests()
    _camp_brawls(result)

    if day != prev_day:
        result.append(
            events.add_event(
                "daynight",
                data={"day": day},
                description="Dawn breaks." if day else "Night falls.",
            )
        )
        if day:
            _decay_relationships()

    was_alive = biome["campfire"] > 0
    lit = _feed_campfire()
    if was_alive and not lit:
        result.append(
            events.add_event("world", description="The campfire dies out.")
        )

    if new_season != "Winter":
        growth = REGROWTH_SPRING if new_season == "Spring" else REGROWTH
        growth = max(0, round(growth * _modifier("regrowth")))
        if biome["wood_stock"] < 100:
            biome["wood_stock"] = _clamp(biome["wood_stock"] + growth)
        if biome["food_stock"] < 100:
            biome["food_stock"] = _clamp(biome["food_stock"] + growth)

    result += _grow_farms()  # farm plots ripen in Spring/Summer, dormant otherwise

    for pawn_id, pawn in state.world_state["pawns"].items():
        if pawn.get("mental_break"):
            pawn["break_ticks"] = pawn.get("break_ticks", 0) - 1
            if pawn["break_ticks"] <= 0:
                pawn["mental_break"] = None
                pawn["break_ticks"] = 0
                pawn["vitals"]["morale"] = _clamp(
                    pawn["vitals"]["morale"] + BREAK_RECOVERY_MORALE
                )
                result.append(
                    events.add_event(
                        "break_end",
                        actor=pawn_id,
                        description=f"{pawn['name']} pulls back from the brink.",
                    )
                )
        _metabolize(pawn, pawn_id, biome, lit, day, result)
        _goal_nudge(pawn, 1, kind="survive")
        goal = pawn.get("goal")
        if goal and goal.get("kind") == "survive" and goal.get("progress", 0) >= goal.get("needed", 1):
            _complete_goal(pawn, pawn_id, goal, result)

    for pawn_id, pawn in list(state.world_state["pawns"].items()):
        if pawn.get("child_ticks", 0) > 0:
            pawn["child_ticks"] -= 1
    for pawn_id, pawn in list(state.world_state["pawns"].items()):
        if pawn.get("pregnant_ticks", 0) > 0:
            pawn["pregnant_ticks"] -= 1
            if pawn["pregnant_ticks"] <= 0:
                _give_birth(pawn, pawn_id, result)

    for pawn_id, pawn in list(state.world_state["pawns"].items()):
        cause = _death_cause(pawn, biome)
        if cause:
            result.append(_kill(pawn_id, pawn, cause))

    _update_titles()
    result += _drain_runes()
    return result


def resolve_actions(intents):
    """intents: dict pawn_id -> (action, target, flavor, new_goal). Applies deterministic effects."""
    resulting = []

    # Incapacitated pawns recover before anyone acts.
    for pawn_id, pawn in state.world_state["pawns"].items():
        if pawn["status"] == "dead":
            continue
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

    for pawn_id, intent in intents.items():
        pawn = state.world_state["pawns"].get(pawn_id)
        if pawn is None or pawn["status"] != "active":
            continue
        is_god_order = pawn_id in state.god_orders and state.god_orders[pawn_id].get("action") == intent[0]
        if pawn.get("mental_break"):
            resulting.append(_resolve_break(pawn, pawn_id))
            continue
        action = intent[0]
        target = intent[1] if len(intent) > 1 else None
        flavor = intent[2] if len(intent) > 2 else None
        if action == "Rest":
            resulting.append(_do_rest(pawn, pawn_id))
            if not is_god_order:
                state.failed_intents.pop(pawn_id, None)
        elif action == "Chop":
            ev = _do_chop(pawn, pawn_id)
            resulting.append(ev)
            if not is_god_order:
                reason = ev.get("data", {}).get("reason")
                if reason in FEASIBILITY_REASONS:
                    _record_feasibility(pawn_id, action, reason)
                else:
                    state.failed_intents.pop(pawn_id, None)
        elif action == "Scout":
            ev = _do_scout(pawn, pawn_id)
            resulting.append(ev)
            if not is_god_order:
                reason = ev.get("data", {}).get("reason")
                if reason in FEASIBILITY_REASONS:
                    _record_feasibility(pawn_id, action, reason)
                else:
                    state.failed_intents.pop(pawn_id, None)
        elif action == "Forage":
            ev = _do_forage(pawn, pawn_id)
            resulting.append(ev)
            if not is_god_order:
                reason = ev.get("data", {}).get("reason")
                if reason in FEASIBILITY_REASONS:
                    _record_feasibility(pawn_id, action, reason)
                else:
                    state.failed_intents.pop(pawn_id, None)
        elif action == "Build":
            ev = _do_build(pawn, pawn_id)
            resulting.append(ev)
            if not is_god_order:
                reason = ev.get("data", {}).get("reason")
                if reason in FEASIBILITY_REASONS:
                    _record_feasibility(pawn_id, action, reason)
                else:
                    state.failed_intents.pop(pawn_id, None)
        elif action == "Share":
            ev = _do_share(pawn, pawn_id, target)
            resulting.append(ev)
            if not is_god_order:
                reason = ev.get("data", {}).get("reason")
                if reason in FEASIBILITY_REASONS:
                    _record_feasibility(pawn_id, action, reason)
                else:
                    state.failed_intents.pop(pawn_id, None)
        elif action == "Attack":
            ev = _do_attack(pawn, pawn_id, target)
            resulting.append(ev)
            if not is_god_order:
                reason = ev.get("data", {}).get("reason")
                if reason in FEASIBILITY_REASONS:
                    _record_feasibility(pawn_id, action, reason)
                else:
                    state.failed_intents.pop(pawn_id, None)
        elif action == "Move":
            ev = _do_move(pawn, pawn_id, target)
            resulting.append(ev)
            if not is_god_order:
                reason = ev.get("data", {}).get("reason")
                if reason in FEASIBILITY_REASONS:
                    _record_feasibility(pawn_id, action, reason)
                else:
                    state.failed_intents.pop(pawn_id, None)
        elif action == "Mate":
            ev = _do_mate(pawn, pawn_id, target)
            resulting.append(ev)
            if not is_god_order:
                reason = ev.get("data", {}).get("reason")
                if reason in FEASIBILITY_REASONS:
                    _record_feasibility(pawn_id, action, reason)
                else:
                    state.failed_intents.pop(pawn_id, None)
        elif action == "Interact":
            ev = _do_interact(pawn, pawn_id, flavor)
            resulting.append(ev)
            if not is_god_order:
                reason = ev.get("data", {}).get("reason")
                if reason in FEASIBILITY_REASONS:
                    _record_feasibility(pawn_id, action, reason)
                else:
                    state.failed_intents.pop(pawn_id, None)
        else:
            resulting.append(
                events.add_event(
                    "failed",
                    actor=pawn_id,
                    data={"reason": "unknown_action"},
                    description=f"{pawn['name']} hesitates, unsure what to do.",
                )
            )

    # Personal goals: adopt fresh wishes, then pay off any now complete.
    for pawn_id, intent in intents.items():
        if len(intent) > 3 and intent[3]:
            pawn = state.world_state["pawns"].get(pawn_id)
            if pawn and pawn["status"] == "active":
                adopted = _adopt_goal(pawn, intent[3])
                if adopted:
                    pawn["goal"] = adopted
        if len(intent) > 4 and intent[4]:
            pawn = state.world_state["pawns"].get(pawn_id)
            if pawn and pawn["status"] == "active":
                adopted = _adopt_title(pawn, intent[4])
                if adopted:
                    resulting.append(
                        events.add_event(
                            "role",
                            actor=pawn_id,
                            data={"title": adopted["title"], "role": adopted["role"]},
                            description=(
                                f"{pawn['name']} earns a new role: {adopted['title']}!"
                            ),
                        )
                    )
    for pawn_id, pawn in state.world_state["pawns"].items():
        goal = pawn.get("goal")
        if goal and goal.get("progress", 0) >= goal.get("needed", 1):
            _complete_goal(pawn, pawn_id, goal, resulting)
        # Survive goals tick here too (not just in tick_environment).
        if goal and goal.get("kind") == "survive":
            _goal_nudge(pawn, 1, kind="survive")

    resulting += _drain_runes()
    return resulting
