import asyncio
import random

import discord
from discord.ext import commands

import core
import engine
import state
from config import BOT_COMMAND_PREFIX, GOD_CHANNEL_NAME

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_COMMAND_PREFIX, intents=intents)

tick_task = None


def is_god_channel():
    def predicate(ctx):
        if GOD_CHANNEL_NAME is None:
            return True
        return getattr(ctx.channel, "name", None) == GOD_CHANNEL_NAME

    return commands.check(predicate)


def _random_name():
    used = {p["name"].lower() for p in state.world_state["pawns"].values()}
    for n in state.NAME_POOL:
        if n.lower() not in used:
            return n
    return f"Wanderer_{len(state.world_state['pawns']) + 1}"


def _random_job():
    return random.choice(state.JOB_POOL)


def _spawn_pawn(name, hp=100, energy=80):
    return state.make_pawn(
        state.next_pawn_id(),
        name,
        hp=hp,
        energy=energy,
        job=_random_job(),
    )


def resolve_pawn_id(s):
    """Match a pawn by `pawn_N` id or by display name (case-insensitive).

    Returns (pawn_id, None) on success or (None, error_message).
    """
    if s in state.world_state["pawns"]:
        return s, None
    hits = [
        pid
        for pid, p in state.world_state["pawns"].items()
        if p["name"].lower() == s.lower()
    ]
    if len(hits) == 1:
        return hits[0], None
    if len(hits) > 1:
        return None, f"several pawns share the name **{s}**; target one by id instead"
    return None, f"no pawn named `{s}`"


def _pawn_line(pid, pawn):
    v = pawn["vitals"]
    title = f" {pawn['title']}" if pawn.get("title") else ""
    job = f" the {pawn['job']}" if pawn.get("job") not in (None, "", "Wanderer") else ""
    sex = " ♂" if pawn.get("sex") == "M" else " ♀" if pawn.get("sex") == "F" else ""
    preg = " 🤰" if pawn.get("pregnant_ticks", 0) > 0 else ""
    child = " 👶" if pawn.get("child_ticks", 0) > 0 else ""
    gear = f" | 🛠️ {pawn['gear']['main_hand'] or '—'}, {pawn['gear']['body'] or '—'}"
    break_txt = f" | 🌀 {pawn['mental_break']}" if pawn.get("mental_break") else ""
    sk = pawn["skills"]
    x, y = pawn["pos"]
    tile = engine._tile_at(x, y) or "?"
    return (
        f"**{pawn['name']}**{sex}{job}{title}{preg}{child} (`{pid}`): "
        f"HP {v['hp']} | Energy {v['energy']} | "
        f"Hunger {v['hunger']} | Warmth {v['warmth']} | Morale {v['morale']} | "
        f"Wood {pawn['inventory']['wood']} | Food {pawn['inventory']['food']} | "
        f"Stone {pawn['inventory']['stone']} | Fiber {pawn['inventory']['fiber']}"
        f"{gear} | Skills W{sk['woodcutting']} S{sk['scouting']} C{sk['combat']}"
        f" | 📍 {tile} ({x},{y}){break_txt} | {pawn['status']}"
    )


@bot.command(name="add")
@is_god_channel()
async def add_pawn(ctx, name: str = None, hp: int = 100, energy: int = 80):
    """!add [name] [hp] [energy] — spawn a new pawn (name and job auto-generated if omitted)."""
    async with core.tick_lock:
        if name is None:
            name = _random_name()
        pawn = _spawn_pawn(name, hp=max(0, min(100, hp)), energy=max(0, min(100, energy)))
        state.world_state["pawns"][pawn["id"]] = pawn
        state.save_state()
        await ctx.send(
            f"✨ Spawned **{name}** {['♂', '♀'][pawn['sex'] == 'F']} "
            f"the {pawn['job']} (HP {hp} | Energy {energy})."
        )


@bot.command(name="job")
@is_god_channel()
async def set_job(ctx, pawn_id: str, job: str):
    """!job <name|pawn_id> <job> — set a pawn's job (flavor only)."""
    async with core.tick_lock:
        pawn_id, err = resolve_pawn_id(pawn_id)
        if err:
            await ctx.send(f"❌ {err}")
            return
        pawn = state.world_state["pawns"][pawn_id]
        pawn["job"] = job.strip().capitalize()
        state.save_state()
        await ctx.send(f"🛠️ **{pawn['name']}** is now the {pawn['job']}.")


