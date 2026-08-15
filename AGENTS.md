# AGENTS.md

LLM-driven "digital terrarium" simulation: Gemma (hosted via the Gemini API) narrates, Discord lets a "god" intervene. Single-package Python app, no framework.

## Commands

- Verify everything: `ruff check . && python -m pytest tests -q` (70 tests, fully offline — no API/Discord needed; tests never import `llm.py`).
- Syntax check a single file: `python -m py_compile <file>.py`.
- Run the live bot: `python main.py` — requires `.env` with `DISCORD_BOT_TOKEN` (and webhook if embeds wanted) plus a `GEMINI_API_KEY` from Google AI Studio. No local Ollama. Bot needs **Message Content Intent** enabled in the Discord Developer Portal.
- Auto-start on the LXC: `deploy/terrarium.service` (systemd, `Restart=always`, SIGINT for clean state save) → copy to `/etc/systemd/system/`, `systemctl daemon-reload && systemctl enable --now terrarium`, logs via `journalctl -u terrarium -f`. `WorkingDirectory` must be the project dir (state/log/.env are relative paths). On Proxmox also set **LXC → Options → Start at boot** so the bot returns when the host powers on.
- Config is `config.py` (env vars via `.env`/python-dotenv), not hard-coded.

## Architecture (read before editing)

- **The LLM proposes intent only.** Output schema (`schema.py`, rebuilt each tick for active pawns) is `{action, narrative, quote, inner_monologue, direction, target}`. **Never** let the LLM send stat numbers.
- **`engine.py` is the sole source of truth for consequences**: action costs (`ACTION_COSTS`), combat, skill XP, relationships, incapacitation/recovery, crafting, mental breaks, environmental death. Changing mechanics means editing `engine.py` — not prompts or schema.
- **Flow:** `core.run_tick()` → build schema → LLM → build intents (god orders override; Move maps `direction` into the intent) → `engine.resolve_actions()` → `engine.tick_environment()` (metabolism/seasons/weather/campfire/regrowth/break counters/aging/death→graveyard) → events → `tick += 1` then save (persists the advanced tick — never increment after save) → **lock released** → eulogy LLM + Discord embed run outside the lock.
- **LLM provider is `llm.py`** (hosted Google Gemini API, no local model): `generate_with_fallback(system, user, schema_model, temperature)` tries `GEMINI_MODEL` (`gemma-4-31b-it`) then `GEMINI_FALLBACK_MODEL` (`gemma-4-26b-a4b-it`), returning `(text, model_used)`. Ticks pass the per-tick Pydantic model as `response_schema`; eulogies call it with `schema_model=None` (freeform prose). Free-tier quotas: 30 RPM / 16K TPM / 14.4K RPD (reset midnight Pacific) — a 60s tick uses ~10% of the daily RPD. **On hosted Gemma the `response_schema` is what forces clean JSON and disables the thinking channel** (`response_mime_type` alone is ignored); `thinking_level="MINIMAL"` is set as an extra guard. If you hit the SDK 500 "alias" bug on a Gemma model, prefix the model id with `models/` (e.g. `models/gemma-4-31b-it`).
- Actions are exact strings `"Chop" | "Rest" | "Scout" | "Attack" | "Forage" | "Build" | "Share" | "Move" | "Mate"`. `target` is only valid for Attack, Share, or Mate (Attack/Share same-or-adjacent tile, Mate same tile); `direction` (N/S/E/W) only for Move; engine rejects missing/self/down/unknown/far targets.
- The world is a fixed 5×5 grid (`state.DEFAULT_GRID`, `world_state["grid"]`): Camp (2,2), Forest on the edges, Meadow/River for forage, Ruins (rich, risky scout), Quarry (stone). Chop/Forage/Build are tile-gated; a lit campfire warms only within Manhattan distance 1 of Camp. Pawns carry `pos [x,y]` and `engine.render_grid()` draws the emoji map.
- The shared `world_state["biome"]` block (`season`, `weather`, `day`, `campfire`, `shelter`, `wood_stock`, `food_stock`) ages in `engine.tick_environment()` — it is never modified by prompts or schema. Environment constants (season length, drain rates, regrowth) live in `engine.py`.
- **Adding a stat/resource touches all of:** `state.make_pawn` + `state._migrate_pawn` (old saves auto-migrate), `state.DEFAULT_BIOME` for biome fields, `prompts.build_prompt`, `engine` resolution, `core.post_to_discord`, and optionally `bot.god_edit`. Adding an **action** touches `schema.ACTIONS` (Literal) and `engine.ACTION_COSTS` in lockstep — `bot.order`'s whitelist derives from `engine.ACTIONS`, so it follows automatically.

## State & persistence

