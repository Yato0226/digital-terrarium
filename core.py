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

# Milestone webhook posts can be disabled (tests set this False alongside
# events.LOGGING so a real .env webhook can't fire during the suite).
POSTING_ENABLED = True

# Event types that mark a tick as high-impact: the full state embed (map +
# pawn dossier) is only posted on ticks that produced at least one of these.
MILESTONE_EVENT_TYPES = (
    "season", "death", "birth", "feast", "tradition", "monument_complete",
    "quest_complete", "rune", "raid", "fire_start", "fire_damage", "flood", "miasma",
)

# Event types that fire a standalone Breaking Crisis Alert embed.
CRISIS_EVENT_TYPES = ("raid", "fire_start", "fire_damage", "flood", "miasma")


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
                f"{_raiders_txt()}"
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


def post_patch_notes(record):
    """Standalone 'Terrarium Patch Notes' embed to Discord after an Architect review."""
    if not DISCORD_WEBHOOK_URL:
        return
    notes = record.get("notes") or []
    fields = []
    if notes:
        fields.append(
            {
                "name": "Adjustments",
                "value": "• " + "\n• ".join(notes)[:1024],
                "inline": False,
            }
        )
    if record.get("text"):
        fields.append(
            {"name": "Balance notes", "value": record["text"][:1024], "inline": False}
        )
    mods = record.get("modifiers") or {}
    footer = ", ".join(f"{k}={v:.2f}" for k, v in mods.items())
    embed = {
        "title": f"⚙️ Terrarium Patch Notes {record.get('version')}",
        "description": record.get("title") or "The Architect adjusts the world.",
        "fields": fields,
        "footer": {"text": f"Tick {record.get('tick')} — modifiers: {footer}"},
    }
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Patch-notes post failed: {e}")


def _post_embed(embed):
    """Best-effort standalone embed post (single choke point; no-op when off)."""
    if not POSTING_ENABLED or not DISCORD_WEBHOOK_URL:
        return
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Discord post failed: {e}")


def _is_milestone_tick(tick_events):
    """True when any event this tick counts as a high-impact milestone."""
    return any(ev.get("type") in MILESTONE_EVENT_TYPES for ev in tick_events)


def post_chronicle(entry):
    """Season Change & Era Chronicle milestone: the lorekeeper's title + paragraph."""
    names = ", ".join(
        p["name"] for p in state.world_state["pawns"].values()
    ) or "no one"
    embed = {
        "title": f"📜 New Era: {entry['title']}",
        "description": entry["text"][:2048],
        "color": 0xD4AF37,
        "fields": [
            {"name": "Season", "value": entry["season"], "inline": True},
            {"name": "Colony", "value": names[:256], "inline": True},
        ],
        "footer": {"text": f"Tick {entry['tick']}"},
    }
    _post_embed(embed)


def post_eulogy(entry):
    """Fallen Heroes milestone: tombstone inscription and cause of death."""
    day = entry["died_tick"] // engine.TICKS_PER_DAY
    embed = {
        "title": f"🪦 {entry['name']} has fallen",
        "description": entry.get("epitaph") or "Gone, but not forgotten.",
        "color": 0x2C2F33,
        "fields": [
            {"name": "Cause", "value": entry.get("cause", "unknown")[:256], "inline": True},
            {"name": "Day", "value": f"{day} (tick {entry['died_tick']})", "inline": True},
        ],
    }
    _post_embed(embed)


def post_crisis(tick_events):
    """Breaking Crisis Alerts: raids, fires reaching the colony, floods, miasma."""
    titles = {
        "raid": "🥷 Scavenger Raid!",
        "fire_start": "🔥 Wildfire!",
        "fire_damage": "🔥 Flames reach the colony!",
        "flood": "🌊 Flash Flood!",
        "miasma": "☠️ Toxic Miasma!",
    }
    for ev in tick_events:
        etype = ev.get("type")
        if etype not in CRISIS_EVENT_TYPES:
            continue
        embed = {
            "title": titles.get(etype, "⚠️ Crisis!"),
            "description": (ev.get("description") or "")[:1024],
            "color": 0xFF4444,
            "footer": {"text": f"Tick {ev.get('tick', state.world_state['tick'])}"},
        }
        _post_embed(embed)


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
    tradition = state.world_state.setdefault("traditions", {}).get("tag")
    if tradition:
        parts.append(f" | 🏛️ {tradition}")
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


