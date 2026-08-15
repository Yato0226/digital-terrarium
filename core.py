import asyncio
import json

import requests

import config
import engine
import events
import map_renderer
import prompts
import schema
import state
from config import DISCORD_WEBHOOK_URL, TICK_INTERVAL_SECONDS

pause_event = asyncio.Event()
pause_event.set()

tick_lock = asyncio.Lock()

EMBED_CHAR_CAP = 6000  # Discord webhook embed total size limit

MAX_CHRONICLE = state.MAX_CHRONICLE  # seasonal chronicle cap (lives in state.py)

# Adoption notification hook: async callable(user_id: str, message: str), registered
# by bot.on_ready (webhooks can't DM). engine.py stays pure — no Discord logic.
notifier = None

# Event types that trigger an adoption DM for the adopted pawn.
ADOPTION_NOTIFY_TYPES = ("birth", "goal", "break", "death")


def _llm_call(system, user, schema_model, temperature):
    """Lazy llm import keeps core importable in the offline test suite."""
    import llm

    return llm.generate_with_fallback(system, user, schema_model, temperature)


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
                f"{_biome_infra_txt(biome)}"
                f"{_wildlife_txt()}"
                f"{_visitors_txt()}"
                "\n📋 HP=hit points · E=energy · H=hunger · W=warmth · M=morale · "
                "W=wood · F=food · S=stone · Fb=fiber · gear=main/body"
            )[:1024],
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
                if decision.action == "Interact" and getattr(decision, "flavor", None):
                    action_txt = f" | ✨ {decision.flavor}"
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
        elder_txt = " 👴" if engine.is_elder(pawn) else ""
        break_txt = f" 🌀{pawn['mental_break']}" if pawn.get("mental_break") else ""
        gear_txt = f" {pawn['gear']['main_hand'] or '—'}/{pawn['gear']['body'] or '—'}"
        traits_txt = (
            " " + " ".join(state.TRAIT_EMOJI.get(t, t) for t in pawn.get("traits", []))
            if pawn.get("traits")
            else ""
        )
        inv = pawn["inventory"]
        name = (
            f"🌲 {pawn['name']}{sex_txt}{job_txt}{title}{break_txt}{preg_txt}{child_txt}{elder_txt}{traits_txt} | "
            f"HP{v['hp']} E{v['energy']} H{v['hunger']} W{v['warmth']} M{v['morale']} | "
            f"{gear_txt} | W{inv['wood']} F{inv['food']} S{inv['stone']} Fb{inv['fiber']}"
            f"{action_txt}"
        )
        fields.append({"name": name[:256], "value": value[:1024], "inline": False})

    footer_text = " → ".join(
        ev["description"] for ev in state.world_state["history"][-3:]
    )
    embed = {
        "title": f"🌿 Terrarium Tick #{state.world_state['tick']}",
        "description": data.world_event,
        "fields": fields[:25],
        "footer": {"text": footer_text},
    }
    if len(json.dumps(embed, ensure_ascii=False)) > EMBED_CHAR_CAP:
        embed["footer"] = {"text": footer_text[:200]}
        if len(json.dumps(embed, ensure_ascii=False)) > EMBED_CHAR_CAP:
            del embed["footer"]
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        png = map_renderer.render_png()
        embed["image"] = {"url": "attachment://map.png"}
        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            data={"payload_json": json.dumps({"embeds": [embed]}, ensure_ascii=False)},
            files={"file": ("map.png", png, "image/png")},
            timeout=5,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Discord post failed: {e}")
    except Exception as e:
        print(f"Map render failed (falling back to ASCII grid): {e}")
        embed.pop("image", None)
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e2:
            print(f"Discord post failed: {e2}")


def _biome_infra_txt(biome):
    parts = []
    if biome.get("granary"):
        parts.append(" | 🏛️ Granary")
    if biome.get("palisade", 0):
        parts.append(f" | 🛡️ Palisade {biome['palisade']}")
    monument = state.world_state.setdefault(
        "monument", {"wood": 0, "stone": 0, "done": False, "inscription": None}
    )
    if monument.get("done"):
        parts.append(" | 🗿 Monolith")
    return "".join(parts)


