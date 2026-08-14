import events
import state

SYSTEM_PROMPT = """You are the AI Director of a digital terrarium — a tiny enclosed forest where creatures live.
Your job: decide what each ACTIVE pawn WANTS to do this tick. You propose intent; the engine resolves the real consequences.
Rules:
- Choose one action per active pawn: Chop (work the forest), Rest (recover), Scout (explore), or Attack (fight another pawn).
- If a pawn Attacks, you MUST set 'target' to another active pawn's id. Never target yourself.
- HP and Energy are 0-100. Pawns act based on their vitals, skills, personality, and recent history.
- The Creator may give direct orders or whispers; orders are absolute and must appear in your output.
- Keep choices coherent and flavorful. Write a short 1-2 sentence narrative per pawn.
Return ONLY valid JSON matching the required schema."""


def build_prompt():
    history = events.history_to_text()

    pawn_lines = []
    for pid, pawn in state.world_state["pawns"].items():
        if pawn["status"] != "active":
            pawn_lines.append(f"- {pawn['name']} ({pid}): incapacitated — cannot act")
            continue
        v = pawn["vitals"]
        inv = pawn["inventory"]
        sk = pawn["skills"]
        pawn_lines.append(
            f"- {pawn['name']} ({pid}): HP {v['hp']}, Energy {v['energy']}, "
            f"Wood {inv['wood']}, Food {inv['food']}, "
            f"Skills W{sk['woodcutting']} S{sk['scouting']} C{sk['combat']}, "
            f"Personality {pawn['personality']}"
        )
    pawn_status = "\n".join(pawn_lines)

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

Current status:
{pawn_status}
{creator_block}

Decide what each pawn does this tick.
"""
