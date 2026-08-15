import random

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
}
ACTIONS = tuple(ACTION_COSTS)
SKILL_MAX = 20
RECOVER_HEAL = 10

GRID_SIZE = state.GRID_SIZE
CAMP_POS = state.CAMP_POS
CAMP_RANGE = 1
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
FOREST_TILES = {"🌲"}
FORAGE_TILES = {"🫐", "🌊"}
BUILD_TILE = "🏕️"
RUIN_TILE = "💀"
QUARRY_TILE = "🪨"

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

SEASON_TICKS = 100
DAY_CYCLE = 20
DAY_LENGTH = 10
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


def _inspire_bonus(pawn, amount):
    """Morale above 80 → +10% gather/craft yield (Inspiration)."""
    if pawn["vitals"]["morale"] > INSPIRED_MORALE:
        return amount + amount // 10
    return amount


def is_day():
    return (state.world_state["tick"] % DAY_CYCLE) < DAY_LENGTH


def _tile_at(x, y):
    grid = state.world_state["grid"]
    if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
        return grid[y][x]
    return None


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def render_grid():
    """ASCII/emoji codeblock view of the 5x5 map with pawns on it."""
    grid = state.world_state["grid"]
    occupants = {}
    for pawn in state.world_state["pawns"].values():
        if pawn["status"] != "active":
            continue
        x, y = pawn["pos"]
        occupants[(x, y)] = occupants.get((x, y), 0) + 1
    lines = []
    for y in range(len(grid)):
        cells = []
        for x in range(len(grid[y])):
            n = occupants.get((x, y), 0)
            if n > 1:
                cells.append("[👥]")
            elif n == 1:
                cells.append("[🧙]")
            else:
                cells.append(f"[{grid[y][x]}]")
        lines.append("".join(cells))
    return "\n".join(lines)


