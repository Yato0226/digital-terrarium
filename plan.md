# Plan — Phase 6 Step 6+: Top-Down 2D Sprite World (vendored Serene Village tileset)

> **This file is the working plan + continuity anchor.** Update it after every part
> lands (tick the boxes, note decisions). If the conversation gets compacted, read
> this file first — it holds the current state, decisions, and next steps.
> Canonical feature checklist stays in `todo.md` (one `[x]` per committed part).

---

## Current status (updated: decision reversed — procedural → vendored sprite pack)

- **Decision — pixel art source: VENDORED.** Reverses the earlier *procedural pixel
  art* decision. User chose a real sprite pack for the world rendering: **LimeZu
  "Serene Village — revamped"** (free, CC-BY 4.0) — the exact cozy-cottage
  aesthetic smallville's own town map references. Asset acquired:
  `Serene_Village_revamped_v1.9.zip` (622 kB, downloaded to
  `D:\FDM\Serene_Village_revamped_v1.9.zip`; extracted working copy in
  `%TEMP%\opencode\serene\extracted\`).
- **Decision — what gets vendored art:** the **world rendering** — terrain
  (grass/water/rock/dirt), standing objects (trees, bushes, rocks, cottage,
  campfire, well, fences), overlays (farm/ash/scorch, animated water + flame).
  **Pawns, wildlife, visitors, raiders stay procedural** (`sprites.js`) — the pack's
  characters come from the paid *Modern Interiors* set, and our hue-varied pixel
  pawns already match the top-down scale. Emoji stay in HUD/UI (unchanged policy).
- **The visual style changes from iso floating island → flat top-down** (Stardew /
  smallville style): a bordered game-board view of the 5×5 grid, y-sorted sprites.
  This reverses the "floating island cube + atmospheric sky" look from Parts A–H.
- **Attribution required (CC-BY 4.0):** add a credit to `README.md`, `paper.txt`,
  and a small credit line in the client (footer of `atlas.html` + a "🗺️ art" note in
  the HUD tooltip or index). See the license section below.
- Vendored files (all tiny): `Serene_Village_16x16.png` (304×720 = 19×45 tiles of
  16×16, 85 kB), `campfire.png` (64×16 = 4 frames), `water_waves.png` (224×16 =
  14 frames). Total ≈ 87 kB.
- `node` is available (v22.18.0) for `node --check` on client JS.

## What the sheet contains (verified by ASCII tile-dump so far)

Master sheet `Serene_Village_16x16.png`, tile grid 19 cols × 45 rows, tiles at
(col,row):

- **Grass:** solid flat grass (5,0); grass textures rows 29–30 and 33–34.
- **Water:** open water (1,37); water-with-edge (0,37)/(0,38)/(1,38); grass↔water
  coast autotiles (1,1)/(2,1)/(1,2) and the coast-blend band rows 9–19.
- **Rock/cliff:** boulders/stone mounds (1,15),(2,15),(3,15); cliffs (0,18),
  (0,19), (1,28),(2,28); rock bands rows 35–36 and 43–44.
- **House/cottage:** wall tiles row 23 (cols 0–5), roof tiles row 24 (cols 0–2,
  gray + yellow trim), soil/foundation rows 25–26. Exact 2×2 composition to be
  confirmed visually.
- **Farmland:** striped tilled soil (0,21),(1,21),(2,21),(0,22),(1,22),(2,22)
  and rows 25–26.
- **Well:** (0,20). **Fences:** (4,15),(5,15),(4,16). **Bridges/planks:** (4,18)+.
- Animated: `campfire.png` 4 frames, `water_waves.png` 14 frames.

### ✅ Atlas LOCKED (user-verified in GIMP, 2026-08-17) — see `web/TILES.md`
All slices are pixel boxes into `Serene_Village_16x16.png` (304×720 = 19×45 tiles):

- **Trees 🌲 (3 variants):** `(144,201,32,39)`, `(177,201,32,39)`, `(208,201,32,39)` —
  rounded leafy canopies + trunks. V1/V2 near-identical greens, V3 blue-tinted.
- **Bush 🫐:** `(113,194,14,14)` rounded green bush. **Flowers:** `(65,194,14,13)`.
- **Cottage 🏕️ (complete pre-composed):** `(87,404,67,55)` — roof, door, windows,
  stone foundation, yard. Scale to ~128px wide for the camp tile.
- **Rocks 🪨:** `(3,298,24,22)` — 2-rock overlay (fine at scale).
- **Ruins 💀:** `(0,48,47,32)` — scatter of small gray stones (rubble).
- **Dirt 🌾:** `(96,16,12,48)` — brown soil strip; furrows painted procedurally.
- **Water 🌊:** `(141,84,8,8)` flat blue. **Shore N** `(59,67,74,14)`, **S** `(59,94,74,14)`,
  **E** `(126,75,12,29)`, **W** `(55,75,12,29)`.
- **Fence:** H rail `(64,276,48,11)`, V post `(102,244,4,43)`. **Path:** `(35,158,26,15)`.
- **Well ⛲:** round top `(191,530,8,7)` + bottom `(192,537,6,4)` — stack exactly these
  two (a wider crop catches the cottage roof).
- **Not in pack:** campfire (keep `campfire.png` 4-frame), sprout row (procedural).

## Client file map (current)

- `web/index.html` — HUD bar, gauges, stock chips, stage (canvas+sprites+emotes+
  chat+log), dossier panel, roster drawer, lore panel. Loads `sprites.js` + `app.js`.
- `web/style.css` — dark void bg, 1100×900 stage, pawn/creature DOM sprites,
  emotes, HUD, log, chat, panels.
- `web/app.js` (1211 lines) — iso geometry `STAGE_W=1100 STAGE_H=900 TILE_W=168
  TILE_H=84 ORIGIN=(550,212)`; `drawIsland()` (sky, mountains, floating cube,
  tiles); DOM pawns/creatures at iso coords with slot offsets; chat/log/dossier/
  lore/HUD; WebSocket → `applySnapshot()` → `frame()`.
- `web/sprites.js` (778 lines) — procedural pixel art: `makeSprite()`, ground
  textures, tile assembly (`getTile`), 4-frame flame, pawn/creature/visitor/raider
  sprites. **Pawns + creatures + fallback objects stay here.**
- `feed.py` serves any file under `web/` (`.png` → `image/png`, `.js` → JS), so
  **adding `web/atlas.js`, `web/atlas.html`, `web/assets/*.png` needs NO Python
  change.**

## Snapshot data model (unchanged — client is read-only)

- `s.grid` — 5×5 of emoji tile strings. Possible values:
  `🌲` forest · `🫐` meadow · `🪨` quarry · `🌊` river · `💀` ruins · `🏕️` camp ·
  `🌾` farm (Stage 6 tile) · `🔥` burning (wildfire) · `🌫️` ash. Default grid:
  ```
  🌲🌲🌲🌲🌲
  🌲🫐🪨🌊🌲
  🌲💀🏕️🌊🌲
  🌲🫐🌊🌲🌲
  🌲🌲🌲🌲🌲
  ```
- `s.pawns[]` — id, name, job, title, sex, status, pos [x,y], prev_pos, vitals,
  inventory, gear, goal, skills, relationships, partners, mother/father/partner_id,
  action, flavor, direction, quote, inner_monologue, mental_break, traits,
  pregnant/child/elder (bool).
- `s.wildlife[]` / `s.visitors[]` / `s.raiders[]` — id, species/kind, name, pos,
  state. `s.biome` — campfire, shelter, wood/food_stock, granary, palisade.
  `s.resources` — HUD aggregates. `s.lore` — graveyard/monument/patches/chronicle.
  `s.events[]` — per-tick events (`e.tick === s.tick - 1` for emotes/log).

## Design — top-down sprite renderer (vendored tiles, y-sorted sprites)

- **New file `web/atlas.js`** (loaded before `app.js`, after `sprites.js`):
  - Loads the three vendored PNGs via `new Image()` (same-origin; `feed.py` serves
    them; `file://` works too — drawImage never reads pixels back).
  - `Atlas.tile(sheet, col, row)` → cached 16×16 canvas slice (nearest-neighbour).
  - Tile-type → sheet-coord table (the atlas) — single file to tweak when the user
    corrects a tile.
  - `Atlas.ground(type, x, y)` → pre-rendered ground-tile canvas (grass variants
    chosen deterministically per (type,x,y) like the old `GROUND` noise).
  - `Atlas.standSprite(type, x, y)` → cached canvas of the standing object for a
    tile (tree/bush/rock/ruin/cottage/farm) sized to TILE.
- **Geometry:** `TILE = 128` (16 px art × 8 nearest-neighbour), map 5×5 = 640×640,
  centered in the 1100×900 stage (`MAP_X≈230, MAP_Y≈130`). Board fills ~55–65% of
  stage height like Part A. `resize()` scale cap stays `MAX_ZOOM=1.6`.
- **Render layers (bottom → top):**
  1. Canvas: soft dark vignette backdrop + rounded wooden board frame (procedural
     gradients/rects — cheap, no extra assets) around the map.
  2. Canvas: ground layer — one vendored tile per grid cell (grass/water/rock/
     dirt/farm/ash/scorch), shore transitions where river meets land, seasonal
     tint overlay (winter snow-white, autumn warm, summer bright).
  3. DOM (inside `#sprites`): standing objects + pawns + creatures, **y-sorted by
     z-index** (`z = Math.round(anchorY_px * 10)`), so a pawn walks behind a tree
     it's north of and in front of one it's south of.
- **Standing objects as DOM canvas sprites** (cached, rebuilt on grid-signature
  change): forest → tree; meadow → berry bush + flowers; quarry → rock pile;
  ruins → ruined stone; camp → cottage + animated campfire + well + fences;
  farm → sprouts. Wildfire tile → flame overlay (campfire frames) + glow.
- **Pawns/creatures:** same DOM canvas-sprite machinery as today, anchored at the
  tile center (feet at bottom). Compact slot offsets for stacked pawns (small ring
  around center, not the iso diamond). Walk interpolation unchanged (0–4 s).
- **Live effects (kept, adapted):** 14-frame animated river waves (canvas overlay
  on water tiles), 4-frame campfire + smoke particles + night glow, snow veil,
  night tint, per-tick emotes, 💤/🌀/🤰 badges, hover name pills.
- **HUD/panels/chat/log/dossier/lore/roster:** unchanged (all DOM, already
  top-down agnostic). Only coordinate plumbing (`iso()` → `top()`) and z-index
  change.

## Parts to implement (one commit each; tick todo.md per part)

### Part A — Vendor assets + atlas + contact sheet ✅ (committed)
- [x] Copy `Serene_Village_16x16.png`, `campfire.png`, `water_waves.png` →
  `web/assets/`.
- [x] `web/assets/ATTRIBUTION.md` — LimeZu, Serene Village revamped, CC-BY 4.0,
  link + date.
- [x] `web/atlas.js` — image loader, tile slicer, tile→coord table (user-verified
  mapping locked 2026-08-17 — see `web/TILES.md`).
- [x] `web/atlas.html` — labeled contact sheet of all 19×45 master tiles +
  campfire/water frames (dev tool; also serves as the user's PNG reference).
- [x] Client credit: credit line in `atlas.html` footer + `README.md` attribution
  section + `paper.txt` §credits.
- Commit: `Stage 12: vendor Serene Village tileset + tile atlas`. ✅

### Part B — Top-down terrain renderer ✅ (todo Step 12)
- [x] Replace iso geometry with top-down (`TILE=128`, map centered, `top(x,y)`).
- [x] Rewrite `drawIsland()` → `drawWorld()`: backdrop + board frame + ground
  tiles (vendored) + shore transitions + farm/ash/scorch + seasonal tint.
- [x] Water animation: 14-frame waves overlay on river tiles.
- [x] Wire `Atlas.ground()` into the grid-signature tile cache.
- Commit: `Stage 12: top-down terrain renderer`. ✅

Notes landed with Part B:
- **Bank lips are procedural** — the user-locked `shoreN/S/E/W` slices are a
  *diagonal sandy beach* scene (the band runs NW→SE; N/S pieces span 74px, not
  one tile), so straight river banks are drawn as a foam rim on water edges +
  a dark earthy lip on adjacent land edges (`drawBankLips`), reading cleanly as
  a river embankment.
- **`Atlas.ground()` already caches per (type,x,y)** 16×16 canvases, so no
  separate `lastGridSig`/`Sprites.getTile` cache is needed — `lastGridSig` was
  removed and the grid pass draws ground + animated water per frame.
- **Transitional stand-ins**: trees/cottage/bushes/rocks/ruins/sprouts/ash are
  still drawn on the canvas from `Sprites.SPRITES` (Part B); Part C replaces
  them with DOM y-sorted vendored sprites.

### Part C — Standing objects + y-sort ✅ (todo Step 12)
- [x] DOM object layer: trees (forest), berry bushes (meadow), rocks (quarry),
  ruins, cottage + animated campfire (camp), well/fences decor.
- [x] Y-sort all DOM sprites (objects + pawns + creatures) via z-index.
- [x] Wildfire flame/glow on burning tiles (canvas, unchanged).
- Commit: `Stage 12: y-sorted standing objects`. ✅

Notes landed with Part C:
- **New module `web/objects.js`** (loaded between `atlas.js` and `app.js`).
  `Objects.attach(spritesEl)` at init; `Objects.sync(grid, top, campfireGauge)`
  in `applySnapshot` rebuilds only on a grid-signature change (deferred until
  `Atlas.ready` to mirror app.js's `atlasReady` guard — a pre-decode snapshot
  parks the latest grid and builds it from the `onReady` callback);
  `Objects.tick(now)` animates the campfire; `Objects.depthZ(y)` is exported
  for app.js's per-frame pawn/creature z.
- **Depth-z is a bounded band**, not a raw z-index: `4 + round((anchorY-150)/20)`
  puts objects/pawns/creatures in z 4..32. A naive `round(anchorY*10)` would
  push sprites to z≈6800 and paint them **over the #log/#chat panels (z-40)**
  and HUD. The band keeps them between the canvas and the UI panels.
- **Per-tile determinism**: jitter/variants use the same noise family as
  atlas.js (`(x*salt1 + y*salt2) >>> 0`), so the object layout is stable across
  rebuilds and doesn't flicker.
- **Sway is CSS**: `.obj.sway` (trees, sprouts) uses `animation: obj-sway`
  rotating about the sprite base (`transform-origin: 50% 100%`) with a
  per-tile `animation-delay`; the campfire flame is the only JS-animated
  object (4 vendored frames via `Atlas.fireFrame`), swapping to a procedural
  stone pit when `campfire` is 0.
- **Well = composed 8×11 slice** (wellTop + wellBot, the user's two-part lock),
  upscaled 6×; the fence rail runs along the camp tile's north edge with two
  vertical corner posts (no rotation needed — fenceV is already vertical).
- Farm sprouts + ash mounds also live in the DOM layer (procedural stand-ins,
  y-sorted) so they occlude/can be occluded like everything else.
- The Part B canvas stand-ins (`drawStandin`, tent/logs/berry/rock/ruin
  draws) and the canvas campfire flame were **removed** — the DOM campfire
  flame + the existing radial glow/smoke on canvas now compose.
- Smoke test: the `#sprites` children now include objects, so the test counts
  `.pawn`/`.creature`/`.obj` classes instead of a raw total; it asserts the
  tree count, the bounded z band, a genuine top-row-vs-bottom-row y-sort, and
  exercises a 🏕️ tile (cottage/well/campfire/fences + flame↔cold toggling).
  The test grid construction was also fixed to use explicit full-emoji cells
  (`"🌲🌲…".split("")` had been producing lone UTF-16 surrogates).

### Part D — Pawns/creatures in top-down space ✅ (todo Step 12)
- [x] Reposition pawn/creature DOM to tile centers (`top()` coords).
- [x] Compact slot offsets for stacked pawns + stacked creatures.
- [x] Keep walk interpolation, action bobs, emotes, badges, hover pills.
- Commit: `Stage 12: top-down pawns + creatures`. ✅

Notes landed with Part D:
- **Creature slots**: `syncCreatures` groups entries by tile, sorts by `dom`
  key, and assigns `slotOffset(i)` — the same spread used by pawns. This
  prevents Deer/Rabbit/Merchant piling up at the exact tile centre when they
  share a tile. Slots recompute on every snapshot, so a neighbor's departure
  triggers a small "shuffle" glide from the old slot to the new one.
- **Creature glide** (`CREATURE_GLIDE = 1.2`): wildlife/visitors/raiders have
  no `prev_pos` in the snapshot, so the glide is inferred: on the first
  snapshot a creature appears, `created = false` lands it at the target
  directly (no glide from the origin corner); on subsequent snapshots, the
  delta between old and new screen positions is animated via `easeInOut`
  over the glide window, matching the pawn walk pattern.
- **Creature contact shadow**: `.creature::after` mirrors the existing
  `.pawn::after` — a soft `radial-gradient` ellipse at the creature's feet
  with `z-index: -1`, grounding characters on the top-down board.
- **Deterministic test clock**: the smoke test stubs `performance.now()`
  (a controllable `perfNow` variable) so `snapTime` and the `raf` timestamp
  share a clock; `perfNow = now` is set before each `send()` call to make
  walk/glide timing assertions deterministic. A 700ms `await` between snap2
  and snap3 lets the leaving-element `setTimeout(650)` timers fire so stale
  creatures/pawns are actually removed from the DOM.

### Part E — Ambient effects pass (todo Step 12)
- [x] Campfire smoke + night glow centered on camp; snow veil; night tint;
  river shimmer — all adapted to the new geometry.
- Commit: `Stage 12: ambient effects for top-down`.

### Part F — Doc + test sync (todo Step 12 + cross-stage)
- [ ] `plan.md` (this file) ticked; `todo.md` Step 12 checkboxes.
- [ ] `README.md` — feature/run notes + Serene Village attribution (CC-BY 4.0).
- [ ] `paper.txt` — client description §Implementation (top-down sprite renderer,
  vendored tileset) + credits; run `python check_paper.py`.
- [ ] `AGENTS.md` — Phase 6 client paragraph (emoji + procedural canvas → vendored
  tileset top-down renderer; pawns/creatures stay procedural).
- [ ] `tests/smoke_client.js` — update geometry/atlas assertions for the new
  renderer (DOM object layer, y-sort, top-down coords); `tests/test_web_client.py`
  stays green; full `ruff check . && python -m pytest tests -q`.
- Commit: `Stage 12: docs + smoke tests for top-down renderer`.

## Verification per part (AGENTS.md workflow)

- `node --check web/app.js`, `node --check web/sprites.js`, `node --check web/atlas.js`.
- `ruff check . && python -m pytest tests -q` — Python untouched, suite green.
- `python -m py_compile` on touched .py (unlikely — no Python changes expected).
- Live sanity check: `https://budget-universe-manila.ngrok-free.dev/` — confirm
  top-down terrain, trees/cottage/rocks, y-sort (pawn behind tree), campfire,
  HUD/log/chat/dossier/lore all still work; `atlas.html` for tile verification.

## Doc sync (same part/commit as the code)

- `todo.md` — add **Step 12: Top-Down Sprite World (vendored tileset)** section
  under the Phase 6 visual-polish block; tick one checkbox per committed part.
- `README.md` — new client look (top-down), Serene Village attribution, atlas
  dev-tool note.
- `paper.txt` — client description in §Implementation + credits. Keep LaTeX valid.
- `AGENTS.md` — Phase 6 client paragraph + architecture notes (atlas.js, y-sort).
- This `plan.md` — tick parts, record decisions/numbers as they land.

## License / attribution (CC-BY 4.0 — required)

- Pack: **"Serene Village — revamped" by LimeZu**, itch.io
  (https://limezu.itch.io/serenevillagerevamped), free download, license **CC-BY 4.0**.
- Credit line for README/paper/client footer:
  *"World tiles: 'Serene Village — revamped' by LimeZu (limezu.itch.io), CC-BY 4.0."*
- No license file ships inside the zip — the CC-BY 4.0 terms live on the itch page.
  `web/assets/ATTRIBUTION.md` records the pack name, author, source, license,
  download date, and which files were vendored.

## Gotchas / reminders

- Python 3.10; `engine.py` unchanged — all numbers stay in Python, client is
  read-only display.
- `feed.py` content-type map already handles `.png`/`.js`; no server change needed
  for atlas.js / assets / atlas.html.
- The sheet has a blank 19th column and transparent padding tiles — never slice a
  tile the atlas doesn't explicitly list.
- Tile art is 16×16 → upscale 8× nearest-neighbour; never smooth-scale (keeps
  crisp pixel look; `imageSmoothingEnabled=false` everywhere).
- Y-sort: objects taller than a tile (trees, cottage) need their z-index anchored
  to their **footprint** (south edge), not the top of the sprite, or pawns will
  float above them wrongly.
- Keep zero-dependency: no runtime downloads, no fonts, no external CDN — all art
  is vendored or procedural.
- Don't commit `%TEMP%\opencode\` content or `D:\FDM\*.zip`; only the three PNGs
  in `web/assets/`.
