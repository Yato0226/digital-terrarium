# Terrarium Feature Roadmap

> **Status:** Phases 1–5 and Phase 6 Steps 1–5 are **implemented & shipped** (archived below).
> **Active:** **Phase 6 Step 6+ — The Gorgeous Diorama** (visual-polish pass) — work in progress.

---

## ✅ Completed blueprint (archived — all shipped)

### Phase 1: Streamline Discord into a Milestone News Hub
*Goal: Stop every-minute embed spam and turn Discord into a clean newspaper of major colony events.*
- [x] **Step 6: The Milestone Announcement System** — milestone-only embeds (season chronicle, eulogies, patch notes, crisis alerts, adoption DMs).

### Phase 2: Living Memory, Biographies & Generational Sagas
*Goal: Turn the event log into deep historical memory that persists across generations.*
- [x] **Step 7: The Pawn Biography Engine (`!bio <name>`)** — on-demand 3-sentence sagas/obituaries from the event log.
- [x] **Step 8: Generational Handoffs & Dynasties** — G2/G3 succession; graves, heirlooms, and deeds persist in prompts.
- [x] **Step 9: The Monolith as an Oracle & Rune Archive** — achievements carved as runes; prayers grant visions/warnings.
- [x] **Step 10: Ancient Pre-History (The Lost Tribe)** — Ruins = Sunken Tribe remnants with lore fragments and blueprints.

### Phase 3: Social Dynamics, Factions & Dynamic Roles
*Goal: Transform flat relationship numbers into living social drama and emergent governance.*
- [x] **Step 11: Qualitative Relational Badges** — *Lifesaver / Betrayer / Indebted / Mentor / Widow* badges woven into narratives.
- [x] **Step 12: Multigenerational Blood Feuds** — rivalries inherited at birth; peace via courtship/sharing or escalation.
- [x] **Step 13: Free-Form Dynamic Roles with Keyword Bucketing** — organic job titles grant subtle keyword-based perks.
- [x] **Step 14: Annual Camp Council & Colony Mandates** — yearly leader + 1-sentence Colony Mandate for unified focus.

### Phase 4: Living Ecosystem, Cataclysms & Exploration
*Goal: Make the wilderness dynamic, reactive, and dangerous.*
- [x] **Step 15: Trophic Cascades (Food Chain Ecology)** — over-hunting → overpopulation → crop damage; clear-cutting → harsher winters/floods.
- [x] **Step 16: Persistent Named Legendary Beasts** — escaped predators gain names/reputation (*The Grey Terror*) and revenge hunts.
- [x] **Step 17: Fog of War & Off-Grid Expeditions** — mist-shrouded rim; scouting + paired rations-packed expeditions.
- [x] **Step 18: Multi-Tick Seasonal Cataclysms** — *The Long Winter*, *The Great Drought*.

### Phase 5: Emergent Mythology, Religion & Full Interconnection
*Goal: Connect all systems into a self-sustaining, emergent civilization saga.*
- [x] **Step 19: Dynamic Colony Identity & Taboos** — evolving community name; fear-based taboos (e.g. shunning the Ruins).
- [x] **Step 20: The Voice in the Sky & Camp Shrines** — frequent god-whisper recipients become Prophets; shrines + offerings.
- [x] **Step 21: Physical Folklore & Herbal Medicine** — cave murals/totems with positive moodlets; medicinal herb salves.
- [x] **Step 22: The Domino Effect (Total Interconnection)** — full causal loop closed (hazard → fire → morale → break → grave → legend → tradition).

### Phase 6: The Live Isometric Visual Engine & Discord Activity
*Goal: Turn the simulation into a real-time, 60 FPS floating diorama viewable inside Discord voice channels.*
- [x] **Step 1: Lightweight State Broadcast** — WebSocket feed broadcasting a clean JSON snapshot per tick (tiny RAM footprint).
- [x] **Step 2: The Floating Isometric Diorama Client** — 5×5 grid as a cutaway island cube; walk interpolation (0–4s), bubbles (4–12s), looping action animations (12–60s), continuous particles.
- [x] **Step 3: Comic Speech & Thought Bubbles** — speech `quote` bubbles, `inner_monologue` thought clouds, status emotes.
- [x] **Step 4: Full Interactive On-Screen Dashboard (HUD)** — snapshot extensions (resources aggregate, dossier fields, lore payloads) + client HUD (top bar, narrative log, click-to-inspect dossiers, lore archives).
- [x] **Step 5: ngrok Tunnel & Discord Activity Embedding** — static domain `budget-universe-manila.ngrok-free.dev`, Rocket Activity icon launch, no URL rotation.

