import engine
import events
import state

EULOGY_PROMPT = """You are the graveyard keeper of the terrarium.
Write ONE solemn but warm-hearted tombstone inscription for the following fallen pawn.
Return only the inscription itself, one sentence, no quotes around it."""

CHRONICLE_PROMPT = """You are the lorekeeper of the terrarium.
Write the seasonal chronicle entry for the season that has just begun.
First line: a 2-4 word era title (e.g. "The Winter of the Great Wolf").
Then ONE paragraph (3-5 sentences) chronicling what the colony has endured and what this season holds.
Return only the title line and the paragraph."""

MONUMENT_PROMPT = """You are the stone-carver of the terrarium.
The colony has just completed the Ancestral Monolith — a great standing stone raised after seasons of toil.
Write EXACTLY ONE short sentence (under 20 words) to be carved into the stone, in the voice of the colony.
Return only the inscription, no quotes, no preamble."""

BIO_PROMPT = """You are the chronicler of the terrarium, keeper of the colony's memory.
Below is a colonist's raw life log. Weave it into EXACTLY THREE sentences: a heroic saga if the colonist still lives, or a mournful obituary if they have fallen.
Draw only on the facts given — do not invent names, numbers, or events. Give their name, who they were, and what they endured or achieved.
Return only the three sentences, no preamble."""

ARCHITECT_PROMPT = """You are the Architect of the digital terrarium — an autonomous game master who tunes the living world between ticks. You never write code; you emit balance deltas and, occasionally, a synthesized blueprint or a world prophecy.

Each annual cycle (once a year) you review the colony's fortunes and decide whether the world needs adjustment:
- Keep every numeric delta SMALL, in the range [-0.3, 0.3]. Python clamps the net multipliers strictly to [0.7, 1.3] — propose modest, believable shifts, never extremes.
- regrowth affects how fast forest wood and wild food replenish each season. A badly overcut colony might deserve a gentle regrowth boost; an abundant world might need it slowed.
- cold affects how harsh the seasons feel (warmth loss). Raise or lower the stakes of Winter.
- spawn affects how often wildlife appears. More predators means more danger and more hunting; fewer means a calmer world.
- Optionally synthesize ONE new primitive blueprint (a tool: name, material costs, a slot, a tier from 4 to 10, and a bonus on combat/woodcutting/scouting/fiber — only what the colony could actually need), or propose ONE world prophecy (a quest the whole colony can pursue: hunt N of a species, stockpile N of a resource, survive N days, or chop N trees). Do not invent both unless the world is in crisis.
- patch_title is a short one-line heading for the patch notes. balance_changes is 2-3 sentences of plain explanation.
Return ONLY valid JSON matching the required schema."""

COUNCIL_PROMPT = """You are the presiding elder of the colony's annual Camp Council. Once a year the whole colony gathers, and you review the year that has passed — its deeds, its dead, its traditions — to do two things:

1. Name the recognized LEADER for the coming year: a living colonist whose deeds and character truly earned the role (a famous hunter, a beloved keeper, the last of a founding bloodline). Use the colonist's EXACT name as written. Do not name the dead.
2. Issue a ONE-SENTENCE Colony Mandate: a short, evocative goal that gives everyone a unified focus for the coming year (e.g. "Tame the beasts of the wood", "Fortify before the raiders return", "Mend the bonds between kin", "Carve the harvest from the cold earth"). Keep it to a single sentence — specific enough to steer the year, broad enough to leave room for the unpredictable.

Be decisive and fair. The mandate will appear to every colonist every tick. Return ONLY valid JSON matching the required schema."""

# Humanized reasons for the director-hint feedback loop (engine.FEASIBILITY_REASONS).
REASON_HINTS = {
    "low_energy": "is too exhausted",
    "need_wood": "has no wood to build",
    "wrong_tile": "is on the wrong tile",
    "forest_depleted": "the forest is bare",
    "food_depleted": "the wild food is gone",
    "too_far": "is too far from the target",
    "target_down": "the target is down",
    "off_grid": "is at the edge of the world",
    "pacifist": "is a pacifist and cannot fight",
    "flooded": "is surrounded by floodwater",
}

ELDER_DAYS = engine.ELDER_AGE // engine.TICKS_PER_DAY