@bot.command(name="rename")
@is_god_channel()
async def rename_pawn(ctx, pawn_id: str, new_name: str):
    """!rename <name|pawn_id> <newname> — rename a pawn."""
    async with core.tick_lock:
        pawn_id, err = resolve_pawn_id(pawn_id)
        if err:
            await ctx.send(f"❌ {err}")
            return
        pawn = state.world_state["pawns"][pawn_id]
        old = pawn["name"]
        pawn["name"] = new_name.strip()
        state.save_state()
        await ctx.send(f"📛 **{old}** is now **{pawn['name']}**.")


@bot.command(name="remove")
@is_god_channel()
async def remove_pawn(ctx, pawn_id: str):
    """!remove <name|pawn_id> — remove a pawn."""
    async with core.tick_lock:
        pawn_id, err = resolve_pawn_id(pawn_id)
        if err:
            await ctx.send(f"❌ {err}")
            return
        if len(state.world_state["pawns"]) <= 1:
            await ctx.send("❌ Can't remove the last pawn.")
            return
        name = state.world_state["pawns"].pop(pawn_id)["name"]
        state.save_state()
        await ctx.send(f"💀 Removed **{name}**.")


@bot.command(name="god")
@is_god_channel()
async def god_edit(ctx, pawn_id: str, stat: str, value: str = "50"):
    """!god <name|pawn_id> <hp|energy|hunger|warmth|morale|sex|wood|food|revive> [value]"""
    async with core.tick_lock:
        pawn_id, err = resolve_pawn_id(pawn_id)
        if err:
            await ctx.send(f"❌ {err}")
            return
        pawn = state.world_state["pawns"][pawn_id]
        key = stat.lower()
        if key == "revive":
            pawn["status"] = "active"
            pawn["vitals"]["hp"] = max(pawn["vitals"]["hp"], 1)
            state.save_state()
            await ctx.send(f"⚡ **{pawn['name']}** has been revived.")
            return
        if key == "sex":
            s = value.strip().upper()
            if s not in ("M", "F"):
                await ctx.send("❌ Sex must be M or F.")
                return
            pawn["sex"] = s
            state.save_state()
            await ctx.send(f"⚡ {pawn['name']} is now {'♂ male' if s == 'M' else '♀ female'}.")
            return
        try:
            value = int(value)
        except ValueError:
            await ctx.send("❌ Value must be a number (or M/F for sex).")
            return
        if key in ("hp", "energy", "hunger", "warmth", "morale"):
            pawn["vitals"][key] = max(0, min(100, value))
        elif key in ("wood", "food", "stone", "fiber"):
            pawn["inventory"][key] = max(0, value)
        else:
            await ctx.send(
                "❌ Stat must be `hp`, `energy`, `hunger`, `warmth`, `morale`, "
                "`sex`, `wood`, `food`, `stone`, `fiber`, or `revive`."
            )
            return
        state.save_state()
        await ctx.send(f"⚡ {pawn['name']} {key} → {value}")


@bot.command(name="order")
@is_god_channel()
async def order(ctx, pawn_id: str, action: str, target: str = None):
    """!order <name|pawn_id> <Chop|Rest|Scout|Attack|Forage|Build|Share|Move|Mate> [target]"""
    async with core.tick_lock:
        pawn_id, err = resolve_pawn_id(pawn_id)
        if err:
            await ctx.send(f"❌ {err}")
            return
        pawn = state.world_state["pawns"][pawn_id]
        action = action.capitalize()
        valid_actions = ("Chop", "Rest", "Scout", "Attack", "Forage", "Build", "Share", "Move", "Mate")
        needs_target = ("Attack", "Share", "Mate")
        if action not in valid_actions:
            await ctx.send(
                "❌ Action must be Chop, Rest, Scout, Attack, Forage, Build, Share, Move, or Mate."
            )
            return
        if action == "Move":
            if not target or target.upper() not in ("N", "S", "E", "W"):
                await ctx.send("❌ Move requires a direction: N, S, E, or W.")
                return
            target = target.upper()
        elif action in needs_target:
            if not target:
                await ctx.send("❌ Attacks, shares, and mates require a valid target (not self).")
                return
            target, t_err = resolve_pawn_id(target)
            if t_err:
                await ctx.send(f"❌ {t_err}")
                return
            if target == pawn_id:
                await ctx.send("❌ Can't target a pawn with itself.")
                return
        else:
            target = None
        state.god_orders[pawn_id] = {"action": action, "target": target}
        tgt = f" target **{target}**" if target else ""
        await ctx.send(f"🗣️ Order locked in: **{pawn['name']}** must {action}{tgt}.")


