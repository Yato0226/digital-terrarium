import asyncio

import requests

import config
import engine
import events
import llm
import prompts
import schema
import state
from config import DISCORD_WEBHOOK_URL, TICK_INTERVAL_SECONDS

pause_event = asyncio.Event()
pause_event.set()

tick_lock = asyncio.Lock()


def post_to_discord(data):
    fields = []
    biome = state.world_state["biome"]
    day_txt = "☀️ Day" if biome["day"] else "🌙 Night"
    season_emoji = {
        "Spring": "🌸",
        "Summer": "☀️",
        "Autumn": "🍂",
        "Winter": "❄️",
    }.get(biome["season"], "")
    fields.append(
        {
            "name": f"{season_emoji} {biome['season']}, {biome['weather']}, {day_txt}",
            "value": (
                "```"
                + engine.render_grid()
                + "```\n"
                f"🔥 Campfire {biome['campfire']} | 🏠 Shelter {biome['shelter']} | "
                f"🌲 Wood {biome['wood_stock']} | 🍎 Food {biome['food_stock']}"
            ),
            "inline": False,
        }
    )

    for pid, pawn in state.world_state["pawns"].items():
        if pawn["status"] == "active":
            decision = getattr(data, pid, None)
            if decision is not None:
                value = f"*{decision.narrative}*"
                quote = getattr(decision, "quote", None)
                if quote:
                    value += f" 💬 *\"{quote}\"*"
                action_txt = f" | {decision.action}"
            else:
                value = "🌱 *A new life enters the terrarium.*"
                action_txt = ""
        else:
            value = "💤 *Incapacitated* — recovering"
            action_txt = ""
        v = pawn["vitals"]
        title = f" {pawn['title']}" if pawn.get("title") else ""
        job_txt = f" the {pawn['job']}" if pawn.get("job") not in (None, "", "Wanderer") else ""
        sex_txt = "♂" if pawn.get("sex") == "M" else "♀" if pawn.get("sex") == "F" else ""
        preg_txt = " 🤰" if pawn.get("pregnant_ticks", 0) > 0 else ""
        child_txt = " 👶" if pawn.get("child_ticks", 0) > 0 else ""
        break_txt = f" 🌀{pawn['mental_break']}" if pawn.get("mental_break") else ""
        gear_txt = f" {pawn['gear']['main_hand'] or '—'}/{pawn['gear']['body'] or '—'}"
        inv = pawn["inventory"]
        name = (
            f"🌲 {pawn['name']}{sex_txt}{job_txt}{title}{break_txt}{preg_txt}{child_txt} | "
            f"HP{v['hp']} E{v['energy']} H{v['hunger']} W{v['warmth']} M{v['morale']} | "
            f"{gear_txt} | W{inv['wood']} F{inv['food']} S{inv['stone']} Fb{inv['fiber']}"
            f"{action_txt}"
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


async def _eulogize_fallen():
    """Best-effort one-shot LLM epitaph for pawns that died this tick."""
    for entry in state.world_state["graveyard"]:
        if entry.get("died_tick") != state.world_state["tick"] or entry.get("eulogized"):
            continue
        try:
            text, _model_used = await asyncio.to_thread(
                llm.generate_with_fallback,
                prompts.EULOGY_PROMPT,
                f"{entry['name']} died of {entry['cause']} on Day {entry['died_tick']}.",
                None,
                0.9,
            )
            text = (text or "").strip()
            if text:
                entry["epitaph"] = text[:200]
        except Exception as e:
            print(f"❌ Eulogy failed for {entry['name']}: {e}")
        entry["eulogized"] = True


def _notify_extinction():
    """Roster empty: ping the god and pause so no more API is wasted."""
    if state.world_state.get("extinct"):
        return
    state.world_state["extinct"] = True
    print("🪦 Extinction detected — pausing simulation.")
    message = (
        "🪦 **The terrarium has fallen silent.** Every last pawn is gone. "
        f"<@{config.NOTIFY_USER_ID}>"
    )
    if DISCORD_WEBHOOK_URL:
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
        except requests.exceptions.RequestException as e:
            print(f"Extinction ping failed: {e}")
    pause_event.clear()


async def run_tick():
    async with tick_lock:
        print(f"🌱 Tick {state.world_state['tick']} starting...")

        if state.world_state["pawns"]:
            state.world_state["extinct"] = False
        else:
            _notify_extinction()
            state.world_state["tick"] += 1
            return

        try:
            TickResponse = schema.build_models()
        except ValueError as e:
            print(f"❌ Schema error: {e}")
            state.world_state["tick"] += 1
            return

        prompt = prompts.build_prompt()
        try:
            content, model_used = await asyncio.to_thread(
                llm.generate_with_fallback,
                prompts.SYSTEM_PROMPT,
                prompt,
                TickResponse,
                config.LLM_TEMPERATURE,
            )
            if not content:
                raise ValueError("LLM returned empty content")
            data = TickResponse.model_validate_json(content)
            print(f"🤖 Tick #{state.world_state['tick']} decided by {model_used}")
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
            if action == "Move":
                target = decision.direction
            order = state.god_orders.get(pid)
            if order:
                action, target = order["action"], order.get("target")
            intents[pid] = (action, target)

        engine.resolve_actions(intents)
        engine.tick_environment()
        await _eulogize_fallen()
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