---

## 🎨 Phase 6 (continued): The Gorgeous Diorama — Visual Polish Pass
*Goal: Take the working diorama from "small flat sticker in a black void" to a cozy, close, polished indie-game look — scale/depth, real sprites, un-stacked pawns, a framed RPG HUD, and ambient juice.*

### Step 6: Scale, Depth & the Floating-Island Look
- [x] **Zoom the camera in**: scale the board so the 5×5 island fills ~55–65% of the screen height — cozy, close, and detailed instead of tiny and far away.
- [x] **3D thickness**: below the grass edge add a 20–30 px dirt drop, dark rock strata, and dangling roots → a real floating diorama cube (upgrade the current flat cutaway diamonds).
- [x] **Soft ground shadow**: blurred dark oval beneath the floating island for elevation + lighting.
- [x] **Atmospheric background**: replace the pitch-black void with a deep gradient (e.g. midnight navy on a Winter Night), faint twinkling stars, and a distant mountain silhouette.

### Step 7: Procedural Pixel-Art Sprites (supersedes the Kenney-pack plan — user chose procedural art)
*Decision (plan.md): hand-authored pixel maps in JS drawn with nearest-neighbor scaling — keeps the "offline, zero runtime downloads, tiny" ethos; no external assets to vendor or attribute.*
- [x] **`web/sprites.js` sprite factory + palettes**: `makeSprite(rows, palette)` rasterizes string grids to offscreen canvases; deterministic hashing for per-tile noise; `imageSmoothingEnabled=false` crisp scaling; exposed as `window.Sprites` (loaded before `app.js`).
- [x] **Ground textures + object sprites**: coarse 28×14 textures (grass/water/rock/dirt/ash/scorch/farm) upscaled 6× and clipped to the iso diamond + pixel sprites — pine 🌲, rock pile 🪨, ruin wall 💀, tent 🏕️, campfire logs, farm sprouts 🌾, ash mound 🌫️, berry bush 🫐, lily pad 🌊 — cached per tile and rebuilt only when the grid changes.
- [x] **Rewire `drawIsland()`**: pre-rendered tile sprites replace the colored diamonds + emoji glyphs; water shimmer, wildfire flame/glow, and the campfire flame (2-frame animated) stay live per-frame.
- [x] **Pawn sprites**: standing pixel characters (sex/elder/child + hue variants, idle/walk) — Part C.
- [x] **Fauna / visitor / raider sprites** + **4-frame animated campfire** — Part D.
- [ ] **Attribution**: n/a (procedural, zero external assets — note this in `README.md`).

