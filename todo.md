# Terrarium Feature Roadmap: Stage 1 → 3

Respects the core philosophy: the LLM proposes intent only; the deterministic engine owns all consequences.

---

## Stage 1: Traits + Moodlets + Director Hints

**Status: DONE** — implemented in `state.py`, `engine.py`, `prompts.py`, `core.py`, `bot.py`; tested in `tests/test_traits.py`; docs synced (AGENTS.md, paper.tex).

### 1. Data model — `state.py`

- [x] Add `TRAITS` pool constant (Night Owl, Brawler, Pyromaniac, Pacifist, Iron Stomach).
- [x] `make_pawn`: add `traits=None` param — `None` rolls `random.sample(TRAITS, k=1 or 2)`; store `pawn["traits"]` (list of str).
- [x] `make_pawn`: add `pawn["moodlets"]` default `[]` (`{"name", "delta", "ticks_left"}` items).
- [x] `reset_world`: give the two founders fixed traits (deterministic world start).
- [x] `_migrate_pawn`: copy `traits`/`moodlets` if present in old saves, else fresh-roll traits.
- [x] Add transient `state.failed_intents = {}` (not persisted, like `god_orders`).

### 2. Traits — `engine.py` (all logic here, never in prompts/schema)

- [x] **Night Owl**: `_pay_cost` halves action cost at night (`max(1, cost // 2)` when `not is_day()`).
- [x] **Night Owl**: `_metabolize` morale block: `+2` at night / `−2` during day.
- [x] **Brawler**: `_do_attack` `+3` damage when `gear.main_hand is None`.
- [x] **Brawler**: `_metabolize` `−5` morale/tick while `main_hand` is set.
- [x] **Pyromaniac**: `_metabolize` `+5` morale when near a **lit** campfire.
- [x] **Pyromaniac**: `_break_archetype` returns `"firesetter"` when trait present.
- [x] **Pyromaniac**: `_resolve_break` handles `"firesetter"` — douse fire (`campfire −10`), else burn 2 inventory wood, else `shelter −5`.
- [x] **Pacifist**: `_do_attack` returns a `"failed"` "refuses to fight" event (no cost).
- [x] **Pacifist**: `_do_forage` and gather-Interact bucket get `+2` yield.
- [x] **Iron Stomach**: `_metabolize` hunger drain `2 → 1`.
- [x] **Birth inheritance**: `_give_birth` child inherits one trait from each parent (50% each), top up with random roll to ≥1 trait.

### 3. Moodlets — `engine.py`

- [x] `_add_moodlet(pawn, name, delta, ticks)` — dedupe by name (refresh + replace).
- [x] `_tick_moodlets(pawn)` — decrement `ticks_left`, drop expired, return summed delta.
- [x] `_metabolize` calls `_tick_moodlets` and adds the sum into the morale delta block.
- [x] Hook `_kill` → all living pawns get `Grief (−10, 10 ticks)`.
- [x] Hook `_metabolize` frostbite → `Frostbitten (−5, 10 ticks)`.

### 4. Director hints

- [x] `resolve_actions`: on a returned `"failed"` event with a feasibility reason (`low_energy`, `need_wood`, `wrong_tile`, `forest_depleted`, `food_depleted`, `too_far`, `target_down`, `off_grid`, `pacifist`), increment `state.failed_intents[pid]`; success resets it. God orders are exempt.
- [x] `prompts.build_prompt`: for count ≥ 2 append `Director note: {name} tried {action} but {reason} — choose a feasible action.`
- [x] `prompts.SYSTEM_PROMPT`: add rule that traits are fixed — never propose changing them.

### 5. Display

- [x] `prompts.build_prompt` pawn line: add `Traits {traits}` and `Mood: Grief(−10) Frostbitten(−5)`.
- [x] `core.post_to_discord`: compact trait tags (e.g. `🦉 Night Owl`) on the pawn name line.
- [x] `bot._pawn_line`: trait tags + active moodlets (used by `!list` / `!status`).

