import asyncio

import requests
from ollama import chat

import engine
import events
import prompts
import schema
import state
from config import DISCORD_WEBHOOK_URL, MODEL_NAME, TICK_INTERVAL_SECONDS

pause_event = asyncio.Event()
pause_event.set()

tick_lock = asyncio.Lock()


def post_to_discord(data):
    fields = []
    for pid, pawn in state.world_state["pawns"].items():
        if pawn["status"] == "active":
            decision = getattr(data, pid)
            value = f"*{decision.narrative}* (Action: {decision.action})"
        else:
            value = "💤 *Incapacitated* — recovering"
        name = (
            f"🌲 {pawn['name']} ({pid}) | HP {pawn['vitals']['hp']} | "
            f"Energy {pawn['vitals']['energy']} | Wood {pawn['inventory']['wood']} | "
            f"Food {pawn['inventory']['food']}"
        )
        fields.append({"name": name, "value": value, "inline": False})

    footer_text = " → ".join(
        ev["description"] for ev in state.world_state["history"][-3:]
    )
    embed = {
        "title": f"🌿 Terrarium Tick #{state.world_state['tick']}",
        "description": data.world_event,
        "fields": fields[:25],
        "footer": {"text": footer_text},
    }
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Discord post failed: {e}")


async def run_tick():
    async with tick_lock:
        print(f"🌱 Tick {state.world_state['tick']} starting...")

        try:
            TickResponse = schema.build_models()
        except ValueError as e:
            print(f"❌ Schema error: {e}")
            state.world_state["tick"] += 1
            return

        prompt = prompts.build_prompt()
        try:
            response = await asyncio.to_thread(
                chat,
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": prompts.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                format=TickResponse.model_json_schema(),
            )
            content = response.message.content
            if content is None:
                raise ValueError("LLM returned empty content")
            data = TickResponse.model_validate_json(content)
        except Exception as e:
            print(f"❌ LLM or parsing error: {e}")
            state.world_state["tick"] += 1
            return

        events.add_event("world", description=data.world_event)

        # Build intents; god orders override the LLM's proposal.
        intents = {}
        for pid, pawn in state.world_state["pawns"].items():
            if pawn["status"] != "active":
                continue
            decision = getattr(data, pid)
            action, target = decision.action, decision.target
            order = state.god_orders.get(pid)
            if order:
                action, target = order["action"], order.get("target")
            intents[pid] = (action, target)

        engine.resolve_actions(intents)
        state.god_orders.clear()
        state.god_whispers.clear()
        state.save_state()

        await asyncio.to_thread(post_to_discord, data)

        state.world_state["tick"] += 1
        print(f"✅ Tick complete. {state.status_summary()}")


async def tick_loop():
    while True:
        await pause_event.wait()
        await run_tick()
        for _ in range(TICK_INTERVAL_SECONDS):
            await asyncio.sleep(1)
            if not pause_event.is_set():
                break
