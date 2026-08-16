# 🌿 Digital Terrarium

An LLM-driven multi-agent simulation that runs forever in a Discord server. An AI "director" (hosted Gemma 4 via the Google Gemini API) narrates a tiny living world on a fixed 5×5 map, and a human "god" can intervene live through Discord commands.

![Architecture](https://img.shields.io/badge/stack-Python%20%7C%20Discord%20%7C%20Gemini-blue)

## How it works

Every tick (default 60 s):

1. **Schema rebuild** — a Pydantic schema is generated from the live agent roster.
2. **Decision** — the LLM proposes *intent only*: action, narrative, quote, inner monologue, direction, target, free-form `flavor` verb, and optional personal goal.
3. **Override** — god orders (`!order`) replace the model's proposal.
4. **Resolve** — a deterministic engine (`engine.py`) validates, costs, and applies all consequences.
5. **Persist & broadcast** — state saves, events log to `terrarium_log.jsonl`, and high-impact milestones post to Discord (era chronicles, fallen-hero eulogies, patch notes, and crisis alerts) — quiet ticks stay quiet.

The model **never emits stat numbers** — the engine is the sole source of truth, so a hallucinating LLM cannot corrupt the simulation.

## Features

- **AI director** — Gemma 4 (31B, fallback 26B MoE) decides for every pawn each tick, with per-tick structured JSON output
- **5×5 living world** — seasons, weather, day/night, depletable wood/food stocks, campfire warmth
- **Wildfires & dynamic tiles** — lightning storms and Summer heatwaves can ignite the forest: 🔥 burning tiles hurt pawns, drain wood, and spread to nearby Forest and the Camp until they burn out into 🌫️ scorched earth that regrows over time. Pawns can `Interact` to douse an adjacent fire or `Chop` a firebreak
- **Seasonal disasters** — Spring downpours flood the riverbanks (🌊 meadows flood for 3 ticks — no foraging, then +5 wild food as it recedes); clear Winter nights can bring the ✨ Aurora Borealis (+10 colony morale); damp Autumn air brews ☠️ toxic spores around the Ruins (5 HP/tick unless a `Warm Coat` is worn)
- **Pawn biology & psyche** — HP, energy, hunger, warmth, morale, skills, relationships, gear, mental breaks
- **Traits & moodlets** — deterministic psychological layers rolled at spawn/birth (Night Owl, Brawler, Pyromaniac, Pacifist, Iron Stomach); transient moodlets (Grief, Frostbitten) decay and can tip a pawn into a mental break
- **Free-form `Interact` + personal goals** — pawns can do almost anything (socialize, gather, craft, relax, train) and pursue LLM-proposed personal goals (gather wood, befriend the Chief, survive the season) that pay morale and skill XP
- **Wildlife & hunting** — season-gated prey/predators roam the map: hunt them for food+fiber, or tame them into camp pets that lift morale; predators bite to incapacitate, never kill
- **Visitors & travelers** — every ~150 ticks a wandering NPC (Merchant, Lost Wanderer, or Bard) walks in from the grid edge, lingers by the campfire, and leaves: share food to barter, court or invite them to stay to recruit a colonist, or rob them and feel the guilt
- **Fortifications** — build a Granary (stops Summer food decay) and a Palisade (deters predators)
- **Megaprojects** — once the camp is fully fortified, `Build` raises the **Ancestral Monolith** (20 wood + 15 stone, 5/5 per action): it permanently anchors colony morale (never below 10) and warms the camp (`!monument` shows its LLM-carved dedication)
- **Oracle & rune archive** — the completed monolith is an **oracle**: significant achievements (tradition forged, prophecy fulfilled, first predator slain, a new generation's firstborn) are carved as **permanent runes** (`!monument`) — including the **fall of a beloved, titled, or elder ancestor**, so a death in one generation becomes a legend for the next — and colonists who `Interact` with *pray* at Camp gain divine inspiration (+8 morale, +1 XP to their weakest skill) — and in the cold, a *Divine Warmth* blessing that shields them from frost
- **Farming** — till a Meadow (`🫐`) into a **Farm Plot** (`🌾`) with `Interact` ("till soil" / "plant seeds" / "farm"); it ripens over 20 ticks in Spring/Summer, then `Interact` to harvest a guaranteed 15 food + 5 fiber without depleting wild stocks
- **Reproduction & lineage** — pawns have a sex (♂/♀); mutually bonded pairs Mate (relationship ≥ 25), pregnancies come to term, newborns mature into colonists (capped at 10), and `!tree` shows couples, kinship, and rivalries
- **Aging & old age** — pawns age tick by tick; elders (👴) tire faster, heal less, and eventually die of old age, freeing a colony slot
- **Tools & crafting** — Stone Axe, Flint Spear, Warm Coat (built at Camp)
- **Permadeath** — freeze in a Blizzard, starve, or reach old age → pawn is enshrined in the Graveyard with a tombstone and eulogy
- **Seasonal chronicle** — a lorekeeper LLM writes a title and paragraph whenever the season turns (`!chronicle`)
- **Living memory & biographies** — `!bio <name>` reads a pawn's own life log and weaves it into a 3-sentence heroic saga (living) or mournful obituary (fallen ancestors in the graveyard)
- **Generational handoffs & dynasties** — every pawn carries its **generation** (founders = Gen 1, children +1); the prompt always shows the dynasty roll-up (living + fallen 🪦 per generation), the colony's cumulative deeds, and unclaimed ancestral relics, so Generation 2 and 3 inherit the memory of Generation 1
- **Emergent traditions** — the engine tallies colony history and auto-assigns a **Tradition Tag** on a season change: *Hunters of the North* (10+ predators slain → double hunting XP, colder-tolerant), *Children of the Forest* (100+ trees felled → +1 wood per chop, shelter decays half as fast), or *Kindred of the Hearth* (20+ rations shared → socials grant +8 morale). Tags persist once earned (`!tradition` shows the tag, its effects, and the counters)
- **Festivals & rites** — on the first day of Winter and Summer, a bountiful larder (15+ camp food) means a **Solstice Feast**: everyone gains +15 morale and a Festive moodlet. When a beloved pawn dies (high average relationships, marked 💖 in `!graveyard`), survivors can `Interact` at the Camp or Ruins to *bury*, *mourn*, or *eulogize* — halving the grief of everyone gathered
- **Scavenger raids** — a wealthy colony (30+ food+wood on hand) attracts Autumn raids: 1–2 hostile scavengers march on the camp to loot the granary (5 food, then they flee). Palisades slow their approach; tamed predators and high-combat pawns at the camp drive them off or cut them down before they steal; wounding one sends it running
- **Heirlooms** — titled pawns drop their tools as relics on death; claim them to pass on skills (`!heirlooms`)
- **Autonomous world engine** — every 400 ticks (one year) an **Architect LLM** reviews the world's fortunes and emits a bounded balance patch (regrowth/cold/spawn multipliers clamped to `[0.7, 1.3]`), optionally synthesizing a new tool blueprint (crafted via `Build`, tier 4+) or seeding a **world prophecy** — a colony-wide quest (hunt, chop, stockpile, or survive) that pays shared morale and a custom title when completed. Patches post as ⚙️ *Terrarium Patch Notes* embeds (`!patchnotes`) and are queryable via `!recipes` and `!quests`
- **Pawn adoption** — any Discord user can `!adopt` a pawn and get DM notifications about its births, goals, breaks, and deaths
- **Ancient pre-history** — the Ruins 💀 are the remnants of **The Sunken Tribe**: Scouts there sometimes unearth fragments of forgotten history, an ancient tool **blueprint** (craftable `Sunken Harpoon` / `Tidal Shawl`, tier 4), or a carved **warning** that the colony heeds (+2 scouting XP, +5 colony morale). Recovered lore feeds the prompt and `!lore`
- **Relational badges** — deeds leave durable labels the AI Director can weave into drama: **Lifesaver** (shared food with a starving pawn), **Betrayer** (attacked a friend, 25+ bond), **Indebted** (received a share), **Mentor** (*teach* an Interact near a pupil), **Widow** (lost a partner). Shown per pawn in the prompt and via `!badges`
- **Blood feuds** — children are born carrying their parents' rivalries (seeded −40 toward each mutual rival), and mutual rivals who share the camp tile risk flare-ups: a **camp brawl** (−3 HP each, deeper hatred). The only way out is the LLM's choice — courtship, sharing food (+25/share), or letting the feud burn on
- **Dynamic roles** — the Director can bestow custom titles for earned deeds (`new_title`, e.g. *"Fang-Breaker"*, *"Keeper of the Hearth"*, *"Seer of Whispers"`). The engine buckets them by keyword into subtle passive perks — **martial** (fang/claw/blade/slayer/…) → −2 damage taken, **nurturing** (keeper/hearth/mother/…) → +1 food per share, **spiritual** (seer/shaman/oracle/…) → grief heals 2× faster. Shown on the pawn line and via `!roles`
- **Annual Camp Council** — every year a council LLM reviews the colony's year, names a **recognized leader** (Chosen moodlet, +5 morale) and issues a one-sentence **Colony Mandate** (e.g. *"Tame the beasts of the wood"*). The mandate leads every prompt so the whole colony steers together toward the year's focus (`!council`)
- **Trophic cascades** — hunting every predator away removes predator pressure: deer and rabbits **overpopulate** (cap 3 → 5), strip the wild forage (`food_stock`), and raid ripe farm plots. Clear-cutting the Forest (≤6 tiles) strips the **windbreak**: Winter cold +2 and Spring flood risk roughly doubles. The Director sees this in the prompt and the consequences land in the event log
- **Legendary beasts** — a wild predator that has mauled multiple colonists earns a permanent name (*The Grey Terror*, *Old Scar-Face*) and grows tougher with each escape (fame raises HP and bite). The whole colony carries a *Legend Hunt* moodlet, the beast stalks the woods season after season (👑 on the map), and slaying it grants +15 colony morale and a `legends_slain` counter (`!legends`)
- **Fog of war** — the 16 outer rim tiles start shrouded in mist (🌫): Scouts reveal the perimeter one Scout-action at a time, and fully mapping it lifts the mist with a colony-wide morale bonus
- **Off-grid expeditions** — two colonists at the map's edge can `Expedition` (15 energy + 5 rations each) to leave the grid for 15–20 ticks, returning with rare loot, exotic seeds (a new farm plot), a tamed companion, or battle scars (`!fog` shows who's away)
- **Seasonal cataclysms** — at a season change a trial may descend for 150 ticks: *The Long Winter* doubles the campfire's fuel appetite and drives the cold harder than any blizzard; *The Great Drought* dries the rivers (river forage fails) and doubles lightning and wildfire spread (`!cataclysm` shows the active trial)
- **Dynamic colony identity & taboos** — the colony earns an evolving name from what it survives (survived The Long Winter → *The Hearthfolk*, wildfire → *The Ashen Kin*, famine → *The Famineborn*, a tradition → *The Kindred*); traumas seed cultural taboos, so a death in the Ruins makes low-bravery colonists refuse to set foot there (`!colony` / `!taboo` show both)
- **The Voice in the Sky & camp shrines** — three god whispers (`!say`) to the same colonist make them a **Prophet** (🕊️): a spiritual leader who gains steady morale and can preach at camp to steady everyone on the tile; a fortified colony can raise a small shrine (Build) and leave food offerings (Interact `offer`) to appease the Creator — a Prophet's tithe counts double, and a full shrine blesses the whole colony and halves the next cataclysm's chance (`!shrine` shows all)
- **Physical folklore & herbal medicine** — artisans carve wooden totems (Interact `carve a totem`, 2 wood) commemorating the colony's landmarks (survived cataclysms, slain legends, the Monolith, shrine blessings), stirring a *Proud* moodlet across the colony that keeps the memory alive for future generations (`!totems`); foragers gather herbs on meadow tiles (Interact `gather herbs`) into salves and brew them at camp (Interact `brew salve`/`heal`) to nurse the most-injured colonist on the tile back to health (+12 HP, clears frostbite)
- **God interface** — spawn, edit, order, whisper, pause/resume, inspect wildlife, visitors & raiders, read the chronicle
- **Milestone news hub** — Discord no longer broadcasts every tick. Embeds are reserved for high-impact moments: 📜 a new-era chronicle each season, 🪦 fallen-hero eulogies (tombstone inscription + cause of death), ⚙️ annual patch notes, and 🥷🔥🌊☠️ breaking crisis alerts (raids, wildfires, floods, miasma, extinction)
- **Map renderer** — a pure-Python PNG renderer (no Pillow) draws the grid, pawns, and wildlife into the milestone embeds
- **Live isometric web diorama** — a zero-dependency asyncio server (`feed.py`, hand-rolled RFC 6455 WebSocket + static files) broadcasts a clean JSON snapshot after every tick, and a vanilla HTML/CSS/JS client (`web/`) renders it as a floating isometric island with **procedurally-generated pixel-art sprites** (hand-authored string-grid sprites + seeded ground textures in `web/sprites.js`, drawn with nearest-neighbor scaling — zero external assets, no runtime downloads): the island floats over a season/day-aware sky (twinkling stars, mountain silhouettes) with rock strata, roots, and a ground shadow; standing pawn sprites (sex/elder/child + hue variants, idle/walk strides) plus pixel fauna/visitor/raider sprites (legendary beasts get a dark variant) walk diagonally to their tiles (0–4 s) — pawns on the same tile fan out in a stable diamond formation with hover name pills — comic speech and cloudy thought bubbles float above the individual sprite (4–12 s), and looping animations and particles (4-frame campfire flame, campfire smoke, river shimmer, night tint, **drifting snow** in winter and a **warm night glow** around camp) run the rest of the tick. An interactive HUD sits on top: a wooden-banner top bar with season/weather/day-night, wood/food/stone/fiber stockpile chips, campfire/shelter gauges and winter frost edging; a 👥 colonist roster drawer (pixel portraits + mini health/energy bars + current action); a scrolling bottom narrative log that highlights AI-Director prose with an amber rail; click-to-inspect pawn dossiers (vitals, gear, rucksack, skills, goal, relationships, lineage); and a 📖 Lore panel with Graveyard, Monolith, Chronicle, and Patch-notes tabs. Open `http://<host>:8900/` in a browser (auto-reconnects; `FEED_PORT`/`FEED_HOST`/`FEED_ENABLED` configurable)
- **Auto-persist** — survives restarts; `terrarium_state.json` auto-migrates from older saves

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env      # then fill in your keys
python main.py
```

### Environment variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `DISCORD_BOT_TOKEN` | ✅ | Bot token from the [Discord Developer Portal](https://discord.com/developers/applications) (enable **Message Content Intent**) |
| `GEMINI_API_KEY` | ✅ | Key from [Google AI Studio](https://aistudio.google.com/) |
| `DISCORD_WEBHOOK_URL` | 🟡 | Channel webhook for the embeds (optional — bot falls back to chat) |
| `GOD_CHANNEL_NAME` | — | Restrict god commands to one channel (default: any) |
| `BOT_COMMAND_PREFIX` | — | Command prefix (default `!`) |
| `TICK_INTERVAL_SECONDS` | — | Seconds per tick (default 60) |
| `FEED_ENABLED` | — | Serve the live web diorama (default `1`; set `0` to disable) |
| `FEED_HOST` / `FEED_PORT` | — | Bind host/port for the diorama feed (default `0.0.0.0:8900`; browser clients connect to `http://<host>:8900/`) |
| `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` | — | Primary/fallback model ids |
| `LLM_TEMPERATURE` | — | Sampling temperature (default 0.7) |
| `NOTIFY_USER_ID` | — | Discord user id pinged on total extinction (defaults to a configured id) |

### Exposing the diorama (ngrok static domain — on the LXC)

The feed server binds `0.0.0.0:8900` on the LXC. The diorama is published at a **static ngrok domain** — `budget-universe-manila.ngrok-free.dev` — so the URL never rotates and the Discord Activity mapping is set once.

```bash
# on the LXC (as root): install ngrok to /usr/local/bin/ngrok
curl -L https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -o /tmp/ngrok.tgz
tar xzf /tmp/ngrok.tgz -C /usr/local/bin ngrok

# paste your dashboard authtoken into deploy/ngrok.service (the
# --authtoken=... argument in ExecStart), then install the unit:
cp deploy/ngrok.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now ngrok
journalctl -u ngrok -f                      # confirms the public URL
curl -s https://budget-universe-manila.ngrok-free.dev/ | head   # sanity check
```

Because the domain is static, the URL survives restarts — map it once in the Discord Developer Portal under **Activities / URL Mappings**, and the Rocket activity icon launches the diorama from any voice channel.

**Convenience alias** (run as root — restarts both services after pulling; the static ngrok domain means no URL re-mapping after restarts):

```bash
alias update='cd /opt/terrarium && git pull origin main && chown -R terrarium:terrarium /opt/terrarium && systemctl restart terrarium && systemctl restart ngrok && journalctl -u terrarium -f'
```

## God commands (prefix `!`)

| Command | Effect |
|---|---|
| `!add [name] [hp] [energy]` | Spawn a new pawn (name and job auto-generated if omitted) |
| `!rename <name\|pawn_id> <newname>` | Rename a pawn |
| `!job <name\|pawn_id> <job>` | Set a pawn's job/role (flavor only, e.g. `!job Willow Lumberjack`) |
| `!remove <name\|pawn_id>` | Remove a pawn (never the last) |
| `!god <name\|pawn_id> <stat> <value>` | Set vitals / sex / wood / food / stone / fiber, or `revive` |
| `!order <name\|pawn_id> <action> [target]` | Enforce an action next tick (Move takes `N/S/E/W`; Mate takes a bonded partner) |
| `!say <name\|pawn_id> <text>` | Whisper to a pawn in the prompt (+15 morale) |
| `!graveyard` | List the fallen with epitaphs |
| `!bio <name\|pawn_id>` | 3-sentence biography (living) or obituary (fallen) woven from a pawn's life log |
| `!list` | List all pawns with full stats for easy targeting |
| `!tree` | Show couples, kinship, and rivalries |
| `!wildlife` | List the fauna roaming the terrarium |
| `!visitors` | List the wandering travelers at the edge of the world |
| `!raiders` | List the hostile scavengers menacing the colony |
| `!heirlooms` | List the relics of the fallen |
| `!monument` | Inspect the Ancestral Monolith (dedication, permanent runes, oracle) |
| `!tradition` | Inspect the colony's emergent Tradition Tag (or its progress toward one) |
| `!chronicle` | Read the seasonal chronicle of the terrarium |
| `!lore` | Read the fragments recovered from The Sunken Tribe's ruins |
| `!badges` | List the relational badges colonists have earned by their deeds |
| `!roles` | List the Director-invented custom roles and their keyword-bucketed perks |
| `!council` | The annual Camp Council — the recognized leader and this year's Colony Mandate |
| `!legends` | The legendary beasts that have earned names from their maulings, and their fates |
| `!fog` | Fog of war: perimeter tiles mapped, and which colonists are off-map on expeditions |
| `!cataclysm` | The active multi-tick seasonal trial (*The Long Winter* / *The Great Drought*) and its effects |
| `!colony` | The colony's evolving name and the landmarks it survived |
| `!taboo` | Cultural taboos born from the colony's traumas (e.g. fearing the Ruins) |
| `!shrine` | The camp shrine's offerings, blessings, and the Voice's Prophet |
| `!totems` | Carved wooden totems remembering the colony's landmarks |
| `!recipes` | List all known blueprints (base + Architect-synthesized + ancient) |
| `!quests` / `!prophecies` | View the world's active objectives and progress |
| `!patchnotes` | Read the latest autonomous balance notes from the Architect |
| `!status` / `!tick` / `!pause` / `!resume` | Inspect, force, or gate the simulation |
| `!reset` | Wipe the world and restart from tick 1 (two fresh founders) — clears graveyard, chronicle, traditions, and all progression |
| `!adopt <name\|pawn_id>` | Bond with a pawn — you'll be DM'd about its milestones (any channel) |
| `!unadopt` | Release your adopted pawn (any channel) |
| `!my` | Show your adopted pawn (any channel) |

`!adopt`, `!unadopt`, and `!my` need no god channel: any Discord user can adopt one pawn (a second `!adopt` replaces the previous ward).

Pawns are targeted **by name** (case-insensitive) or by their `pawn_N` id. New pawns get an auto-generated name (e.g. `Willow`) and a flavor job (e.g. `the Forager`) from built-in pools, or you can set both explicitly (`!add Fern`, `!job Fern Hunter`).

**Total extinction is possible**: if every pawn dies (blizzard freeze or starvation), the bot pings `NOTIFY_USER_ID`, pauses itself to stop API usage, and waits for you to `!add` new colonists and `!resume`.## Run as a service (Proxmox / LXC)

```bash
sudo useradd -r -m terrarium
sudo cp -r . /opt/terrarium   # includes .env, state, log
cd /opt/terrarium && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
sudo cp deploy/terrarium.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now terrarium
journalctl -u terrarium -f   # follow the logs
```

Also enable **LXC → Options → Start at boot** so the bot returns when the host powers on.

## Data files

| File | Purpose |
|---|---|
| `terrarium_state.json` | Auto-saved world state (gitignored) |
| `terrarium_log.jsonl` | Append-only structured event log — the dataset (gitignored) |
| `paper.txt` | The accompanying paper (pdflatex; rename to `main.tex` on Overleaf) |

## Development

```bash
ruff check . && python -m pytest tests -q   # 233 tests, fully offline
```

See `AGENTS.md` for the architecture, the engine's lockstep constraints (adding a stat/action touches multiple modules), and deployment notes.

Built with [opencode](https://opencode.ai) — an open-source AI coding CLI that wrote, tested, and iterated the codebase with a human in the loop.

## Disclaimer

`google-genai` requires a network call to the Gemini API. Free-tier quotas (~14.4K requests/day, 30 RPM) are more than enough for a 60 s tick; the server costs nothing while the bot is off.