### 6. Tests — `tests/`

- [x] Night Owl: halved action cost at night.
- [x] Brawler: unarmed `+3` damage; morale penalty while a tool is equipped.
- [x] Pacifist: Attack → refused event, no energy cost; forage `+2` bonus.
- [x] Iron Stomach: hunger drains 1/tick.
- [x] Pyromaniac: `+5` morale near lit fire; break → `firesetter` douses the fire.
- [x] Moodlets: add/dedup, tick decay, sum into morale.
- [x] Grief moodlet applied to living pawns on death.
- [x] Director hints: counter increments after 2 failed intents; prompt contains the note; resets on success.
- [x] Migration: trait-less old pawn dicts load with defaults.

### 7. Sync

- [x] `paper.tex`: add a representative trait/moodlet line to the `lst:engine` excerpt; keep prose claims truthful.
- [x] `AGENTS.md`: document traits, moodlets, `failed_intents`; extend the "adding a stat" touch list.

---

## Stage 2: Fauna & Wildlife (Living Ecosystem)

### 1. Data model — `state.py`

- [x] Add `world_state["wildlife"]` top-level list (default `[]`); `load_state` `setdefault`.
- [x] `make_animal(species)` factory: `{"id": "wild_1", "species", "pos": [x,y], "state": "wandering", "hp", "spawn_tick", "tamed_by": None}`.
- [x] `next_wild_id()` helper.
- [x] Add transient `state.god_orders`-style extension for wildlife targets if needed (or reuse).

### 2. Species table + AI — `engine.py`

- [x] `WILDLIFE` table: per species `{emoji, kind (prey/predator), hp, food_yield, fiber_yield, bite_damage}`. Deer/Rabbit = prey; Wolf/Bear = predator.
- [x] Spawn logic in `tick_environment`: Winter/Autumn → predator chance; Spring/Summer → prey chance; cap 1–3 entities.
- [x] Prey AI: flee nearest pawn within Manhattan distance 2 (deterministic move).
- [x] Predator AI: stalk the pawn furthest from Camp (Manhattan); fixed tiebreak for tests.
- [x] Predator bite: same-tile pawn takes damage (incapacitation only, never death — consistent with combat).
- [x] Wildlife HP decay / despawn: predators despawn at season change or when world extinct; prey despawn chance.
- [x] `render_grid`: draw wildlife markers (🦌/🐺) combined with pawn occupancy.

### 3. Hunting & taming — `engine.py` + `schema.py`

- [x] `schema.build_models`: extend `target` Literal to `pawn_ids + wildlife_ids`.
- [x] `_do_attack` handles wildlife targets: damage → kills → yields **food + fiber** (no new "meat" resource); prey flee on hit; predator may retaliate.
- [x] `_do_interact`: `"tame"/"feed <species>"` flavor → skill-based tame roll → pet (camp-wide passive morale bonus in `_metabolize`).
- [x] Tamed pet counts toward wildlife cap; renders at camp.

### 4. Infrastructure — `engine.py`

- [x] **Granary**: `biome["granary"]` flag; `Build` upgrades it after shelter+campfire maxed; prevents Summer food_stock decay.
- [x] **Palisade**: `biome["palisade"]` level; `Build` upgrades it; reduces predator spawn chance.

### 5. Discord — `bot.py`

- [x] `!order ... Attack <animal>` — extend target resolution to wildlife names/ids.
- [x] New `!wildlife` command to list fauna on the map.

### 6. Tests — `tests/`

- [x] Spawn determinism (season-gated, capped).
- [x] Prey flees nearest pawn.
- [x] Predator stalks furthest-from-camp pawn.
- [x] Predator bite incapacitates (never kills).
- [x] Hunt: Attack on wildlife yields food/fiber.
- [x] Tame roll + camp morale bonus.
- [x] Granary stops Summer food decay.
- [x] Palisade reduces predator spawn.
- [x] Migration: old worlds without `wildlife` load clean.