def _raiders_txt():
    raiders = state.world_state.get("raiders", [])
    if not raiders:
        return ""
    parts = []
    for r in raiders:
        parts.append(
            f"🥷 {r['name']} ({r['state']}"
            + (f", {r['stolen']} stolen" if r["stolen"] else "")
            + ")"
        )
    return "\n⚠️ " + " | ".join(parts)


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
        post_eulogy(entry)


BIO_EVENT_LIMIT = 40  # most recent life events fed to the biography LLM


def _read_log(max_lines=500):
    """Read the tail of the append-only event log as a list of event dicts."""
    try:
        with open(state.LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    out = []
    for line in lines[-max_lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _pawn_events(pawn_id, name, limit=BIO_EVENT_LIMIT):
    """Life events mentioning a pawn (as actor, target, or by name)."""
    name_low = name.lower()
    matched = [
        ev
        for ev in _read_log()
        if ev.get("actor") == pawn_id
        or ev.get("target") == pawn_id
        or name_low in (ev.get("description") or "").lower()
    ]
    return matched[-limit:]


def _bio_context(pawn):
    """Raw life story for the biography LLM: identity, family, and life events."""
    pid = pawn["id"]
    name = pawn["name"]
    lines = []
    living = pid in state.world_state["pawns"]
    if living:
        p = state.world_state["pawns"][pid]
        role = f" the {p['job']}" if p.get("job") not in (None, "", "Wanderer") else ""
        title = f", title \"{p['title']}\"" if p.get("title") else ""
        lines.append(
            f"Name: {name} ({pid}) — {p['sex']}{role}{title}, "
            f"Day {engine.age_of(p) // engine.TICKS_PER_DAY} of life"
        )
        sk = p["skills"]
        lines.append(
            f"Skills: woodcutting {sk['woodcutting']}, scouting {sk['scouting']}, combat {sk['combat']}"
        )
        if p.get("traits"):
            lines.append(f"Traits: {', '.join(p['traits'])}")
        partners = [
            q["name"] for qid in p.get("partners", []) if (q := engine._pawn_by_id(qid))
        ]
        if partners:
            lines.append(f"Partners: {', '.join(partners)}")
        kin = engine.lineage_label(p)
        if kin:
            lines.append(kin.capitalize())
        owned = [h["name"] for h in state.world_state["heirlooms"] if h.get("owner") == pid]
        if owned:
            lines.append(f"Carries the heirlooms: {', '.join(owned)}")
        goal = p.get("goal")
        if goal:
            lines.append(f"Current goal: {goal.get('text')} ({goal.get('progress')}/{goal.get('needed')})")
    else:
        title = f", title \"{pawn.get('title')}\"" if pawn.get("title") else ""
        lines.append(
            f"Name: {name} ({pid}) — the fallen{title}, died of {pawn.get('cause')} "
            f"on Day {pawn.get('died_tick', 0) // engine.TICKS_PER_DAY} "
            f"(born Day {pawn.get('born_tick', 0) // engine.TICKS_PER_DAY})"
        )
        if pawn.get("beloved"):
            lines.append("The colony held them dear.")
        if pawn.get("epitaph"):
            lines.append(f"Tombstone: \"{pawn['epitaph']}\"")
        legacy = [
            h["name"]
            for h in state.world_state["heirlooms"]
            if h.get("name", "").startswith(name + "'s")
        ]
        if legacy:
            lines.append(f"Left behind the heirloom: {', '.join(legacy)}")
        children = [
            q["name"]
            for q in state.world_state["pawns"].values()
            if pid in (q.get("mother_id"), q.get("father_id"))
        ]
        if children:
            lines.append(f"Surviving children: {', '.join(children)}")

    events_txt = _pawn_events(pid, name)
    if events_txt:
        lines.append("Life events:")
        for ev in events_txt:
            lines.append(f"- Tick {ev['tick']} ({ev['type']}): {ev.get('description') or ev['type']}")
    else:
        lines.append("Life events: none recorded.")
    return "\n".join(lines)


def _fallback_bio(pawn):
    """Deterministic obituary when the LLM is unavailable."""
    name = pawn["name"]
    if pawn.get("died_tick"):
        return (
            f"{name} lived from Day {pawn.get('born_tick', 0) // engine.TICKS_PER_DAY} "
            f"to Day {pawn.get('died_tick', 0) // engine.TICKS_PER_DAY} and was taken by "
            f"{pawn.get('cause', 'the wild')}. They rest in the graveyard, remembered."
        )
    return f"{name} walks among the living, still writing their story."


async def compose_bio(pawn_id):
    """Best-effort on-demand LLM biography/obituary for a living pawn or tombstone."""
    pawn = engine._pawn_by_id(pawn_id)
    if pawn is None:
        return None
    try:
        text, _model_used = await asyncio.to_thread(
            _llm_call,
            prompts.BIO_PROMPT,
            _bio_context(pawn),
            None,
            0.9,
        )
        text = (text or "").strip()
    except Exception as e:
        print(f"❌ Bio failed for {pawn_id}: {e}")
        text = ""
    return text or _fallback_bio(pawn)


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
    post_chronicle(entry)


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


def _patch_context():
    """Compact context for the Architect's annual balance review."""
    biome = state.world_state["biome"]
    mods = biome.get("modifiers") or {}
    names = ", ".join(
        p["name"] for p in state.world_state["pawns"].values()
    ) or "no one"
    history = events.history_to_text()
    recipes = ", ".join(sorted(state.world_state.get("custom_recipes", {}))) or "the three basic tools"
    quests = state.world_state.get("active_quests", [])
    quest_txt = (
        ", ".join(
            f"{q.get('title')} ({q.get('progress', 0)}/{q.get('needed')})" for q in quests
        )
        or "none"
    )
    return (
        f"The terrarium is at patch version {state.world_state.get('patch_version', 'v1.0')}. "
        f"The colony of {names} has reached Tick {state.world_state['tick']} "
        f"(Day {state.world_state['tick'] // engine.TICKS_PER_DAY}). "
        f"Season {biome['season']}, weather {biome['weather']}. "
        f"Campfire {biome['campfire']}, shelter {biome['shelter']}, "
        f"wood {biome['wood_stock']}, food {biome['food_stock']}, "
        f"granary {biome.get('granary')}, palisade {biome.get('palisade', 0)}. "
        f"Balance modifiers: regrowth {mods.get('regrowth', 1.0)}, "
        f"cold {mods.get('cold', 1.0)}, spawn {mods.get('spawn', 1.0)}. "
        f"Known blueprints: {recipes}. "
        f"Active prophecies: {quest_txt}. "
        f"Recent events: {history}"
    )


async def _run_architect():
    """Annual Architect review: bounded tuning + optional blueprint/prophecy.

    Runs outside the tick lock like the chronicle. Emits a 'patch' event,
    bumps patch_version, persists, and returns the patch record for Discord.
    """
    PatchModel = schema.build_patch_model()
    try:
        content, _model_used = await asyncio.to_thread(
            _llm_call,
            prompts.ARCHITECT_PROMPT,
            _patch_context(),
            PatchModel,
            config.ARCHITECT_TEMPERATURE,
        )
        if not content:
            raise ValueError("Architect returned empty content")
        patch = PatchModel.model_validate_json(content)
    except Exception as e:
        print(f"❌ Architect review failed: {e}")
        return None

    old, new = engine.apply_patch(
        {
            "regrowth": getattr(patch, "regrowth_delta", 0.0) or 0.0,
            "cold": getattr(patch, "cold_delta", 0.0) or 0.0,
            "spawn": getattr(patch, "spawn_delta", 0.0) or 0.0,
        }
    )
    notes = []
    for key in ("regrowth", "cold", "spawn"):
        if new[key] != old[key]:
            notes.append(f"{key}: {old[key]:.2f} → {new[key]:.2f}")

    recipe = engine.validate_new_recipe(getattr(patch, "new_recipe", None))
    if recipe:
        recipes = state.world_state.setdefault("custom_recipes", {})
        if len(recipes) >= engine.CUSTOM_RECIPE_LIMIT:
            recipe = None
        else:
            recipes[recipe["name"]] = recipe
            notes.append(f"new blueprint: {recipe['name']}")

    quest = engine.validate_new_quest(getattr(patch, "new_quest", None))
    if quest:
        if len(state.world_state.get("active_quests", [])) >= engine.QUEST_MAX:
            quest = None
        else:
            state.world_state.setdefault("active_quests", []).append(quest)
            notes.append(f"new prophecy: {quest['title']}")

    version = engine.bump_patch_version()
    record = {
        "version": version,
        "title": (getattr(patch, "patch_title", "") or "").strip()[:120],
        "text": (getattr(patch, "balance_changes", "") or "").strip()[:800],
        "notes": notes,
        "modifiers": new,
        "tick": state.world_state["tick"],
    }
    events.add_event(
        "patch",
        data={"version": version, "notes": notes},
        description=(
            f"⚙️ Patch {version}: {record['title'] or 'balance pass'}"
            + (" — " + "; ".join(notes) if notes else "")
        ),
    )
    patches = state.world_state.setdefault("patches", [])
    patches.append(record)
    if len(patches) > state.MAX_PATCHES:
        state.world_state["patches"] = patches[-state.MAX_PATCHES:]
    state.save_state()
    return record


def _resolve_leader(name):
    """Resolve a council-nominated leader name to a living active pawn id."""
    name = (name or "").strip().lower()
    for pid, p in state.world_state["pawns"].items():
        if p["status"] == "active" and p["name"].lower() == name:
            return pid
    return None


def _council_context():
    """Compact review of the past year for the Camp Council LLM."""
    biome = state.world_state["biome"]
    names = ", ".join(
        p["name"] for p in state.world_state["pawns"].values()
    ) or "no one"
    history = events.history_to_text()
    trad = state.world_state.get("traditions", {})
    tag = trad.get("tag")
    tag_txt = f" The colony's tradition tag is {tag}." if tag else ""
    fallen = len(state.world_state["graveyard"])
    monument = state.world_state.get("monument", {})
    mon_txt = " The Ancestral Monolith stands complete." if monument.get("done") else ""
    return (
        f"The colony of {names} has survived to Day "
        f"{state.world_state['tick'] // engine.TICKS_PER_DAY} in {biome['season']} "
        f"({biome['weather']}). {fallen} colonists have been lost and laid to rest. "
        f"Counters: {trad.get('predators_slain', 0)} predators slain, "
        f"{trad.get('trees_felled', 0)} trees felled, "
        f"{trad.get('rations_shared', 0)} rations shared.{tag_txt}{mon_txt} "
        f"Recent events: {history}"
    )


async def _run_council():
    """Annual Camp Council: names a leader and issues a Colony Mandate.

    Runs outside the tick lock like the chronicle and Architect. Emits a
    'council' event and persists the new council record for Discord/prompt.
    """
    CouncilModel = schema.build_council_model()
    try:
        content, _model_used = await asyncio.to_thread(
            _llm_call,
            prompts.COUNCIL_PROMPT,
            _council_context(),
            CouncilModel,
            config.COUNCIL_TEMPERATURE,
        )
        if not content:
            raise ValueError("Council returned empty content")
        decision = CouncilModel.model_validate_json(content)
    except Exception as e:
        print(f"❌ Camp Council failed: {e}")
        return None
    leader_pid = _resolve_leader(getattr(decision, "leader", ""))
    record = engine.apply_council(leader_pid, getattr(decision, "mandate", ""))
    if record is None:
        print("❌ Camp Council: could not seat a leader (unknown name or invalid mandate).")
        return None
    state.save_state()
    return record


def council_txt():
    """The current council, leader, and Colony Mandate, for `!council`."""
    council = state.world_state.get("council")
    if not council or not council.get("leader_name"):
        return "🏛️ No council has been held yet — the colony has no recognized leader or mandate."
    lines = [
        f"🏛️ **Council** (Day {council.get('day', '?')}):",
        f"- Leader: **{council['leader_name']}**",
        f"- Colony Mandate: “{council.get('mandate', '')}”",
    ]
    return "\n".join(lines)


def legends_txt():
    """The legend archive and which beast currently stalks, for `!legends`."""
    legends = state.world_state.get("legends", [])
    if not legends:
        return "👑 No legendary beasts yet — no predator has survived mauling enough colonists."
    living = {w["id"] for w in state.world_state["wildlife"]}
    lines = ["👑 **Legendary beasts:**"]
    for lg in legends:
        active = not lg.get("slain") and lg.get("wild_id") in living
        if lg.get("slain"):
            status = f"slain (Day {lg.get('slain_tick', 0) // engine.TICKS_PER_DAY})"
        elif active:
            status = "stalking the colony NOW"
        else:
            status = f"escaped {lg.get('escapes', 0)}× — may return"
        lines.append(
            f"- **{lg['name']}** — {lg['species']}, fame {lg.get('fame', 1)} ({status})"
        )
    return "\n".join(lines)


def recipes_txt():
    """All known blueprints (base + synthesized), for `!recipes`."""
    recipes = engine._all_recipes()
    lines = ["🛠️ **Blueprints:**"]
    for name in sorted(recipes, key=lambda n: (recipes[n]["tier"], n)):
        r = recipes[name]
        mats = ", ".join(f"{k}×{v}" for k, v in sorted(r["materials"].items()))
        slot = r["slot"]
        custom = state.world_state.get("custom_recipes", {}).get(name)
        bonus_txt = ""
        if custom and custom.get("bonus"):
            bonus = ", ".join(f"+{v} {k}" for k, v in sorted(custom["bonus"].items()))
            bonus_txt = f" — {bonus}"
        lines.append(
            f"- **{name}** (tier {r['tier']}, {slot}): {mats}{bonus_txt}"
        )
    return "\n".join(lines)


def quests_txt():
    """Active world objectives with progress, for `!quests` / `!prophecies`."""
    quests = state.world_state.get("active_quests", [])
    if not quests:
        return "🌠 No prophecies are stirring — the world waits."
    lines = ["🌠 **Prophecies:**"]
    for q in quests:
        kind = q.get("kind", "?")
        detail = ""
        if kind == "hunt":
            detail = f" slay {q.get('species')}"
        elif kind == "stockpile":
            detail = f" stockpile {q.get('resource')}"
        elif kind == "survive":
            detail = " survive"
        elif kind == "chop":
            detail = " chop"
        title = q.get("title", "The Unwritten Prophecy")
        morale = q.get("reward_morale", 0)
        title_txt = f" **{title}** —" if title else ""
        lines.append(
            f"- {title_txt}{detail} {q.get('progress', 0)}/{q.get('needed')} "
            f"(+{morale} morale"
            + (f", title {q.get('reward_title')}" if q.get("reward_title") else "")
            + ")"
        )
    return "\n".join(lines)


def patchnotes_txt():
    """Latest Architect patch records, for `!patchnotes`."""
    patches = state.world_state.get("patches", [])
    if not patches:
        return "⚙️ No patches yet — the Architect reviews the world every 400 ticks."
    lines = ["⚙️ **Terrarium Patch Notes**"]
    for p in patches[-3:]:
        lines.append(f"**{p.get('version')}** — {p.get('title') or 'balance pass'} (tick {p.get('tick')})")
        if p.get("notes"):
            lines.append("• " + "\n• ".join(p["notes"]))
        if p.get("text"):
            lines.append(f"> {p['text'][:300]}")
    return "\n".join(lines)


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
            new_title = getattr(decision, "new_title", None)
            if action == "Move":
                target = decision.direction
            order = state.god_orders.get(pid)
            if order:
                action, target = order["action"], order.get("target")
                if action == "Interact":
                    flavor = order.get("flavor") or flavor
            intents[pid] = (action, target, flavor, new_goal, new_title)

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
    patch_record = None
    if dead_tick % engine.PATCH_INTERVAL == 0:
        patch_record = await _run_architect()
    council_record = None
    if dead_tick % engine.COUNCIL_INTERVAL == 0:
        council_record = await _run_council()
    state.save_state()
    milestone = (
        _is_milestone_tick(tick_events)
        or bool(pending_season)
        or bool(pending_monument)
        or bool(patch_record)
        or bool(council_record)
    )
    if milestone:
        await asyncio.to_thread(post_to_discord, data)
    await asyncio.to_thread(post_crisis, tick_events)
    if patch_record:
        await asyncio.to_thread(post_patch_notes, patch_record)


async def tick_loop():
    while True:
        await pause_event.wait()
        await run_tick()
        for _ in range(TICK_INTERVAL_SECONDS):
            await asyncio.sleep(1)
            if not pause_event.is_set():
                break
