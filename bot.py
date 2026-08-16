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


def resolve_animal_id(s):
    """Match a wildlife entity by `wild_N` id or by species name (case-insensitive)."""
    wildlife = state.world_state["wildlife"]
    if any(w["id"] == s for w in wildlife):
        return s, None
    hits = [w["id"] for w in wildlife if w["species"].lower() == s.lower()]
    if len(hits) == 1:
        return hits[0], None
    if len(hits) > 1:
        return None, f"several **{s}**s are around; target one by id instead"
    return None, f"no animal named `{s}` is around right now"


def _pawn_line(pid, pawn):
    v = pawn["vitals"]
    title = f" {pawn['title']}" if pawn.get("title") else ""
    job = f" the {pawn['job']}" if pawn.get("job") not in (None, "", "Wanderer") else ""
    sex = " ♂" if pawn.get("sex") == "M" else " ♀" if pawn.get("sex") == "F" else ""
    preg = " 🤰" if pawn.get("pregnant_ticks", 0) > 0 else ""
    child = " 👶" if pawn.get("child_ticks", 0) > 0 else ""
    elder = " 👴" if engine.is_elder(pawn) else ""
    traits = (
        " " + " ".join(state.TRAIT_EMOJI.get(t, t) for t in pawn["traits"])
        if pawn.get("traits")
        else ""
    )
    mood_txt = ""
    if pawn.get("moodlets"):
        moods = ", ".join(
            f"{m['name']} ({m['delta']:+d})" for m in pawn["moodlets"]
        )
        mood_txt = f" | 😔 {moods}"
    age = f" | {engine.age_of(pawn) // engine.TICKS_PER_DAY} days old"
    kin = engine.lineage_label(pawn)
    kin_txt = f" | {kin}" if kin else ""
    gear = f" | 🛠️ {pawn['gear']['main_hand'] or '—'}, {pawn['gear']['body'] or '—'}"
    break_txt = f" | 🌀 {pawn['mental_break']}" if pawn.get("mental_break") else ""
    goal_txt = ""
    g = pawn.get("goal")
    if g:
        goal_txt = f" | 🎯 {g['text']} ({g['progress']}/{g['needed']})"
    sk = pawn["skills"]
    x, y = pawn["pos"]
    tile = engine._tile_at(x, y) or "?"
    heirlooms = [
        h["name"] for h in state.world_state["heirlooms"] if h.get("owner") == pid
    ]
    heir_txt = f" | 🏆 {', '.join(heirlooms)}" if heirlooms else ""
    return (
        f"**{pawn['name']}**{sex}{job}{title}{preg}{child}{elder}{traits} (`{pid}`): "
        f"HP {v['hp']} | Energy {v['energy']} | "
        f"Hunger {v['hunger']} | Warmth {v['warmth']} | Morale {v['morale']} | "
        f"Wood {pawn['inventory']['wood']} | Food {pawn['inventory']['food']} | "
        f"Stone {pawn['inventory']['stone']} | Fiber {pawn['inventory']['fiber']}"
        f"{gear} | Skills W{sk['woodcutting']} S{sk['scouting']} C{sk['combat']}"
        f"{age} | 📍 {tile} ({x},{y}){kin_txt}{break_txt}{goal_txt}{mood_txt}{heir_txt} | {pawn['status']}"
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
    """!order <name|pawn_id> <Chop|Rest|Scout|Attack|Forage|Build|Share|Move|Mate|Interact> [target|verb]"""
    async with core.tick_lock:
        pawn_id, err = resolve_pawn_id(pawn_id)
        if err:
            await ctx.send(f"❌ {err}")
            return
        pawn = state.world_state["pawns"][pawn_id]
        action = action.capitalize()
        valid_actions = engine.ACTIONS
        needs_target = ("Attack", "Share", "Mate")
        if action not in valid_actions:
            await ctx.send(
                "❌ Action must be Chop, Rest, Scout, Attack, Forage, Build, Share, Move, Mate, or Interact."
            )
            return
        if action == "Move":
            if not target or target.upper() not in ("N", "S", "E", "W"):
                await ctx.send("❌ Move requires a direction: N, S, E, or W.")
                return
            target = target.upper()
        elif action == "Interact":
            flavor = target or "idling"
            state.god_orders[pawn_id] = {"action": action, "target": None, "flavor": flavor}
            await ctx.send(f"🗣️ Order locked in: **{pawn['name']}** must {flavor}.")
            return
        elif action in needs_target:
            if not target:
                await ctx.send("❌ Attacks, shares, and mates require a valid target (not self).")
                return
            if action == "Attack":
                target, t_err = resolve_pawn_id(target)
                if t_err:
                    target, t_err = resolve_animal_id(target)
            else:
                target, t_err = resolve_pawn_id(target)
            if t_err:
                await ctx.send(f"❌ {t_err}")
                return
            if target and not target.startswith("wild_") and target == pawn_id:
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
        state.save_state()
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
        beloved = " 💖" if entry.get("beloved") else ""
        survived = max(0, entry.get("died_tick", 0) - entry.get("born_tick", 0))
        lines.append(
            f"- **{entry['name']}**{title}{beloved} — died of {entry['cause']} "
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
        f"🌲 Wood {biome['wood_stock']} | 🍎 Food {biome['food_stock']}"
        + core._biome_infra_txt(biome),
    ]
    for pid, pawn in state.world_state["pawns"].items():
        lines.append(f"- {_pawn_line(pid, pawn)}")
    if state.god_orders:
        pending = ", ".join(
            f"{pid} → {o['action']}" for pid, o in state.god_orders.items()
        )
        lines.append(f"**Pending orders:** {pending}")
    await ctx.send("\n".join(lines))


@bot.command(name="tree")
@is_god_channel()
async def family_tree(ctx):
    """!tree — show couples, kinship, and rivalries."""
    await ctx.send(engine.render_family_tree())


@bot.command(name="bio")
@is_god_channel()
async def bio(ctx, name: str):
    """!bio <name|pawn_id> — compose a 3-sentence biography or obituary from a pawn's life log."""
    pawn, err = engine.find_pawn_ref(name)
    if err:
        await ctx.send(f"❌ {err}")
        return
    await ctx.send(f"📜 Writing the life of **{pawn['name']}**...")
    text = await core.compose_bio(pawn["id"])
    if not text:
        await ctx.send("❌ No record of that pawn.")
        return
    header = "🪦 **Obituary**" if pawn["id"] not in state.world_state["pawns"] else "📜 **Biography**"
    await ctx.send(f"{header} — {pawn['name']}:\n{text}")


@bot.command(name="wildlife")
@is_god_channel()
async def wildlife_cmd(ctx):
    """!wildlife — list the fauna roaming the terrarium."""
    ws = state.world_state["wildlife"]
    if not ws:
        await ctx.send("🌿 The terrarium is quiet — no animals are about.")
        return
    lines = ["🐾 **Wildlife:**"]
    for w in ws:
        spec = engine.WILDLIFE[w["species"]]
        if w["state"] == "tamed":
            tamer = state.world_state["pawns"].get(w["tamed_by"])
            who = f" (tamed by {tamer['name']})" if tamer else " (tamed)"
            lines.append(f"- {spec['emoji']} **{w['species']}** (`{w['id']}`) HP {w['hp']}{who}")
        else:
            lines.append(f"- {spec['emoji']} **{w['species']}** (`{w['id']}`) HP {w['hp']} @ {w['pos']}")
    await ctx.send("\n".join(lines))


@bot.command(name="visitors")
@is_god_channel()
async def visitors_cmd(ctx):
    """!visitors — list the wandering travelers at the edge of the world."""
    vs = state.world_state.get("visitors", [])
    if not vs:
        await ctx.send("🚶 No travelers are passing through right now.")
        return
    lines = ["🧭 **Visitors:**"]
    for v in vs:
        lines.append(
            f"- {engine.VISITOR_TYPES[v['kind']]['emoji']} **{v['name']}** "
            f"(`{v['id']}`) the {v['kind']} HP {v['hp']} @ {v['pos']} ({v['state']})"
        )
    await ctx.send("\n".join(lines))


@bot.command(name="raiders")
@is_god_channel()
async def raiders_cmd(ctx):
    """!raiders — list the hostile scavengers menacing the colony."""
    rs = state.world_state.get("raiders", [])
    if not rs:
        await ctx.send("🥷 No raiders are about — the camp is safe.")
        return
    lines = ["⚠️ **Raiders:**"]
    for r in rs:
        lines.append(
            f"- 🥷 **{r['name']}** (`{r['id']}`) HP {r['hp']} @ {r['pos']} "
            f"({r['state']}"
            + (f", {r['stolen']} food stolen" if r["stolen"] else "")
            + ")"
        )
    await ctx.send("\n".join(lines))


@bot.command(name="heirlooms")
@is_god_channel()
async def heirlooms_cmd(ctx):
    """!heirlooms — list the relics of the fallen."""
    hs = state.world_state["heirlooms"]
    if not hs:
        await ctx.send("🏆 No heirlooms yet — a titled pawn must die holding a tool.")
        return
    lines = ["🏆 **Heirlooms:**"]
    for h in hs:
        owner = state.world_state["pawns"].get(h.get("owner"))
        who = f"held by {owner['name']}" if owner else "unclaimed"
        lines.append(f"- **{h['name']}** — {who} ({h['source']})")
    await ctx.send("\n".join(lines))


@bot.command(name="chronicle")
@is_god_channel()
async def chronicle_cmd(ctx):
    """!chronicle — read the seasonal chronicle of the terrarium."""
    cs = state.world_state["chronicle"]
    if not cs:
        await ctx.send("📜 The chronicle is still blank — no season has turned yet.")
        return
    lines = ["📜 **The Chronicle**"]
    for entry in cs[-6:]:
        lines.append(f"*{entry['season']}* — **{entry['title']}** (tick {entry['tick']})")
        lines.append(f"> {entry['text'][:300]}")
    await ctx.send("\n".join(lines))


@bot.command(name="lore")
@is_god_channel()
async def lore_cmd(ctx):
    """!lore — read the fragments recovered from The Sunken Tribe's ruins."""
    lore = state.world_state.get("lore") or []
    if not lore:
        await ctx.send(
            f"💀 The ruins of {engine.SUNKEN_TRIBE} guard their secrets still — "
            "send a Scout to unearth them."
        )
        return
    lines = [f"💀 **Fragments of {engine.SUNKEN_TRIBE}**"]
    for frag in lore[-10:]:
        lines.append(f"- {frag['text']}")
    await ctx.send("\n".join(lines))


@bot.command(name="badges")
@is_god_channel()
async def badges_cmd(ctx):
    """!badges — list the relational badges each colonist has earned by their deeds."""
    out = ["🏅 **Relational badges** (earned by deeds, shown to the AI Director)"]
    for pid, p in state.world_state["pawns"].items():
        if p["status"] != "active":
            continue
        names = []
        for oid, bgs in p.get("rel_badges", {}).items():
            other = engine._pawn_by_id(oid)
            if other:
                names += [f"{b} of {other['name']}" for b in bgs]
        names += list(p.get("badges", []))
        if names:
            out.append(f"- **{p['name']}**: {', '.join(names)}")
    if len(out) == 1:
        out.append("No badges earned yet — deeds will speak soon.")
    await ctx.send("\n".join(out))


@bot.command(name="monument")
@is_god_channel()
async def monument_cmd(ctx):
    """!monument — inspect the Ancestral Monolith."""
    mon = state.world_state.setdefault(
        "monument", {"wood": 0, "stone": 0, "done": False, "inscription": None}
    )
    if mon.get("done"):
        msg = (
            "🗿 **Ancestral Monolith** — complete! It anchors colony morale "
            "(never below 10), warms the camp (+2 insulation), and answers prayers "
            "(`Interact` with *pray* at Camp for divine inspiration or a weather warning)."
        )
        if mon.get("inscription"):
            msg += f"\n*“{mon['inscription']}”*"
        else:
            msg += "\n*No dedication has been carved yet.*"
        runes = mon.get("runes") or []
        if runes:
            msg += "\n\n**Permanent runes:**"
            for r in reversed(runes):
                msg += f"\n- **{r['title']}** (day {r.get('tick', 0) // engine.TICKS_PER_DAY}) — {r['text']}"
        else:
            msg += "\n\nNo runes have been carved yet."
        await ctx.send(msg)
        return
    if mon.get("wood", 0) or mon.get("stone", 0):
        await ctx.send(
            f"🗿 The Ancestral Monolith is under construction — "
            f"{mon['wood']}/{engine.MONUMENT_WOOD_NEEDED} wood, "
            f"{mon['stone']}/{engine.MONUMENT_STONE_NEEDED} stone."
        )
        return
    biome = state.world_state["biome"]
    if (
        biome["shelter"] >= 100
        and biome["campfire"] >= 100
        and biome.get("granary")
        and biome.get("palisade", 0) >= engine.PALISADE_MAX
    ):
        await ctx.send(
            "🗿 The camp is fully fortified — Build to raise the Ancestral "
            "Monolith (20 wood + 15 stone, 5 of each per action)."
        )
        return
    await ctx.send(
        "🗿 No monument yet — complete the shelter and campfire (100), build the "
        "Granary, and max the Palisade to unlock it."
    )


@bot.command(name="tradition")
@is_god_channel()
async def tradition_cmd(ctx):
    """!tradition — inspect the colony's emergent tradition and its history."""
    t = state.world_state.setdefault(
        "traditions", {"tag": None, "predators_slain": 0, "trees_felled": 0, "rations_shared": 0}
    )
    effects = {
        engine.HUNTERS_TAG: "+2 combat XP when hunting; cold penalties −1",
        engine.FORESTERS_TAG: "+1 wood from Chop; shelter degrades half as fast",
        engine.KINDRED_TAG: "social Interact grants +8 morale instead of +5",
    }
    if t.get("tag"):
        msg = (
            f"🏛️ **{t['tag']}**\n*{effects[t['tag']]}*\n\n"
            f"Colony history: {t['predators_slain']} predators slain, "
            f"{t['trees_felled']} trees felled, {t['rations_shared']} rations shared."
        )
    else:
        msg = (
            "🏛️ No tradition yet — a way of life emerges from survival. "
            f"Thresholds: {engine.HUNTERS_THRESHOLD} predators slain, "
            f"{engine.FORESTERS_THRESHOLD} trees felled, "
            f"{engine.KINDRED_THRESHOLD} rations shared. "
            f"So far: {t['predators_slain']} / {t['trees_felled']} / {t['rations_shared']}."
        )
    await ctx.send(msg)


@bot.command(name="recipes")
@is_god_channel()
async def recipes_cmd(ctx):
    """!recipes — list all known blueprints (base + synthesized)."""
    await ctx.send(core.recipes_txt())


@bot.command(name="quests", aliases=["prophecies"])
@is_god_channel()
async def quests_cmd(ctx):
    """!quests / !prophecies — view the world's active objectives."""
    await ctx.send(core.quests_txt())


@bot.command(name="patchnotes")
@is_god_channel()
async def patchnotes_cmd(ctx):
    """!patchnotes — read the latest autonomous balance notes from the Architect."""
    await ctx.send(core.patchnotes_txt())


@bot.command(name="adopt")
async def adopt(ctx, pawn_id: str):
    """!adopt <name|pawn_id> — bond with a pawn; you'll be DM'd about its milestones (any channel)."""
    async with core.tick_lock:
        pid, err = resolve_pawn_id(pawn_id)
        if err:
            await ctx.send(f"❌ {err}")
            return
        uid = str(ctx.author.id)
        state.world_state["adoptions"][uid] = pid
        state.save_state()
        name = state.world_state["pawns"][pid]["name"]
    await ctx.send(f"🐾 **{name}** is now your adopted pawn. You'll be DM'd about its milestones.")


@bot.command(name="unadopt")
async def unadopt(ctx):
    """!unadopt — release your adopted pawn."""
    uid = str(ctx.author.id)
    async with core.tick_lock:
        pid = state.world_state["adoptions"].pop(uid, None)
        state.save_state()
    if pid:
        name = state.world_state["pawns"].get(pid, {}).get("name", pid)
        await ctx.send(f"🐾 You released **{name}**.")
    else:
        await ctx.send("❌ You haven't adopted a pawn.")


@bot.command(name="my")
async def my_pawn(ctx):
    """!my — show your adopted pawn."""
    pid = state.world_state["adoptions"].get(str(ctx.author.id))
    if not pid:
        await ctx.send("❌ You haven't adopted a pawn yet — try `!adopt <name>`.")
        return
    pawn = state.world_state["pawns"].get(pid)
    if not pawn:
        await ctx.send("🪦 Your adopted pawn is no longer among the living.")
        return
    await ctx.send(f"Your adopted pawn:\n{_pawn_line(pid, pawn)}")


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


async def _dm_adopter(user_id, message):
    """Gateway DM hook registered as core.notifier (webhooks can't DM)."""
    try:
        user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
        if user:
            await user.send(message)
    except Exception as e:
        print(f"Adoption DM to {user_id} failed: {e}")


@bot.event
async def on_ready():
    global tick_task
    core.notifier = _dm_adopter
    print(f"🤖 Logged in as {bot.user}")
    print(f"📡 God channel: {GOD_CHANNEL_NAME or 'any channel'}")
    if tick_task is None or tick_task.done():
        tick_task = asyncio.create_task(core.tick_loop())
    if state.world_state.get("extinct"):
        print("🪦 World is extinct — scheduler stays paused.")
        core.pause_event.clear()
