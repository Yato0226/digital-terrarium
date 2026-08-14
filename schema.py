from typing import Literal, Optional

from pydantic import Field, create_model

import state

ACTIONS = ("Chop", "Rest", "Scout", "Attack")


def build_models():
    """Rebuild the LLM output schema each tick from currently active pawns."""
    pawn_ids = [
        pid
        for pid, pawn in state.world_state["pawns"].items()
        if pawn["status"] == "active"
    ]
    if not pawn_ids:
        raise ValueError("No active pawns to simulate")

    AgentDecision = create_model(
        "AgentDecision",
        action=(
            Literal[ACTIONS],
            Field(description="Action the pawn intends this tick."),
        ),
        narrative=(
            str,
            Field(description="1-2 sentence description of what the pawn does this tick."),
        ),
        target=(
            Optional[Literal[tuple(pawn_ids)]],
            Field(default=None, description="Target pawn id — ONLY for Attack."),
        ),
    )
    fields = {
        "world_event": (
            str,
            Field(description="A short global status update for the terrarium"),
        ),
    }
    for pid in pawn_ids:
        fields[pid] = (AgentDecision, Field(description=f"Decision for {pid}"))
    return create_model("TickResponse", **fields)