def _do_rest(pawn, pawn_id):
    pawn["vitals"]["hp"] = _clamp(pawn["vitals"]["hp"] + 10)
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
    wood = _inspire_bonus(pawn, wood)
    wood = min(biome["wood_stock"], wood)
    biome["wood_stock"] -= wood
    pawn["inventory"]["wood"] += wood
    pawn["counters"]["trees_felled"] += 1
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
    if _tile_at(*pawn["pos"]) == QUARRY_TILE:
        _gain_skill(pawn, "scouting")
        stone = 1 + skill // 5 + random.choice([0, 1])
        pawn["inventory"]["stone"] += stone
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
        food = 4 + skill // 3 + random.choice([0, 1])
        pawn["inventory"]["food"] += food
        return events.add_event(
            "scout",
            actor=pawn_id,
            data={"food": food, "tile": "ruins"},
            description=f"{pawn['name']} scavenges the ruins and finds {food} food.",
        )
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
    food = _inspire_bonus(pawn, food)
    food = min(biome["food_stock"], food)
    biome["food_stock"] -= food
    pawn["inventory"]["food"] += food
    fiber_gain = 0
    if _tile_at(*pawn["pos"]) == "🫐" and random.random() < 0.35:
        fiber_gain = 1
        pawn["inventory"]["fiber"] += fiber_gain
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
    """Auto-craft the highest-tier affordable tool not yet owned."""
    inv = pawn["inventory"]
    gear = pawn["gear"]
    candidates = []
    for name, recipe in RECIPES.items():
        slot = recipe["slot"]
        if gear[slot] is not None:
            continue
        if all(
            inv.get(res, 0) >= cost
            for res, cost in recipe.items()
            if res != "slot"
        ):
            candidates.append(name)
    if not candidates:
        return None
    best = max(candidates, key=lambda name: TOOL_TIER[name])
    recipe = RECIPES[best]
    for res, cost in recipe.items():
        if res != "slot":
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
        return events.add_event(
            "craft",
            actor=pawn_id,
            data={"item": crafted},
            description=f"{pawn['name']} crafts a {crafted}.",
        )
    if pawn["inventory"]["wood"] < BUILD_WOOD_COST:
        return events.add_event(
            "failed",
            actor=pawn_id,
            data={"reason": "need_wood"},
            description=f"{pawn['name']} doesn't have enough wood to build.",
        )
    pawn["inventory"]["wood"] -= BUILD_WOOD_COST
    biome = state.world_state["biome"]
    if biome["shelter"] < 100:
        biome["shelter"] = _clamp(biome["shelter"] + BUILD_GAIN)
        _gain_skill(pawn, "woodcutting")
        return events.add_event(
            "build",
            actor=pawn_id,
            data={"structure": "shelter", "level": biome["shelter"]},
            description=f"{pawn['name']} reinforces the shelter.",
        )
    biome["campfire"] = _clamp(biome["campfire"] + BUILD_GAIN)
    _gain_skill(pawn, "woodcutting")
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
        + (SPEAR_DAMAGE if pawn["gear"]["main_hand"] == "Flint Spear" else 0),
    )
    tpawn["vitals"]["hp"] = _clamp(tpawn["vitals"]["hp"] - damage)
    pawn["counters"]["attacks_won"] += 1
    pawn["counters"]["damage_dealt"] += damage
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
    if pawn["inventory"]["food"] < SHARE_FOOD:
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
    pawn["inventory"]["food"] -= SHARE_FOOD
    tpawn["inventory"]["food"] += SHARE_FOOD
    pawn["counters"]["rations_shared"] += 1
    _adjust_relationship(pawn, target, 25)
    _adjust_relationship(tpawn, pawn_id, 25)
    pawn["vitals"]["morale"] = _clamp(pawn["vitals"]["morale"] + 5)
    tpawn["vitals"]["morale"] = _clamp(tpawn["vitals"]["morale"] + 5)
    return events.add_event(
        "share",
        actor=pawn_id,
        target=target,
        data={"food": SHARE_FOOD},
        description=f"{pawn['name']} shares food with {tpawn['name']}.",
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
    v["hunger"] = _clamp(v["hunger"] - HUNGER_DRAIN)
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
    if pawn["gear"]["body"] == "Warm Coat":
        cold = max(0, cold - COAT_INSULATION)
    near_fire = lit and _manhattan(pawn["pos"], CAMP_POS) <= CAMP_RANGE
    recovery = (
        WARMTH_RECOVERY
        + (CAMPFIRE_WARMTH if near_fire else 0)
        + (SHELTER_WARMTH if biome["shelter"] > 50 else 0)
    )
    delta = recovery - cold
    if delta < 0 and v["warmth"] > 0:
        v["warmth"] = _clamp(v["warmth"] + delta)
        if v["warmth"] <= 0:
            v["warmth"] = 0
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
    if not day:
        morale -= 1
    v["morale"] = _clamp(v["morale"] + morale)

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
    pers = pawn["personality"]
    if pers.get("aggression", 0) >= 6:
        return "berserk"
    if pers.get("bravery", 5) <= 3:
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
        biome["shelter"] = _clamp(biome["shelter"] - 5)
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
    return None


def _kill(pawn_id, pawn, cause):
    """Remove a pawn and enshrine a snapshot in the graveyard."""
    entry = {
        "id": pawn_id,
        "name": pawn["name"],
        "title": pawn.get("title"),
        "cause": cause,
        "died_tick": state.world_state["tick"],
        "born_tick": pawn.get("born_tick", 0),
        "epitaph": f"Here lies {pawn['name']}, taken by {cause}.",
    }
    state.world_state["graveyard"].append(entry)
    pawn["status"] = "dead"
    pawn["vitals"]["hp"] = 0
    del state.world_state["pawns"][pawn_id]
    return events.add_event(
        "death",
        actor=pawn_id,
        data={"cause": cause},
        description=f"{pawn['name']} has fallen — {cause}.",
    )


def tick_environment():
    result = []
    biome = state.world_state["biome"]
    tick = state.world_state["tick"]

    day = 1 if is_day() else 0
    prev_day = biome["day"]
    biome["day"] = day

    new_season = SEASONS[(tick // SEASON_TICKS) % len(SEASONS)]
    if new_season != biome["season"]:
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
    biome["season"] = new_season

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

    if day != prev_day:
        result.append(
            events.add_event(
                "daynight",
                data={"day": day},
                description="Dawn breaks." if day else "Night falls.",
            )
        )

    was_alive = biome["campfire"] > 0
    lit = _feed_campfire()
    if was_alive and not lit:
        result.append(
            events.add_event("world", description="The campfire dies out.")
        )

    if new_season != "Winter":
        growth = REGROWTH_SPRING if new_season == "Spring" else REGROWTH
        if biome["wood_stock"] < 100:
            biome["wood_stock"] = _clamp(biome["wood_stock"] + growth)
        if biome["food_stock"] < 100:
            biome["food_stock"] = _clamp(biome["food_stock"] + growth)

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

    for pawn_id, pawn in list(state.world_state["pawns"].items()):
        cause = _death_cause(pawn, biome)
        if cause:
            result.append(_kill(pawn_id, pawn, cause))

    _update_titles()
    return result


def resolve_actions(intents):
    """intents: dict pawn_id -> (action, target). Applies deterministic effects."""
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

    for pawn_id, (action, target) in intents.items():
        pawn = state.world_state["pawns"].get(pawn_id)
        if pawn is None or pawn["status"] != "active":
            continue
        if pawn.get("mental_break"):
            resulting.append(_resolve_break(pawn, pawn_id))
            continue
        if action == "Rest":
            resulting.append(_do_rest(pawn, pawn_id))
        elif action == "Chop":
            resulting.append(_do_chop(pawn, pawn_id))
        elif action == "Scout":
            resulting.append(_do_scout(pawn, pawn_id))
        elif action == "Forage":
            resulting.append(_do_forage(pawn, pawn_id))
        elif action == "Build":
            resulting.append(_do_build(pawn, pawn_id))
        elif action == "Share":
            resulting.append(_do_share(pawn, pawn_id, target))
        elif action == "Attack":
            resulting.append(_do_attack(pawn, pawn_id, target))
        elif action == "Move":
            resulting.append(_do_move(pawn, pawn_id, target))
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
