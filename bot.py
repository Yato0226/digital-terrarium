import asyncio

import discord
from discord.ext import commands

import core
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


def next_pawn_id():
    nums = [
        int(pid.split("_")[1])
        for pid in state.world_state["pawns"]
        if pid.startswith("pawn_")
    ]
    return f"pawn_{max(nums, default=0) + 1}"


def _pawn_line(pid, pawn):
    v = pawn["vitals"]
    title = f" {pawn['title']}" if pawn.get("title") else ""
    gear = f" | 🛠️ {pawn['gear']['main_hand'] or '—'}, {pawn['gear']['body'] or '—'}"
    break_txt = f" | 🌀 {pawn['mental_break']}" if pawn.get("mental_break") else ""
    return (
        f"**{pawn['name']}**{title} (`{pid}`): HP {v['hp']} | Energy {v['energy']} | "
        f"Hunger {v['hunger']} | Warmth {v['warmth']} | Morale {v['morale']} | "
        f"Wood {pawn['inventory']['wood']} | Food {pawn['inventory']['food']} | "
        f"Stone {pawn['inventory']['stone']} | Fiber {pawn['inventory']['fiber']}"
        f"{gear}{break_txt} | {pawn['status']}"
    )


@bot.command(name="add")
@is_god_channel()
async def add_pawn(ctx, name: str, hp: int = 100, energy: int = 80):
    """!add <name> [hp] [energy] — spawn a new pawn."""
    async with core.tick_lock:
        pawn_id = next_pawn_id()
        state.world_state["pawns"][pawn_id] = state.make_pawn(
            pawn_id,
            name,
            hp=max(0, min(100, hp)),
            energy=max(0, min(100, energy)),
        )
        state.save_state()
        await ctx.send(f"✨ Spawned **{name}** as `{pawn_id}` (HP {hp} | Energy {energy}).")


@bot.command(name="remove")
@is_god_channel()
async def remove_pawn(ctx, pawn_id: str):
    """!remove <pawn_id> — remove a pawn."""
    async with core.tick_lock:
        if pawn_id not in state.world_state["pawns"]:
            await ctx.send(f"❌ No pawn `{pawn_id}`.")
            return
        if len(state.world_state["pawns"]) <= 1:
            await ctx.send("❌ Can't remove the last pawn.")
            return
        name = state.world_state["pawns"].pop(pawn_id)["name"]
        state.save_state()
        await ctx.send(f"💀 Removed **{name}** (`{pawn_id}`).")


@bot.command(name="god")
@is_god_channel()
async def god_edit(ctx, pawn_id: str, stat: str, value: int = 50):
    """!god <pawn_id> <hp|energy|hunger|warmth|morale|wood|food|revive> [value]"""
    async with core.tick_lock:
        pawn = state.world_state["pawns"].get(pawn_id)
        if not pawn:
            await ctx.send(f"❌ No pawn `{pawn_id}`.")
            return
        key = stat.lower()
        if key == "revive":
            pawn["status"] = "active"
            pawn["vitals"]["hp"] = max(pawn["vitals"]["hp"], 1)
            state.save_state()
            await ctx.send(f"⚡ **{pawn['name']}** has been revived.")
            return
        if key in ("hp", "energy", "hunger", "warmth", "morale"):
            pawn["vitals"][key] = max(0, min(100, value))
        elif key in ("wood", "food", "stone", "fiber"):
            pawn["inventory"][key] = max(0, value)
        else:
            await ctx.send(
                "❌ Stat must be `hp`, `energy`, `hunger`, `warmth`, `morale`, "
                "`wood`, `food`, `stone`, `fiber`, or `revive`."
            )
            return
        state.save_state()
        await ctx.send(f"⚡ {pawn['name']} (`{pawn_id}`) {key} → {value}")


@bot.command(name="order")
@is_god_channel()
async def order(ctx, pawn_id: str, action: str, target: str = None):
    """!order <pawn_id> <Chop|Rest|Scout|Attack|Forage|Build|Share> [target]"""
    async with core.tick_lock:
        pawn = state.world_state["pawns"].get(pawn_id)
        if not pawn:
            await ctx.send(f"❌ No pawn `{pawn_id}`.")
            return
        action = action.capitalize()
        valid_actions = ("Chop", "Rest", "Scout", "Attack", "Forage", "Build", "Share", "Move")
        needs_target = ("Attack", "Share")
        if action not in valid_actions:
            await ctx.send(
                "❌ Action must be Chop, Rest, Scout, Attack, Forage, Build, Share, or Move."
            )
            return
        if action == "Move":
            if not target or target.upper() not in ("N", "S", "E", "W"):
                await ctx.send("❌ Move requires a direction: N, S, E, or W.")
                return
            target = target.upper()
        elif action in needs_target and (not target or target == pawn_id):
            await ctx.send("❌ Attacks and shares require a valid target (not self).")
            return
        elif action not in needs_target:
            target = None
        if target not in (None, "N", "S", "E", "W") and target not in state.world_state["pawns"]:
            await ctx.send(f"❌ No pawn `{target}`.")
            return
        state.god_orders[pawn_id] = {"action": action, "target": target}
        tgt = f" target **{target}**" if target else ""
        await ctx.send(f"🗣️ Order locked in: **{pawn['name']}** must {action}{tgt}.")


@bot.command(name="say")
@is_god_channel()
async def say(ctx, pawn_id: str, *, instruction: str):
    """!say <pawn_id> <instruction> — whisper flavor to a pawn."""
    async with core.tick_lock:
        if pawn_id not in state.world_state["pawns"]:
            await ctx.send(f"❌ No pawn `{pawn_id}`.")
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