def _wildlife_txt():
    wildlife = state.world_state["wildlife"]
    if not wildlife:
        return ""
    parts = []
    for w in wildlife:
        spec = engine.WILDLIFE[w["species"]]
        if w["state"] == "tamed":
            parts.append(f"{spec['emoji']} {w['species']} (pet)")
        else:
            parts.append(f"{spec['emoji']} {w['species']} @{w['pos']}")
    return "\n🐾 " + " | ".join(parts)


def _visitors_txt():
    visitors = state.world_state.get("visitors", [])
    if not visitors:
        return ""
    parts = []
    for v in visitors:
        parts.append(
            f"{engine.VISITOR_TYPES[v['kind']]['emoji']} {v['name']} "
            f"({v['kind']}, {v['state']})"
        )
    return "\n🚶 " + " | ".join(parts)


async def _eulogize_fallen(dead_tick):
    """Best-effort one-shot LLM epitaph for pawns that died this tick."""
    for entry in state.world_state["graveyard"]:
        if entry.get("died_tick") != dead_tick or entry.get("eulogized"):
            continue
        try:
            text, _model_used = await asyncio.to_thread(
                _llm_call,
                prompts.EULOGY_PROMPT,
                f"{entry['name']} died of {entry['cause']} on Day {entry['died_tick'] // engine.TICKS_PER_DAY}.",
                None,
                0.9,
            )
            text = (text or "").strip()
            if text:
                entry["epitaph"] = text[:200]
        except Exception as e:
            print(f"❌ Eulogy failed for {entry['name']}: {e}")
        entry["eulogized"] = True


def _chronicle_context(season):
    """Compact context for the seasonal-chronicle LLM call."""
    biome = state.world_state["biome"]
    names = ", ".join(
        p["name"] for p in state.world_state["pawns"].values()
    ) or "no one"
    fallen = len(state.world_state["graveyard"])
    history = events.history_to_text()
    return (
        f"The season has turned to {season}. "
        f"The colony is {names}. {fallen} lie in the graveyard. "
        f"Campfire {biome['campfire']}, shelter {biome['shelter']}, "
        f"wood {biome['wood_stock']}, food {biome['food_stock']}. "
        f"Recent events: {history}"
    )


def _parse_chronicle(text, season):
    """Split the LLM chronicle response into (title, body)."""
    text = (text or "").strip()
    if not text:
        return f"The {season} of Quiet", "The colony endures the turning of the season."
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) == 1:
        return lines[0][:60], lines[0][:1200]
    title = lines[0].rstrip(".").strip()[:60] or f"The {season} of Quiet"
    body = " ".join(lines[1:])[:1500]
    return title, body


async def _chronicle_season(season):
    """Best-effort outside-lock LLM chronicle for a season that just began."""
    try:
        text, _model_used = await asyncio.to_thread(
            _llm_call,
            prompts.CHRONICLE_PROMPT,
            _chronicle_context(season),
            None,
            0.9,
        )
        title, body = _parse_chronicle(text, season)
    except Exception as e:
        print(f"❌ Chronicle failed for {season}: {e}")
        title, body = f"The {season} of Quiet", "The colony endures the turning of the season."
    entry = {"season": season, "title": title, "text": body, "tick": state.world_state["tick"]}
    state.world_state["chronicle"].append(entry)
    if len(state.world_state["chronicle"]) > MAX_CHRONICLE:
        state.world_state["chronicle"] = state.world_state["chronicle"][-MAX_CHRONICLE:]
    events.add_event(
        "chronicle",
        data={"season": season, "title": title},
        description=f"The chronicle records a new era: {title}.",
    )
    state.save_state()


def _monument_context():
    """Compact context for the monument-inscription LLM call."""
    names = ", ".join(
        p["name"] for p in state.world_state["pawns"].values()
    ) or "no one"
    fallen = len(state.world_state["graveyard"])
    history = events.history_to_text()
    return (
        f"The colony of {names} has just completed the Ancestral Monolith on "
        f"Tick {state.world_state['tick']}. {fallen} lie in the graveyard. "
        f"Recent events: {history}"
    )