- `world_state` in `state.py`: `{tick, history, biome, graveyard, grid, pawns}`. Pawn shape is nested (`vitals.hp`, `inventory.{wood,food,stone,fiber}`, `gear.{main_hand,body}`, `counters.*`, `title`, `job`, `sex`, `pregnant_ticks`, `child_ticks`, `pos`, `mental_break`, `skills.*`, `relationships.*`, `status`), not flat. `biome` holds shared environment state (`season`, `weather`, `day`, `campfire`, `shelter`, `wood_stock`, `food_stock`); `grid` holds the 5×5 tile map. Environmental death (Blizzard freeze, `starving_ticks > 5`, or old age) removes a pawn into `graveyard` snapshots (`{id, name, title, cause, died_tick, born_tick, epitaph}`) — combat 0 HP stays recoverable `incapacitated`.
- Tools are crafted via the Build action at Camp (auto-crafts the highest-tier affordable item from `engine.RECIPES`): Stone Axe (3W+2S, doubles Chop), Flint Spear (2W+1S, +4 Attack), Warm Coat (5F, +4 insulation). Stone comes from the Quarry/Ruins scout; fiber from Meadow forage.
- Mental breaks: morale ≤ 0 starts a 3-tick break by personality (aggression ≥6 → berserk, bravery ≤3 → paranoid, else apathetic); `resolve_actions` forces the break behaviour and `tick_environment` counts it down.
- Reproduction: pawns carry `sex` (M/F). `Mate` (cost 10) succeeds only on the same tile with an opposite-sex active pawn whose relationship to the suitor is ≥ 25 (`MATE_RELATIONSHIP`); a starving female can't conceive and the colony caps at `MAX_PAWNS` (10). On a 50% roll the female gains `pregnant_ticks` (20 = 1 day); `tick_environment` counts pregnancy down and calls `_give_birth` (newborn: weaker HP/energy, `child_ticks` 40 = 2 days before it can mate, auto name/job/sex from the state pools). Children can't court or be courted; a birth that comes due while the colony is at cap re-delays the pregnancy rather than losing it.
- Aging: age is derived (`tick - born_tick`, no stored field — `engine.age_of`/`engine.is_elder`; `TICKS_PER_DAY` = `DAY_CYCLE` = 20, one sim day per 20 ticks — display/LLM-facing ages use `tick // TICKS_PER_DAY`). At `ELDER_AGE` (200 = 10 days) a pawn becomes an elder: `_metabolize` drains +1 energy/+1 morale per tick, `_do_rest` heals −5 less, and `_update_titles` names them "the Ancient". `_death_cause` adds old age after the blizzard/starvation checks — 2% per tick once elder, guaranteed at `OLD_AGE_MAX` (320 = 16 days).
- `terrarium_state.json` auto-saved each tick and on god commands; auto-loaded/migrated on startup.
- `terrarium_log.jsonl` — append-only structured event log (the paper dataset). Events are dicts `{tick, type, actor, target, data, description}`; `history` is a ring buffer (`MAX_HISTORY=10`).
- `.env`, `terrarium_state.json`, `terrarium_log.jsonl` are gitignored — never commit secrets.

## Concurrency (easy to break)

- `core.tick_lock` serializes ticks and state mutation. **Any Discord command that mutates `world_state` must wrap its body in `async with core.tick_lock:`** (see `bot.py`). `run_tick` holds the lock only for deterministic mutation + save, then releases it for the eulogy LLM and Discord webhook so god commands aren't stalled by network I/O.
- `pause_event` gates the scheduler; single `tick_loop` task is created in `bot.on_ready` with a reconnect guard — don't add a second one. Extinction is durable: `_notify_extinction` sets `world_state["extinct"]` (persisted) and clears `pause_event`; `load_state` keeps a dead world with a graveyard instead of force-respawning it.

## Gotchas

- **Python 3.10** (not 3.11+): `Literal[*ids]` unpacking is unavailable — use `Literal[tuple(pawn_ids)]` (valid per PEP 586) in `schema.py`.
- Roster changes are reflected by the schema being rebuilt every tick — no schema edits when adding/removing pawns.
- Tests reset the world and set `events.LOGGING = False` via the `fresh_world` fixture; run `resolve_actions` against `state.world_state["pawns"]` directly.
- The god `!say` is a whisper in the prompt **and** grants +15 morale (a god effect applied in `bot.say`); `!order` is enforced by the engine override. Don't blur these.

## Paper (paper.txt)

- `paper.txt` is a **pdflatex document for Overleaf**, not prose/markdown. Keep edits valid LaTeX (escaping `%`, `&`, `#`, math as needed); don't reformat it as markdown.
- Its `lstlisting` blocks are condensed excerpts of the real modules (in `§Implementation Code`) — keep them in sync when `schema.py`/`engine.py`/`core.py` mechanics change.
- Figures are pure TikZ (`\usetikzlibrary{arrows.meta, positioning}`) — no external image files, so the paper compiles on Overleaf without uploads. Keep them in sync with the architecture (Fig 1), per-tick flow (Fig 2), and season cycle (Fig 3).
- Tables and claims in the paper must match the implementation (see Architecture/engine above); it's the paper's executable-source-of-truth counterpart.
