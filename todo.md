
# Terrarium Feature Roadmap: Stage 4 → 9

Respects the core philosophy: the LLM proposes intent only; the deterministic engine owns all consequences; state stays flat; everything remains offline-testable.

---

## Stage 4: Dynamic World Hazards & Dynamic Tiles

*Theme: the 5×5 map becomes a living, evolving landscape rather than a static backdrop.*

### 1. Wildfires & Fire Propagation

- [x] **Ignition triggers:** lightning during `Storm` (5% on a `🌲` Forest tile); Summer heatwave (10% if `wood_stock` high); Pyromaniac pawn during a `firesetter` break.
- [x] **Tile lifecycle:** `🌲 Forest` → `🔥 Burning` (3 ticks; drains 10 wood stock/tick; dangerous to enter) → `🌫️ Ash / Scorched Earth` → regrows to Meadow or Forest over 40 ticks.
- [x] `Interact` `flavor="extinguish"` / `"quench"` / `"douse"` on an adjacent tile puts out the fire before it spreads to adjacent Forest/Camp tiles.
- [x] `Chop` on an adjacent tile acts as a firebreak.
- [x] `map_renderer.py`: add colors for `"🔥"` (orange/red) and `"🌫️"` (dark charcoal).

### 2. Seasonal Disasters & Environmental Anomalies

- [x] **Flash floods (Spring Rain):** River tiles (`🌊`) temporarily expand to adjacent Meadow tiles for 3 ticks — foraging impossible, but +5 food stock deposited when the water recedes.
- [x] **Aurora Borealis (Winter Night):** clear Winter nights have a chance to trigger an Aurora — +10 colony-wide morale and an atmospheric LLM prompt line.
- [x] **Toxic Miasma / Spore Bloom (Autumn):** Swamps/Ruins emit toxic spores for 2 ticks — pawns on those tiles lose 5 HP unless wearing a `Warm Coat` (protective wrapping).

---

## Stage 5: Visitors, Caravans & Wandering Nomads

*Theme: the colony is no longer fully isolated — outside travelers pass through.*

### 1. Transient Visitor Entities (`world_state["visitors"]`)

- [ ] **Spawning:** once every ~150 ticks, a wandering NPC appears at the grid edge — Merchant (rare stocks: ~10 stone, ~10 fiber), Lost Wanderer (low HP/energy, seeks shelter), or Wandering Bard (performs at the campfire, +5 morale).
- [ ] **Visitor AI:** pathfind directly to Camp `(2,2)`, stay 3–5 ticks, then walk off the edge and despawn.
- [ ] `Share` food to a visitor → barter (e.g. give 2 food → receive 3 stone) or colony reputation.
- [ ] `Mate` or `Interact` `flavor="invite to stay"` / `"recruit"`: a high-sociability pawn has a chance to permanently recruit the wanderer as a colonist (respects `MAX_PAWNS`).
- [ ] `Attack` visitors → plunder their inventory, but non-aggressive pawns gain a `Guilt` moodlet (−5 morale).

---

## Stage 6: Base Megaprojects & Cultivation

*Theme: long-term endgame goals once shelter/fire/food are secured.*

### 1. Colony Megaprojects (The Great Work)

- [ ] Once Shelter (100), Campfire (100), Granary, and Palisade (3) are complete, `Build` unlocks **Monument Construction**.
- [ ] **Ancestral Monolith:** requires 20 Wood + 15 Stone, built progressively (5 wood/5 stone per Build action).
- [ ] **Passive effect on completion:** permanently anchors colony morale (floor of 10) and +2 insulation camp aura.
- [ ] **Inscription:** outside-lock LLM call writes a 1-sentence dedication; visible via `!monument` in Discord.

### 2. Agriculture / Garden Plots (Meadow Transformation)

- [ ] Meadow (`🫐`) tiles accept `Interact` `flavor="till soil"` / `"plant seeds"` / `"farm"` → tile converts to `🌾 Farm Plot`.
- [ ] Grows over 20 ticks (Spring/Summer only); guaranteed harvest of 15 Food + 5 Fiber without depleting natural biome stocks; halts in Winter.

---

## Stage 7: Colony Ideology, Traditions & Rituals

*Theme: emergent culture from what the colony has survived.*

### 1. Emergent Traditions (Culture Engine)

- [ ] Engine evaluates historical counters each season and auto-assigns a **Tradition Tag**: *Hunters of the North* (>10 predators slain → +2 combat XP when hunting; cold-weather penalties reduced by 1).
- [ ] *Children of the Forest* (>100 trees felled → +1 wood yield from Chop; shelter degrades slower).
- [ ] *Kindred of the Hearth* (>20 rations shared → social interactions grant +8 morale instead of +5).