### Step 8: Fix the Stacked-Pawn Blob & Clean Up the Sprites
- [x] **Isometric slotting**: multi-pawn tiles arrange in a tiny triangle/diamond formation inside the tile (top-left, bottom-right, top-right…) instead of one overlapping blob at the same pixel.
- [x] **Standing sprites**: replace the circular portrait tokens with standing character sprites that stand on the grass.
- [x] **Hovering name tags**: show names on hover (or crisp small name pills under each pawn's feet) instead of always-overlapping labels.
- [x] **Per-pawn bubbles**: speech, thought, and 💤 sleep icons float above the *individual* sprite (honoring the slot offset), not covering the whole tile.

### Step 9: Frame the Game — HUD Upgrade
- [x] **Top bar (world header)**: styled wooden/slate banner background; slightly larger resource icons with clear numbers + tooltips; subtle frost texture along the top/bottom edges in Winter.
- [x] **Right-side pawn roster drawer**: a clean sidebar with a mini card per colonist — portrait, name, mini health bar, energy bar, current action — at-a-glance status without squinting at the map.
- [x] **Bottom-left chronicle log**: RPG dialogue-parchment or dark-glass card styling; highlight the AI Director's world narrative with an accent color/italic, distinct from dry action lines like *"Fern moves W"*.

### Step 10: Ambient Visual Juice
- [x] **Drifting snow FX**: lightweight canvas particle layer dropping soft white snowflakes when it's Winter / Snow.
- [x] **Night campfire glow**: warm soft orange radial glow on the tiles immediately around the camp while the outer forest stays in shadow.
- [x] **Named legendary beasts**: named predators (e.g. *The Grey Terror* from the log) render as a menacing dark sprite (dark palette variant of their species) distinct from normal wildlife — landed with Part D.

### Step 11: Corner Chat Box (tester feedback — dialogue instead of floating bubbles)
- [x] **Bottom-right chat box**: pawn speech (`quote`) and thoughts (`inner_monologue`) land as colour-coded chat rows (name chip tinted by pawn hue, thoughts italic/dimmer) in a bottom-right panel — deduped per `pawnId@tick:kind`, capped at 8, auto-hidden when empty, cleared on world reset. Floating speech/thought bubbles removed (`#bubbles` layer, `addBubble`, per-frame bubble lift); per-tick status emotes and 💤/🌀/🤰 badges stay. (Also: hotfix for a roster-bar class mismatch that froze the live UI, plus `tests/smoke_client.js` + `tests/test_web_client.py` regression harness.)

### Step 12: Top-Down Sprite World (vendored LimeZu Serene Village tileset)
*Decision (plan.md, 2026-08-17): replaces the floating-island cube with a flat top-down game-board view. World art is vendored from the free CC-BY 4.0 pack "Serene Village — revamped" by LimeZu (3 PNGs, ~87 kB — no runtime downloads). Pawns/creatures/visitors/raiders stay procedural (`sprites.js`). Emoji stay in HUD/UI. Tile map user-verified in GIMP and locked (see `web/TILES.md`).*
- [x] **Vendor assets + attribution**: copy `Serene_Village_16x16.png`, `campfire.png`, `water_waves.png` → `web/assets/`; `web/assets/ATTRIBUTION.md` (LimeZu, CC-BY 4.0, source link, date); credit line in `atlas.html` footer.
- [x] **`web/atlas.js` tile atlas**: image loader + named slice table (`Atlas.slice`/`Atlas.scaled`/`Atlas.ground`/frame strips) with all user-verified pixel boxes — trees, bush, flowers, cottage, rocks, ruins, dirt, water+shore, fences, path, well (two-part).
- [x] **`web/atlas.html` contact sheet**: labeled 19×45 master-sheet grid + campfire/water frames (dev tool + user reference).
- [ ] **`README.md` + `paper.txt` attribution**: Serene Village credit line + client-description update (same part/commit as the code).
- [x] **Part B — top-down terrain renderer**: replace iso geometry with `TILE=128` top-down (`top(x,y)`), rewrite `drawIsland()` → `drawWorld()` (backdrop + board frame + vendored ground + shore transitions + farm/ash/scorch + seasonal tint), 14-frame water animation. *(Bank lips are procedural — the pack's sand "coast band" is a diagonal beach, not axis-aligned river banks; `Atlas.ground()` caches 16×16 tiles internally, no separate grid-signature cache.)*
- [x] **Part C — standing objects + y-sort**: DOM object layer (trees/bush/rocks/ruins/cottage+campfire/well/fences), y-sorted z-index by footprint, wildfire flame/glow. *(New module `web/objects.js`; depth-z is a bounded `4 + round((anchorY−150)/20)` band that stays below the z-40 HUD panels; layer defers until `Atlas.ready`.)*
- [ ] **Part D — pawns/creatures top-down**: tile-center anchors, compact slot offsets, walk interpolation/action bobs/emotes/badges/hover pills preserved.
- [ ] **Part E — ambient effects pass**: campfire smoke + night glow, snow veil, night tint, river shimmer adapted to top-down.
- [ ] **Part F — docs + smoke tests**: `plan.md`/`todo.md` ticks, README client-look update, paper §Implementation sync, `AGENTS.md` Phase 6 paragraph, `tests/smoke_client.js` geometry/atlas assertions, full verify suite green.

### Cross-stage verification (each part: implement → test → commit)
- [x] Commit per checkbox above, one `todo.md` tick per part; run `ruff check . && python -m pytest tests -q` after each part (Python unchanged — suite must stay green).
- [x] `node --check web/app.js` on touched client JS.
- [x] Keep `README.md` (feature/run notes) and `paper.txt` (client description in §Implementation) in sync in the same part/commit.
- [ ] Live sanity check after the pass: open `https://budget-universe-manila.ngrok-free.dev/` (or the Rocket Activity in a voice channel) and confirm the zoom, sprites, slotting, HUD, and snow/glow all render.

---

This step-by-step blueprint takes you from the core visual setup to an unforgettable, living autonomous civilization simulation!