@bot.command(name="say")
@is_god_channel()
async def say(ctx, pawn_id: str, *, instruction: str):
    """!say <name|pawn_id> <instruction> — whisper flavor to a pawn."""
    async with core.tick_lock:
        pawn_id, err = resolve_pawn_id(pawn_id)
        if err:
            await ctx.send(f"❌ {err}")
            return
        state.god_whispers[pawn_id] = instruction
        pawn = state.world_state["pawns"][pawn_id]
        pawn["vitals"]["morale"] = max(0, min(100, pawn["vitals"]["morale"] + 15))
        name = pawn["name"]
        await ctx.send(f"🗣️ Whisper sent to **{name}** (+15 morale).")


@bot.command(name="graveyard")
@is_god_channel()
async def graveyard(ctx):
    """!graveyard — list the fallen and their epitaphs."""
    fallen = state.world_state["graveyard"]
    if not fallen:
        await ctx.send("🪦 The graveyard is empty — no one has fallen yet.")
        return
    lines = ["🪦 **The Graveyard**"]
    for entry in fallen:
        title = f" {entry['title']}" if entry.get("title") else ""
        survived = max(0, entry.get("died_tick", 0) - entry.get("born_tick", 0))
        lines.append(
            f"- **{entry['name']}**{title} — died of {entry['cause']} "
            f"on tick {entry.get('died_tick', '?')} (survived {survived} ticks)"
        )
        lines.append(f"  {entry.get('epitaph', '')}")
    await ctx.send("\n".join(lines))


@bot.command(name="list")
@is_god_channel()
async def list_pawns(ctx):
    """!list — list all pawns with full stats for easy targeting."""
    pawns = state.world_state["pawns"]
    if not pawns:
        await ctx.send("🪦 The terrarium is empty — spawn someone with `!add`.")
        return
    lines = [f"📜 **Pawns ({len(pawns)}):**"]
    for i, (pid, pawn) in enumerate(pawns.items(), 1):
        lines.append(f"{i}. {_pawn_line(pid, pawn)}")
    await ctx.send("\n".join(lines))


@bot.command(name="status")
@is_god_channel()
async def status(ctx):
    """!status — show the full current state."""
    biome = state.world_state["biome"]
    day_txt = "☀️ Day" if biome["day"] else "🌙 Night"
    lines = [
        f"🌿 **Terrarium** — Tick #{state.world_state['tick']}",
        f"🌍 {biome['season']}, {biome['weather']}, {day_txt} | "
        f"🔥 Campfire {biome['campfire']} | 🏠 Shelter {biome['shelter']} | "
        f"🌲 Wood {biome['wood_stock']} | 🍎 Food {biome['food_stock']}",
    ]
    for pid, pawn in state.world_state["pawns"].items():
        lines.append(f"- {_pawn_line(pid, pawn)}")
    if state.god_orders:
        pending = ", ".join(
            f"{pid} → {o['action']}" for pid, o in state.god_orders.items()
        )
        lines.append(f"**Pending orders:** {pending}")
    await ctx.send("\n".join(lines))


@bot.command(name="tick")
@is_god_channel()
async def force_tick(ctx):
    """!tick — force a tick immediately."""
    await ctx.send("⏩ Forcing a tick...")
    await core.run_tick()
    await ctx.send("✅ Tick complete.")


@bot.command(name="pause")
@is_god_channel()
async def pause(ctx):
    """!pause — halt the scheduler."""
    core.pause_event.clear()
    await ctx.send("⏸️ Terrarium paused.")


@bot.command(name="resume")
@is_god_channel()
async def resume(ctx):
    """!resume — resume the scheduler."""
    core.pause_event.set()
    await ctx.send("▶️ Terrarium resumed.")


@bot.event
async def on_ready():
    global tick_task
    print(f"🤖 Logged in as {bot.user}")
    print(f"📡 God channel: {GOD_CHANNEL_NAME or 'any channel'}")
    if tick_task is None or tick_task.done():
        tick_task = asyncio.create_task(core.tick_loop())