async def _inscribe_monument():
    """Best-effort outside-lock LLM dedication for a freshly completed monolith."""
    monument = state.world_state.setdefault(
        "monument", {"wood": 0, "stone": 0, "done": False, "inscription": None}
    )
    inscription = None
    try:
        text, _model_used = await asyncio.to_thread(
            _llm_call,
            prompts.MONUMENT_PROMPT,
            _monument_context(),
            None,
            0.8,
        )
        text = (text or "").strip().strip('"').strip()
        if text:
            inscription = text.splitlines()[0][:120]
    except Exception as e:
        print(f"❌ Monument inscription failed: {e}")
    if inscription:
        monument["inscription"] = inscription
        events.add_event(
            "monument",
            data={"inscription": inscription},
            description=f"The monolith bears the dedication: \"{inscription}\"",
        )
        state.save_state()


def _adoption_message(etype, name, description):
    label = {
        "birth": "gave birth",
        "goal": "fulfilled a personal goal",
        "break": "is having a mental break",
        "death": "has died",
    }.get(etype, etype)
    return f"🐾 **{name}** {label}: {description}"


async def _notify_adopted(tick_events):
    """DM the owner of each adopted pawn that hit a milestone this tick."""
    if notifier is None or not state.world_state["adoptions"]:
        return
    by_pawn = {pid: uid for uid, pid in state.world_state["adoptions"].items()}
    for ev in tick_events:
        etype = ev.get("type")
        if etype not in ADOPTION_NOTIFY_TYPES:
            continue
        pid = ev.get("actor") or ev.get("target")
        uid = by_pawn.get(pid)
        if uid is None:
            continue
        pawn = engine._pawn_by_id(pid)
        name = pawn["name"] if pawn else pid
        try:
            await notifier(uid, _adoption_message(etype, name, ev.get("description", "")))
        except Exception as e:
            print(f"❌ Adoption DM failed for {uid}: {e}")


def _notify_extinction():
    """Roster empty: ping the god once and pause so no more API is wasted."""
    if not state.world_state.get("extinct"):
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
            if not state.world_state.get("extinct"):
                state.world_state["tick"] += 1
            _notify_extinction()
            state.save_state()
            return

        try:
            TickResponse = schema.build_models()
        except ValueError as e:
            print(f"❌ Schema error: {e}")
            state.world_state["tick"] += 1
            state.save_state()
            return

        prompt = prompts.build_prompt()
        try:
            content, model_used = await asyncio.to_thread(
                _llm_call,
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
            state.save_state()
            return

        events.add_event("world", description=data.world_event)
        dead_tick = state.world_state["tick"]

        # Build intents; god orders override the LLM's proposal.
        intents = {}
        for pid, pawn in state.world_state["pawns"].items():
            if pawn["status"] != "active":
                continue
            decision = getattr(data, pid)
            action, target = decision.action, decision.target
            flavor = getattr(decision, "flavor", None) if action == "Interact" else None
            new_goal = getattr(decision, "new_goal", None)
            if action == "Move":
                target = decision.direction
            order = state.god_orders.get(pid)
            if order:
                action, target = order["action"], order.get("target")
                if action == "Interact":
                    flavor = order.get("flavor") or flavor
            intents[pid] = (action, target, flavor, new_goal)

        tick_events = engine.resolve_actions(intents)
        tick_events += engine.tick_environment()
        state.god_orders.clear()
        state.god_whispers.clear()
        state.world_state["tick"] += 1
        state.save_state()
        print(f"✅ Tick complete. {state.status_summary()}")

    # Lock released: god commands can run during the slow LLM/webhook I/O.
    pending_season = state.pending_chronicle
    state.pending_chronicle = None
    if pending_season:
        await _chronicle_season(pending_season)
    pending_monument = state.pending_monument
    state.pending_monument = None
    if pending_monument:
        await _inscribe_monument()
    await _eulogize_fallen(dead_tick)
    await _notify_adopted(tick_events)
    state.save_state()
    await asyncio.to_thread(post_to_discord, data)


async def tick_loop():
    while True:
        await pause_event.wait()
        await run_tick()
        for _ in range(TICK_INTERVAL_SECONDS):
            await asyncio.sleep(1)
            if not pause_event.is_set():
                break
