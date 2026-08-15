# 🌿 Digital Terrarium

An LLM-driven multi-agent simulation that runs forever in a Discord server. An AI "director" (hosted Gemma 4 via the Google Gemini API) narrates a tiny living world on a fixed 5×5 map, and a human "god" can intervene live through Discord commands.

![Architecture](https://img.shields.io/badge/stack-Python%20%7C%20Discord%20%7C%20Gemini-blue)

## How it works

Every tick (default 60 s):

1. **Schema rebuild** — a Pydantic schema is generated from the live agent roster.
2. **Decision** — the LLM proposes *intent only*: action, narrative, quote, inner monologue, direction, target, free-form `flavor` verb, and optional personal goal.
3. **Override** — god orders (`!order`) replace the model's proposal.
4. **Resolve** — a deterministic engine (`engine.py`) validates, costs, and applies all consequences.
5. **Persist & broadcast** — state saves, events log to `terrarium_log.jsonl`, an embed posts to Discord.

The model **never emits stat numbers** — the engine is the sole source of truth, so a hallucinating LLM cannot corrupt the simulation.

## Features

- **AI director** — Gemma 4 (31B, fallback 26B MoE) decides for every pawn each tick, with per-tick structured JSON output
- **5×5 living world** — seasons, weather, day/night, depletable wood/food stocks, campfire warmth
- **Wildfires & dynamic tiles** — lightning storms and Summer heatwaves can ignite the forest: 🔥 burning tiles hurt pawns, drain wood, and spread to nearby Forest and the Camp until they burn out into 🌫️ scorched earth that regrows over time. Pawns can `Interact` to douse an adjacent fire or `Chop` a firebreak
- **Pawn biology & psyche** — HP, energy, hunger, warmth, morale, skills, relationships, gear, mental breaks
- **Traits & moodlets** — deterministic psychological layers rolled at spawn/birth (Night Owl, Brawler, Pyromaniac, Pacifist, Iron Stomach); transient moodlets (Grief, Frostbitten) decay and can tip a pawn into a mental break
- **Free-form `Interact` + personal goals** — pawns can do almost anything (socialize, gather, craft, relax, train) and pursue LLM-proposed personal goals (gather wood, befriend the Chief, survive the season) that pay morale and skill XP
- **Wildlife & hunting** — season-gated prey/predators roam the map: hunt them for food+fiber, or tame them into camp pets that lift morale; predators bite to incapacitate, never kill
- **Fortifications** — build a Granary (stops Summer food decay) and a Palisade (deters predators)
- **Reproduction & lineage** — pawns have a sex (♂/♀); mutually bonded pairs Mate (relationship ≥ 25), pregnancies come to term, newborns mature into colonists (capped at 10), and `!tree` shows couples, kinship, and rivalries
- **Aging & old age** — pawns age tick by tick; elders (👴) tire faster, heal less, and eventually die of old age, freeing a colony slot
- **Tools & crafting** — Stone Axe, Flint Spear, Warm Coat (built at Camp)
- **Permadeath** — freeze in a Blizzard, starve, or reach old age → pawn is enshrined in the Graveyard with a tombstone and eulogy
- **Seasonal chronicle** — a lorekeeper LLM writes a title and paragraph whenever the season turns (`!chronicle`)
- **Heirlooms** — titled pawns drop their tools as relics on death; claim them to pass on skills (`!heirlooms`)
- **Pawn adoption** — any Discord user can `!adopt` a pawn and get DM notifications about its births, goals, breaks, and deaths
- **God interface** — spawn, edit, order, whisper, pause/resume, inspect wildlife, read the chronicle
- **Map renderer** — a pure-Python PNG renderer (no Pillow) draws the grid, pawns, and wildlife into the daily embed
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
| `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` | — | Primary/fallback model ids |
| `LLM_TEMPERATURE` | — | Sampling temperature (default 0.7) |
| `NOTIFY_USER_ID` | — | Discord user id pinged on total extinction (defaults to a configured id) |

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
| `!list` | List all pawns with full stats for easy targeting |
| `!tree` | Show couples, kinship, and rivalries |
| `!wildlife` | List the fauna roaming the terrarium |
| `!heirlooms` | List the relics of the fallen |
| `!chronicle` | Read the seasonal chronicle of the terrarium |
| `!status` / `!tick` / `!pause` / `!resume` | Inspect, force, or gate the simulation |
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
| `paper.tex` | The accompanying paper (pdflatex, compiles on Overleaf) |

## Development

```bash
ruff check . && python -m pytest tests -q   # 221 tests, fully offline
```

See `AGENTS.md` for the architecture, the engine's lockstep constraints (adding a stat/action touches multiple modules), and deployment notes.

Built with [opencode](https://opencode.ai) — an open-source AI coding CLI that wrote, tested, and iterated the codebase with a human in the loop.

## Disclaimer

`google-genai` requires a network call to the Gemini API. Free-tier quotas (~14.4K requests/day, 30 RPM) are more than enough for a 60 s tick; the server costs nothing while the bot is off.