### 7. Sync

- [x] `paper.tex`: reflect fauna/species/hunting in the `lst:engine` excerpt + prose claims (season-cycle figure unaffected).
- [x] `AGENTS.md`: document wildlife, hunting, taming, granary/palisade.

---

## Stage 3: Community & Lorekeeper

**Status: DONE** — implemented in `state.py`, `engine.py`, `core.py`, `bot.py`, `prompts.py`, new `map_renderer.py`; tested in `tests/test_stage3.py`; docs synced (AGENTS.md, paper.tex).

### 1. Seasonal chronicle — `core.py` + `engine.py`

- [x] `world_state["chronicle"]` list: `{"season", "title", "text", "tick"}`; `load_state` `setdefault`.
- [x] `tick_environment` returns/exposes a "season changed" signal (it already emits a `"season"` event).
- [x] `core._chronicle_season()`: async LLM call **outside the tick lock** (clone of `_eulogize_fallen`, `schema_model=None`) producing a 1-paragraph season summary.
- [x] Title generation: LLM writes a 2–4 word era title (e.g. "The Winter of the Great Wolf").
- [x] Emit a `"chronicle"` event + include in the event log for the paper dataset.

### 2. Heirlooms & relics — `engine.py`

- [x] `world_state["heirlooms"]` list: `{"id", "name" (e.g. "Willow's Flint Spear"), "stat_bonus", "moodlet_delta", "source"}`; `load_state` `setdefault`.
- [x] `_kill`: if the fallen pawn had a title and a `main_hand` tool, drop an heirloom (owner released if the holder dies).
- [x] `_do_interact`: `"claim"/"inherit <heirloom>"` flavor → equips it (+1 skill / damage bonus) and grants a positive moodlet.
- [x] `render_grid` / `!list` shows owned heirlooms.

### 3. Pawn adoption — `bot.py` + `core.py`

- [x] `world_state["adoptions"]`: map `discord_user_id → pawn_id`; `load_state` `setdefault`.
- [x] `!adopt <name|pawn_id>` command (any channel) — binds the invoking user.
- [x] `!unadopt` / `!my` commands to list adoptions.
- [x] Notification hook: `core` scans the tick's events (`birth`, `goal`, `break`, `death`) and calls a notifier registered by `bot.on_ready` — DMs via the gateway client (webhook can't DM).
- [x] Notifier sends a DM: birth, goal fulfilled, mental break, or death of the adopted pawn.
- [x] Engine stays pure — no Discord logic in `engine.py`.

### 4. Graphical map renderer (optional)

- [x] Pure-Python PNG writer (zlib/struct, ~60 lines, no Pillow dependency) rendering the 5×5 grid + pawns + wildlife.
- [x] Attach to the webhook embed via multipart (`attachment://map.png`).
- [x] Fallback to ASCII grid when no webhook is configured.

### 5. Tests — `tests/`

- [x] Chronicle: season-change detection triggers chronicle queue; stored entry shape.
- [x] Heirloom: death of a titled pawn drops an heirloom; `Interact` claim equips it.
- [x] Adoptions: mapping persist/load; notifier called on matching events (mock the notifier).
- [x] Map renderer: produces a valid PNG header (pure-Python writer).

### 6. Sync

- [x] `paper.tex`: reflect chronicle, heirlooms, adoptions in prose/claims (no new listings needed unless mechanics change).
- [x] `AGENTS.md`: document chronicle, heirlooms, adoptions, notifier hook, PNG map.

---

## Cross-stage verification

- [x] `ruff check . && python -m pytest tests -q` — all offline tests pass after every stage.
- [x] `python -m py_compile <edited>.py` for every touched module.
- [ ] Git commit per stage (or per coherent chunk). — left to the user
- [x] Old save files load and auto-migrate at each stage (`terrarium_state.json`).
- [x] `paper.tex` claims match the implementation at every stage (executable-source-of-truth counterpart).