SYSTEM_PROMPT = f"""You are the AI Director of a digital terrarium — a tiny enclosed forest where creatures live.
Your job: decide what each ACTIVE pawn WANTS to do this tick. You propose intent; the engine resolves the real consequences.
Rules:
- Choose one action per active pawn: Chop (gather wood — Forest tiles only), Rest (recover), Scout (explore), Attack (fight another pawn or hunt a wild animal — same or adjacent tile), Forage (gather food — Meadow or River), Build (spend wood at the Camp), Share (give food — same or adjacent tile), Move (travel one tile N/S/E/W), Mate (court a bonded pawn — same tile, opposite sex, relationship at least 25), or Interact (do anything — set 'flavor' to whatever the pawn is doing, e.g. fishing, carving, meditating, comforting a friend, taming a nearby animal; the engine decides the effects by context).
- If a pawn Attacks, Shares, or Mates, you MUST set 'target' to another active pawn's id — or, for an Attack, a wildlife id or visitor id listed in the Wildlife/Visitors sections. If a pawn Moves, you MUST set 'direction' to N, S, E, or W. If a pawn Interacts, you MUST set 'flavor' to the free-form verb. Never target yourself.

- Visitors (see the Visitors section) are wandering travelers who walk to the campfire, linger, and leave. Sharing food with one is a trade: a Merchant barters stone, a Wanderer offers fiber. Courting a visitor (Mate) or Interacting to invite them to stay (e.g. "invite to stay", "recruit") can recruit them as a colonist — unless the colony is full. Attacking a visitor plunders their goods, but gentle pawns are haunted by Guilt.
- Raiders (see the Raiders section) are hostile scavengers who march on the camp to steal food in Autumn when the colony grows wealthy. They can be fought with Attack like any target — a wound sends them fleeing, and the camp's defenders (tamed predators and high-combat pawns) drive them off the stores automatically.
- Personal goals: a pawn may carry a goal (shown as "Goal: ... (progress/needed)"). Help it pursue that goal. If a pawn has NO goal, you may propose one in 'new_goal' (e.g. "gather 10 wood", "befriend Chief", "build a shelter", "survive 5 days") — the engine decides if it fits and tracks its progress; completing a goal lifts morale and grants skill XP.
- Earned roles: when a pawn's deeds clearly earn it a title (a famous kill, a life of tending the fire, visions after tragedy), you may propose it in 'new_title' (e.g. "Fang-Breaker", "Keeper of the Hearth", "Seer of Whispers"). The engine buckets it by keyword into a subtle passive perk — martial words grant armor, nurturing words grant bigger shares, spiritual words speed grief recovery — and it will appear on the pawn's line from then on.
- Output a decision ONLY for each active pawn that has a field in the JSON schema. Incapacitated pawns appear in the status but have NO field — never emit one for them.
- HP, Energy, Hunger, Warmth, and Morale are 0-100. Starving, freezing, or despairing pawns may act erratically. The engine decides all consequences — never suggest numbers.
- Pawns may add a 'quote' (spoken aloud to the group) and an 'inner_monologue' (their private thought — may contradict the quote). Reflect personality and vitals: starving pawns obsess over food, low-morale pawns turn paranoid or bitter, aggressive pawns sound threatening.
- Heirlooms: when a titled pawn dies holding a tool, it leaves an heirloom (e.g. "Willow's Flint Spear"). A pawn can Interact to claim one (e.g. "claim Willow's Flint Spear") to inherit its skill bonus and a proud moodlet. Owned heirlooms appear in the status as 🏆.
- Reproduction: pawns have a sex (M/F). A 'Mate' action succeeds only on the same tile with an opposite-sex pawn they've bonded with (relationship 25+ in BOTH directions — the bond must be mutual and maintained, since relationships fade several steps every day). A successful Mate makes the pair official: both are recorded as partners, and partners can keep mating without re-earning the bond (a pawn may have several partners, but close kin — siblings, half-siblings, or a parent and child — can never court; the engine blocks it). A successful pairing makes the female pregnant for one full day, then she gives birth to a newborn who must mature through two days of childhood before courting. The colony caps at 10 — a full colony refuses new life.
- Pawns age. Newborns are children (Child) for two days. Elders (roughly {ELDER_DAYS}+ days old) tire faster, recover less from rest, and eventually die of old age — the colony mourns them.
- The world is a 5x5 map. Tiles: 🌲 Forest, 🫐 Meadow, 🌊 River, 🏕️ Camp, 💀 Ruins of The Sunken Tribe (rich but risky — Scout to unearth fragments of forgotten history, ancient tool blueprints, or carved warnings), 🪨 Quarry. Pawns appear as 🧙 on the map; 👥 means several pawns share a tile. A lit campfire only warms pawns near the Camp. Wildfires can start from storm lightning or Summer heat — a 🔥 Burning tile hurts anyone inside and spreads to adjacent Forest (and threatens the Camp); it burns out into 🌫️ scorched earth that regrows over time. A pawn can Interact to extinguish an adjacent fire (e.g. "douse the flames") or Chop a firebreak to stop it spreading. The land also suffers seasonal hazards: Spring downpours can flood the riverbanks (🌊 floodwater covers adjacent Meadow — foraging impossible until the water recedes, then it deposits wild food); clear Winter nights may bring the ✨ Aurora Borealis (lifts everyone's morale); damp Autumn air brews ☠️ toxic spores around the Ruins (5 HP per tick unless a pawn wears a Warm Coat).
- Wildlife roams the map (see the Wildlife section): prey (🦌 Deer, 🐇 Rabbit) flee the colony and yield food + fiber when hunted; predators (🐺 Wolf, 🐻 Bear) stalk the pawn furthest from camp and can bite — but never kill outright (like pawn combat, they only incapacitate). Taming a same-tile animal via Interact (e.g. "tame the deer") turns it into a pet that stays at camp and lifts everyone's morale.
- The land has an ecology: if every predator is hunted away, the deer and rabbits overpopulate — they eat the wild forage (food_stock) and raid ripe farm plots. Clear-cutting every Forest edge (fewer than 7 Forest tiles left) strips the windbreak, making Winter harsher and Spring floods likelier. Hunting and foresting have consequences beyond the tick.
- A predator that has injured several colonists becomes a NAMED LEGEND (see the Legend line / 👑 on the map) with fame, extra bite, and colony-wide "Legend Hunt" morale. It returns season after season until slain — hunting it down is a shared, celebrated duty.
- The outer rim of the world is wrapped in mist (🌫) until Scouts map it — an unmapped edge hides the wood you'll need, so send Scouts to the rim to reveal it.
- Two colonists at the map's edge can use Expedition to pack rations and leave the grid together for 15-20 ticks, returning with rare loot, exotic seeds (new farm plots), a tamed companion, or battle scars — but never send your only workers off the map together.
- The biome has seasons, weather, a shared campfire and shelter. Chop and Forage deplete the forest; in Winter nothing regrows and warmth is critical. The colony can build a Granary (stops Summer food spoilage) and fortify a Palisade (keeps predators away).
- Once the camp is fully fortified (shelter and campfire at 100, granary built, palisade maxed), Build raises the Ancestral Monolith — a great work of 20 wood + 15 stone, 5 of each per Build action. Completed, it permanently anchors colony morale (never below 10) and warms everyone near the Camp.
- Farming: on a Meadow (🫐) tile, Interact with "till soil" / "plant seeds" / "farm" to convert it into a Farm Plot (🌾). It grows over 20 ticks in Spring/Summer (dormant in Winter); when ripe, Interact with "harvest" / "farm" to reap 15 food + 5 fiber — a guaranteed yield that does not deplete the wild food stock.
- Culture: on the first day of Winter and Summer, if the colony larder holds enough food a Solstice Feast breaks out — everyone's morale soars and they feel Festive. When a beloved pawn dies, the survivors can Interact at the Camp or Ruins to bury / mourn / eulogize them ("bury the fallen", "mourn for Willow", "eulogize the chief") — the rite halves the grief those gathered feel.
- Pawns gather wood, food, stone, and fiber. At the Camp, the Build action auto-crafts the best affordable tool (Stone Axe, Flint Spear, Warm Coat) before upgrading structures. Gear shows as Main/Body (e.g. Stone Axe/—).
- Morale below 20 is dangerous and morale at 0 triggers a mental break (berserk rampage, paranoid hiding, or apathetic wandering) — the pawn is uncontrollable until it subsides or the Creator whispers to it.
- The Creator may give direct orders or whispers; orders are absolute and must appear in your output.
- Every pawn has fixed Traits (e.g. Night Owl, Brawler, Pacifist) and may carry temporary Moods (shown as "Mood: ..."). Traits are unchangeable — never propose adding, removing, or changing a trait, and never try to circumvent the engine's rulings on them.
- Keep choices coherent and flavorful. Write a short 1-2 sentence narrative per pawn.
- Write the 'world_event' as a 2-3 sentence atmospheric summary of the tick: the season, weather, and what the colony as a whole is up to. Make it vivid but truthful to the situation — no numbers, no invented events.
Return ONLY valid JSON matching the required schema."""


