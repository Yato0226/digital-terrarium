from typing import Literal, Optional

from pydantic import Field, create_model

import state

ACTIONS = ("Chop", "Rest", "Scout", "Attack", "Forage", "Build", "Share", "Move", "Mate", "Interact")


def build_models():
    """Rebuild the LLM output schema each tick from currently active pawns."""
    pawn_ids = [
        pid
        for pid, pawn in state.world_state["pawns"].items()
        if pawn["status"] == "active"
    ]
    if not pawn_ids:
        raise ValueError("No active pawns to simulate")
    target_ids = (
        pawn_ids
        + [w["id"] for w in state.world_state["wildlife"]]
        + [v["id"] for v in state.world_state.get("visitors", [])]
        + [r["id"] for r in state.world_state.get("raiders", [])]
    )

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
        quote=(
            Optional[str],
            Field(default=None, description="One line of outward speech to the group."),
        ),
        inner_monologue=(
            Optional[str],
            Field(default=None, description="What the pawn privately thinks — may contradict the quote."),
        ),
        direction=(
            Optional[Literal[("N", "S", "E", "W")]],
            Field(default=None, description="Direction — only for the Move action."),
        ),
        target=(
            Optional[Literal[tuple(target_ids)]],
            Field(default=None, description="Target pawn id (Attack/Share/Mate), wildlife id (Attack/tame), visitor id (Share/barter, Mate/recruit, Attack/plunder), or raider id (Attack) — never self."),
        ),
        flavor=(
            Optional[str],
            Field(default=None, description="Free-form verb — only for the Interact action (e.g. fishing, carving, meditating)."),
        ),
        new_goal=(
            Optional[str],
            Field(default=None, description="A personal goal wish, only when the pawn has no goal (e.g. 'gather 10 wood', 'befriend Chief')."),
        ),
    )
    fields = {
        "world_event": (
            str,
            Field(description="A 2-3 sentence atmospheric summary of this tick — what the season, weather, and colony are doing."),
        ),
    }
    for pid in pawn_ids:
        fields[pid] = (AgentDecision, Field(description=f"Decision for {pid}"))
    return create_model("TickResponse", **fields)
