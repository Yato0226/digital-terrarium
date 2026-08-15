import engine
import events
import state

EULOGY_PROMPT = """You are the graveyard keeper of the terrarium.
Write ONE solemn but warm-hearted tombstone inscription for the following fallen pawn.
Return only the inscription itself, one sentence, no quotes around it."""

SYSTEM_PROMPT = """You are the AI Director of a digital terrarium — a tiny enclosed forest where creatures live.
Your job: decide what each ACTIVE pawn WANTS to do this tick. You propose intent; the engine resolves the real consequences.
Rules:
- Choose one action per active pawn: Chop (gather wood — Forest tiles only), Rest (recover), Scout (explore), Attack (fight another pawn — same or adjacent tile), Forage (gather food — Meadow or River), Build (spend wood at the Camp), Share (give food — same or adjacent tile), or Move (travel one tile N/S/E/W).
- If a pawn Attacks or Shares, you MUST set 'target' to another active pawn's id. If a pawn Moves, you MUST set 'direction' to N, S, E, or W. Never target yourself.
- Output a decision ONLY for each active pawn that has a field in the JSON schema. Incapacitated pawns appear in the status but have NO field — never emit one for them.
- HP, Energy, Hunger, Warmth, and Morale are 0-100. Starving, freezing, or despairing pawns may act erratically. The engine decides all consequences — never suggest numbers.
- Pawns may add a 'quote' (spoken aloud to the group) and an 'inner_monologue' (their private thought — may contradict the quote). Reflect personality and vitals: starving pawns obsess over food, low-morale pawns turn paranoid or bitter, aggressive pawns sound threatening.
- The world is a 5x5 map. Tiles: 🌲 Forest, 🫐 Meadow, 🌊 River, 🏕️ Camp, 💀 Ruins (rich but risky), 🪨 Quarry. Pawns appear as 🧙 on the map; 👥 means several pawns share a tile. A lit campfire only warms pawns near the Camp.
- The biome has seasons, weather, a shared campfire and shelter. Chop and Forage deplete the forest; in Winter nothing regrows and warmth is critical.
- Pawns gather wood, food, stone, and fiber. At the Camp, the Build action auto-crafts the best affordable tool (Stone Axe, Flint Spear, Warm Coat) before upgrading structures. Gear shows as Main/Body (e.g. Stone Axe/—).
- Morale below 20 is dangerous and morale at 0 triggers a mental break (berserk rampage, paranoid hiding, or apathetic wandering) — the pawn is uncontrollable until it subsides or the Creator whispers to it.
- The Creator may give direct orders or whispers; orders are absolute and must appear in your output.
- Keep choices coherent and flavorful. Write a short 1-2 sentence narrative per pawn.
Return ONLY valid JSON matching the required schema."""


def build_prompt():
    history = events.history_to_text()

    biome = state.world_state["biome"]
    day_txt = "Day" if biome["day"] else "Night"
    biome_line = (
        f"{biome['season']}, {biome['weather']}, {day_txt}, "
        f"Campfire {biome['campfire']}, Shelter {biome['shelter']}, "
        f"Forest wood {biome['wood_stock']}, Wild food {biome['food_stock']}"
    )

    pawn_lines = []
    for pid, pawn in state.world_state["pawns"].items():
        if pawn["status"] != "active":
            pawn_lines.append(f"- {pawn['name']} ({pid}): incapacitated — cannot act")
            continue
        v = pawn["vitals"]
        inv = pawn["inventory"]
        sk = pawn["skills"]
        rel = pawn["relationships"]
        title_txt = f", Title: {pawn['title']}" if pawn.get("title") else ""
        rel_txt = f", Relationships {rel}" if rel else ""
        break_txt = f", Mental break: {pawn['mental_break']}" if pawn.get("mental_break") else ""
        x, y = pawn["pos"]
        tile = engine._tile_at(x, y) or "?"
        pawn_lines.append(
            f"- {pawn['name']} ({pid}): HP {v['hp']}, Energy {v['energy']}, "
            f"Hunger {v['hunger']}, Warmth {v['warmth']}, Morale {v['morale']}, "
            f"Wood {inv['wood']}, Food {inv['food']}, Stone {inv['stone']}, "
            f"Fiber {inv['fiber']}, Gear {pawn['gear']['main_hand']}/{pawn['gear']['body']}, "
            f"Pos ({x},{y}) on {tile}, "
            f"Skills W{sk['woodcutting']} S{sk['scouting']} C{sk['combat']}, "
            f"Personality {pawn['personality']}{title_txt}{break_txt}{rel_txt}"
        )
    pawn_status = "\n".join(pawn_lines)

    map_view = engine.render_grid()

    fallen = state.world_state["graveyard"]
    fallen_line = ""
    if fallen:
        names = ", ".join(f"{g['name']} ({g['cause']})" for g in fallen)
        fallen_line = f"\nThe fallen: {names}"

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

    return f"""
Recent terrarium history: {history}

Biome: {biome_line}{fallen_line}

Map:
{map_view}

Current status:
{pawn_status}
{creator_block}

Decide what each pawn does this tick.
"""