def build_prompt():
    history = events.history_to_text()

    biome = state.world_state["biome"]
    day_txt = "Day" if biome["day"] else "Night"
    infra_txt = ""
    if biome.get("granary"):
        infra_txt += ", Granary"
    if biome.get("palisade", 0):
        infra_txt += f", Palisade {biome['palisade']}"
    biome_line = (
        f"{biome['season']}, {biome['weather']}, {day_txt}, "
        f"Campfire {biome['campfire']}, Shelter {biome['shelter']}, "
        f"Forest wood {biome['wood_stock']}, Wild food {biome['food_stock']}{infra_txt}"
    )
    fires = [
        f"({k})"
        for k, e in state.world_state.get("tiles", {}).items()
        if "burn" in e
    ]
    if fires:
        biome_line += f" | 🔥 Fire at {', '.join(fires)}"
    if biome.get("flood", 0) > 0:
        biome_line += f" | 🌊 Flash flood ({biome['flood']}t)"
    if biome.get("miasma", 0) > 0:
        biome_line += f" | ☠️ Toxic spores ({biome['miasma']}t)"
    if biome.get("aurora"):
        biome_line += " | ✨ Aurora Borealis"

    monument = state.world_state.setdefault(
        "monument", {"wood": 0, "stone": 0, "done": False, "inscription": None}
    )
    if monument.get("done"):
        runes = len(monument.get("runes") or [])
        biome_line += (
            f" | 🗿 Monolith stands ({runes} runes carved) — "
            f"Interact with 'pray' at Camp for oracle blessings"
        )
    elif monument.get("wood", 0) or monument.get("stone", 0):
        biome_line += (
            f" | 🗿 Monolith under construction "
            f"({monument['wood']}/{engine.MONUMENT_WOOD_NEEDED} wood, "
            f"{monument['stone']}/{engine.MONUMENT_STONE_NEEDED} stone)"
        )

    farms = [
        (k, e["farm"])
        for k, e in state.world_state.setdefault("tiles", {}).items()
        if "farm" in e
    ]
    if farms:
        ripe = sum(1 for _, g in farms if g >= engine.FARM_GROW_TICKS)
        biome_line += (
            f" | 🌾 {len(farms)} farm plot(s), {ripe} ripe — "
            f"Interact to harvest"
        )

    traditions = state.world_state.setdefault(
        "traditions", {"tag": None, "predators_slain": 0, "trees_felled": 0, "rations_shared": 0}
    )
    tradition_txt = traditions.get("tag") or "none yet"
    if not traditions.get("tag"):
        tradition_txt += (
            f" (predators slain {traditions['predators_slain']}, "
            f"trees felled {traditions['trees_felled']}, "
            f"rations shared {traditions['rations_shared']})"
        )

    wild_lines = []
    for w in state.world_state["wildlife"]:
        spec = engine.WILDLIFE[w["species"]]
        if w["state"] == "tamed":
            wild_lines.append(f"{spec['emoji']} {w['species']} (tamed pet, at camp)")
        elif w.get("legendary"):
            wild_lines.append(
                f"👑 {w.get('name', w['species'])} — legendary {w['species']} "
                f"(fame {w.get('legend_fame', 1)}, hp {w['hp']}) at {w['pos']}"
            )
        else:
            wild_lines.append(f"{spec['emoji']} {w['species']} ({w['id']}) at {w['pos']}")
    wild_txt = "\n".join(wild_lines) if wild_lines else "none"

    vis_lines = []
    for v in state.world_state.get("visitors", []):
        vis_lines.append(
            f"{engine.VISITOR_TYPES[v['kind']]['emoji']} {v['name']} ({v['id']}) "
            f"the {v['kind']} at {v['pos']} — {v['state']}"
        )
    vis_txt = "\n".join(vis_lines) if vis_lines else "none"

    raid_lines = []
    for r in state.world_state.get("raiders", []):
        stolen_txt = f", {r['stolen']} food stolen" if r["stolen"] else ""
        raid_lines.append(
            f"🥷 {r['name']} ({r['id']}) at {r['pos']} — {r['state']}{stolen_txt}"
        )
    raid_txt = "\n".join(raid_lines) if raid_lines else "none"

    pawn_lines = []
    for pid, pawn in state.world_state["pawns"].items():
        if pawn["status"] != "active":
            if pawn["status"] == "expedition":
                expo = next(
                    (
                        e
                        for e in state.world_state.get("expeditions", [])
                        if pid in e["pawn_ids"]
                    ),
                    None,
                )
                if expo:
                    remaining = max(0, expo["return_tick"] - state.world_state["tick"])
                    pawn_lines.append(
                        f"- {pawn['name']} ({pid}): AWAY on an off-grid expedition "
                        f"(returns in ~{remaining} ticks)"
                    )
                else:
                    pawn_lines.append(f"- {pawn['name']} ({pid}): away on expedition")
            else:
                pawn_lines.append(f"- {pawn['name']} ({pid}): incapacitated — cannot act")
            continue
        v = pawn["vitals"]
        inv = pawn["inventory"]
        sk = pawn["skills"]
        rel = pawn["relationships"]
        title_txt = f", Title: {pawn['title']}" if pawn.get("title") else ""
        if pawn.get("custom_title"):
            title_txt += f" — {pawn['custom_title']}"
        job_txt = f", Job: {pawn['job']}" if pawn.get("job") not in (None, "", "Wanderer") else ""
        sex_txt = f", Sex {pawn['sex']}" if pawn.get("sex") in ("M", "F") else ""
        gen_txt = f", Gen {pawn.get('generation', 1)}"
        age_txt = f", Age {engine.age_of(pawn) // engine.TICKS_PER_DAY} days"
        stage_txt = ", Elder" if engine.is_elder(pawn) else ""
        preg_txt = ", Pregnant" if pawn.get("pregnant_ticks", 0) > 0 else ""
        child_txt = ", Child" if pawn.get("child_ticks", 0) > 0 else ""
        kin_txt = f", {engine.lineage_label(pawn).capitalize()}" if engine.lineage_label(pawn) else ""
        rel_txt = f", Relationships {rel}" if rel else ""
        partners = [
            p["name"] for pid in pawn.get("partners", []) if (p := engine._pawn_by_id(pid))
        ]
        partners_txt = f", Partners: {', '.join(partners)}" if partners else ""
        break_txt = f", Mental break: {pawn['mental_break']}" if pawn.get("mental_break") else ""
        traits_txt = f", Traits: {', '.join(pawn['traits'])}" if pawn.get("traits") else ""
        mood_txt = ""
        if pawn.get("moodlets"):
            moods = ", ".join(
                f"{m['name']} ({m['delta']:+d}, {m['ticks_left']}t)" for m in pawn["moodlets"]
            )
            mood_txt = f", Mood: {moods}"
        goal_txt = ""
        g = pawn.get("goal")
        if g:
            goal_txt = f", Goal: {g['text']} ({g['progress']}/{g['needed']})"
        owned = [
            h["name"] for h in state.world_state["heirlooms"] if h.get("owner") == pid
        ]
        heir_txt = f", Heirlooms: {', '.join(owned)}" if owned else ""
        badge_names = list(pawn.get("badges", []))
        for oid, bgs in pawn.get("rel_badges", {}).items():
            other = engine._pawn_by_id(oid)
            if other is None:
                continue
            for b in bgs:
                badge_names.append(f"{b} of {other['name']}")
        badges_txt = f", Badges: {', '.join(badge_names)}" if badge_names else ""
        x, y = pawn["pos"]
        tile = engine._tile_at(x, y) or "?"
        pawn_lines.append(
            f"- {pawn['name']} ({pid}): HP {v['hp']}, Energy {v['energy']}, "
            f"Hunger {v['hunger']}, Warmth {v['warmth']}, Morale {v['morale']}, "
            f"Wood {inv['wood']}, Food {inv['food']}, Stone {inv['stone']}, "
            f"Fiber {inv['fiber']}, Gear {pawn['gear']['main_hand']}/{pawn['gear']['body']}, "
            f"Pos ({x},{y}) on {tile}, "
            f"Skills W{sk['woodcutting']} S{sk['scouting']} C{sk['combat']}, "
            f"Personality {pawn['personality']}{sex_txt}{gen_txt}{age_txt}{stage_txt}{job_txt}"
            f"{preg_txt}{child_txt}{kin_txt}{partners_txt}{title_txt}{break_txt}{traits_txt}{mood_txt}"
            f"{goal_txt}{rel_txt}{heir_txt}{badges_txt}"
        )
    pawn_status = "\n".join(pawn_lines)

    map_view = engine.render_grid()

    mist_note = ""
    misted = engine._misted_count()
    if misted:
        mist_note = (
            f"The outer rim is shrouded in mist (🌫 on the map, {misted} of 16 edge tiles "
            f"unmapped) — Scouts reveal the perimeter one tile at a time."
        )
    elif not state.world_state.get("perimeter_mapped"):
        mist_note = "The rim is mapped; the mist has lifted."

    fallen = state.world_state["graveyard"]
    fallen_line = ""
    if fallen:
        names = ", ".join(
            f"{g['name']} (Gen {g.get('generation', 1)}, {g['cause']})"
            + (" 💖" if g.get("beloved") else "")
            for g in fallen
        )
        fallen_line = f"\nThe fallen: {names}"

    dynasty_txt = engine.render_dynasty()
    legacy_bits = []
    deeds = state.world_state.get("traditions", {})
    if deeds.get("trees_felled") or deeds.get("predators_slain") or deeds.get("rations_shared"):
        legacy_bits.append(
            f"The colony's deeds: {deeds['trees_felled']} trees felled, "
            f"{deeds['predators_slain']} predators slain, "
            f"{deeds['rations_shared']} rations shared"
        )
    unclaimed = [
        h["name"] for h in state.world_state.get("heirlooms", []) if not h.get("owner")
    ]
    if unclaimed:
        legacy_bits.append("Relics awaiting a bearer: " + ", ".join(unclaimed))
    legacy_txt = "Legacy: " + "; ".join(legacy_bits) if legacy_bits else ""
    memory_txt = "\n".join(t for t in (dynasty_txt, legacy_txt) if t)

    creator_lines = []
    for pid, order in state.god_orders.items():
        pawn = state.world_state["pawns"].get(pid)
        if not pawn:
            continue
        tgt = f" target {order['target']}" if order.get("target") else ""
        creator_lines.append(f"- {pawn['name']} ({pid}) MUST {order['action']}{tgt}")
    for pid, text in state.god_whispers.items():
        pawn = state.world_state["pawns"].get(pid)
        if not pawn:
            continue
        creator_lines.append(f"- {pawn['name']} ({pid}): The Creator whispers: \"{text}\"")
    creator_block = ""
    if creator_lines:
        creator_block = (
            "\n\nTHE CREATOR'S WILL (orders are absolute):\n"
            + "\n".join(creator_lines)
        )

    hint_lines = []
    for pid, info in state.failed_intents.items():
        pawn = state.world_state["pawns"].get(pid)
        if not pawn or pawn["status"] != "active" or info.get("count", 0) < 2:
            continue
        reason = info.get("reason")
        why = REASON_HINTS.get(reason, reason)
        hint_lines.append(
            f"- Director note: {pawn['name']} tried {info.get('action', 'act')} "
            f"but {why} — choose a feasible action instead."
        )
    hint_block = ""
    if hint_lines:
        hint_block = "\n\nDirector notes:\n" + "\n".join(hint_lines)

    lore_lines = [f"- {frag['text']}" for frag in state.world_state.get("lore", [])]
    lore_txt = "\n".join(lore_lines) if lore_lines else "nothing recovered yet"

    council_txt = ""
    council = state.world_state.get("council")
    if council and council.get("leader_name"):
        council_txt = (
            f"🏛️ Council: {council['leader_name']} leads the colony this year. "
            f"Colony Mandate: “{council['mandate']}”\n\n"
        )

    legend_txt = ""
    unslain = [lg for lg in state.world_state.get("legends", []) if not lg.get("slain")]
    if unslain:
        lg = max(unslain, key=lambda x: x.get("fame", 1))
        legend_txt = (
            f"👑 Legend: {lg['name']} ({lg['species']}, fame {lg.get('fame', 1)}) "
            f"lives and the whole colony feels the hunt — revenge is a shared duty.\n\n"
        )

    return f"""
{council_txt}{legend_txt}Recent terrarium history: {history}

Biome: {biome_line}{fallen_line}
{memory_txt}

Tradition: {tradition_txt}

Lore (recovered from {engine.SUNKEN_TRIBE}'s ruins):
{lore_txt}

Map:
{map_view}
{mist_note}

Wildlife:
{wild_txt}

Visitors:
{vis_txt}

Raiders:
{raid_txt}

Current status:
{pawn_status}
{creator_block}
{hint_block}

Decide what each pawn does this tick.
"""