### 2. Communal Festivals & Rituals

- [ ] **Seasonal Solstice Feast (Winter/Summer):** with >15 camp food on Day 1 of the season, pawns consume a feast — all gain +15 morale and a `Festive` moodlet (+5 for 15 ticks).
- [ ] **Funerary Rites:** on the death of a beloved pawn (high average relationships), survivors can `Interact` `flavor="bury"` / `"mourn"` / `"eulogize"` at the Ruins or Camp to halve the remaining `Grief` moodlet duration.

---

## Stage 8: Bandits, Raids & Hostile Outcasts

*Theme: high-stakes defensive events during late-game prosperity.*

- [ ] **Scavenger Raid (Autumn):** if the colony holds ≥30 combined food+wood, 1–2 hostile `scavenger_N` spawn at the grid edge.
- [ ] **Raider AI:** move directly to Camp to steal food from the Granary.
- [ ] **Defenses:** Palisade level slows bandit movement; tamed predators (`Wolf`/`Bear`) intercept bandits on the camp tile; high-combat pawns defend the stocks.
- [ ] Bandits flee once damaged or after stealing 5 food.

---

## Stage 9: The Autonomous World Engine (Dynamic Synthesis & Balance Patches)

*Theme: inspired by VRMMO autonomous game masters (e.g. Cardinal System) — dynamic recipe discovery, procedural world prophecies, safe balance tuning, and automated Discord "Patch Notes" without rewriting raw `.py` code.*

### 1. Data Model & Registries — `state.py`

- [ ] Add `world_state["custom_recipes"]` dictionary (stores AI-synthesized blueprints with material costs and primitive bonus keys).
- [ ] Add `world_state["active_quests"]` list (stores multi-tick procedural world prophecies/goals).
- [ ] Add `world_state["patch_version"]` string (`"v1.0"`, incremented each patch cycle).
- [ ] Add `world_state["biome"]["modifiers"]` dictionary (bounded tuning multipliers for regrowth, cold, and spawn rates).
- [ ] `_migrate_pawn` and `load_state` ensure backwards-compatibility for saves without Stage 9 keys.

### 2. Synthesis & Quest Engine — `engine.py`

- [ ] `_try_craft` checks both static `RECIPES` and `custom_recipes`, choosing the highest-tier affordable item.
- [ ] Custom tool bonuses seamlessly apply to `_do_attack` (combat) and `_do_forage` (scouting/fiber).
- [ ] Prophecy/Quest tracker in `resolve_actions` / `tick_environment`: evaluates conditions (e.g. kill species in season, stockpile threshold) → grants colony morale, custom titles, logs `quest_complete` event, and clears the quest.
- [ ] Balance multipliers apply safely to `REGROWTH`, `WEATHER_COLD`, and predator spawn rolls.

### 3. The Architect LLM Routine — `core.py`

- [ ] Triggered outside the lock every annual cycle (400 ticks / 4 seasons) or after major milestones.
- [ ] Schema `PatchUpdate`: outputs `patch_title`, `balance_changes`, optional `new_recipe`, `new_quest`, and bounded numeric deltas (`regrowth_delta`, `cold_delta`).
- [ ] Python enforces strict clamping on all balance deltas (e.g. net multipliers clamped strictly within `[0.7, 1.3]`).
- [ ] Emits `"patch"` event to event log and increments `world_state["patch_version"]`.

### 4. Discord Interface & Commands — `bot.py`

- [ ] Post formatted **"Terrarium Patch Notes vX.Y"** embed to Discord on new balance updates.
- [ ] Add `!recipes` command to inspect all base and synthesized blueprints.
- [ ] Add `!quests` / `!prophecies` command to view active world objectives and progress.
- [ ] Add `!patchnotes` command to view the latest autonomous balance notes.

### 5. Tests — `tests/test_stage9.py`

- [ ] Dynamic recipes load, persist, and auto-craft via `Build`.
- [ ] Custom equipment bonuses apply correctly to deterministic combat and foraging yields.
- [ ] World prophecy completion awards expected morale, titles, and event logs.
- [ ] Balance modifier deltas are strictly clamped within Python-enforced bounds regardless of LLM output.
- [ ] Old save files load cleanly with default empty custom registries.

---

## Starting point

- **Stage 4 (Wildfires & Tile Spreading)** — visual excitement & environmental danger.
- **Stage 5 (Visitors & Wandering Nomads)** — more social drama & pawn diversity.
- **Stage 9 (Autonomous World Engine)** — self-evolving VRMMO-style patch cycle.