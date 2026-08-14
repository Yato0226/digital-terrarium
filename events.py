import json

import state

LOGGING = True


def add_event(event_type, actor=None, target=None, data=None, description=""):
    event = {
        "tick": state.world_state["tick"],
        "type": event_type,
        "actor": actor,
        "target": target,
        "data": data or {},
        "description": description,
    }
    state.world_state["history"].append(event)
    if len(state.world_state["history"]) > state.MAX_HISTORY:
        state.world_state["history"].pop(0)
    if LOGGING:
        try:
            with open(state.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
            pass
    return event


def history_to_text():
    if not state.world_state["history"]:
        return "The terrarium is calm and new."
    return " | ".join(
        ev.get("description") or ev.get("type")
        for ev in state.world_state["history"]
    )
