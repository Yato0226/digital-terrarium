# Plan — Phase 6 Step 6+: The Gorgeous Diorama (pixel-art client pass)

> **This file is the working plan + continuity anchor.** Update it after every part
> lands (tick the boxes, note decisions). If the conversation gets compacted, read
> this file first — it holds the current state, decisions, and next steps.
> Canonical feature checklist stays in `todo.md` (one `[x]` per committed part).

---

## Current status (updated: start of pass)

- **Decision — pixel art source: PROCEDURAL.** User chose *Procedural pixel art*
  (hand-authored pixel maps in JS, drawn with nearest-neighbor scaling) over
  vendoring Kenney PNGs. Keeps the repo's "zero external assets / offline / tiny"
  ethos and `paper.txt`'s "no asset footprint" claim. `AGENTS.md`/`paper.txt`
  wording about "emoji + procedural canvas" stays mostly accurate — the client
  *was* emoji + procedural canvas and now becomes procedural *pixel-art* canvas.
- **Decision — emoji are NOT banned.** User: "i did say hate emoji but i did not
  say do not use it." So: pixel art replaces the **world rendering** (tiles, pawns,
  creatures, visitors, raiders, decorations). **Emoji stay** in HUD chips, gauges,
  emotes, log markers, dossier/lore icons, bubbles, badges — anything that is UI,
  not the diorama itself.
- **Decision — map size: VISUAL ZOOM ONLY** (user chose "Visual zoom only", no
  engine/grid changes). 5×5 grid stays; we scale the client so the island fills
  ~55–65% of screen height.
- Kenney packs were downloaded to `%TEMP%\opencode\kenney\` (landscape / dungeon /
  farm / water / chars / micro) purely as visual reference for palette & tile size.
  **None are vendored.** Do not commit them.
- `node` is available (v22.18.0) for `node --check` on client JS.

## Client file map (current)

- `web/index.html` — HUD bar, gauges, stock chips, stage (canvas+sprites+bubbles+
  emotes+log), dossier panel, lore panel. Loads `app.js` only.
- `web/style.css` — dark void bg with star specks, 1000×640 stage, circular pawn
  rings, bubbles, emotes, HUD, log, panels.
- `web/app.js` (827 lines) — geometry `STAGE_W=1000 STAGE_H=640 TILE_W=120
  TILE_H=60 ORIGIN=(500,250)`; `drawIsland()` draws flat cutaway diamonds + colored
  tile diamonds + emoji glyphs + campfire/smoke/night tint; pawns/creatures as DOM
  with circular rings + emoji figures; bubbles; emotes; HUD; dossier; lore;
  WebSocket `connect()` → `applySnapshot()` → `frame()` rAF loop.
- `feed.py` serves any file under `web/` with proper content type (`.js` maps to
  `text/javascript`), so **adding `web/sprites.js` needs NO Python change**.

## Snapshot data model (what the client renders)

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
- `s.pawns[]` — id, name, job, title, sex (M/F), status, pos [x,y], prev_pos,
  vitals {hp,energy,hunger,warmth,morale}, inventory {wood,food,stone,fiber},
  gear {main_hand,body}, goal, skills, relationships, partners, mother/father/
  partner_id, action, flavor, direction, quote, inner_monologue, mental_break,
  traits, pregnant (bool), child (bool), elder (bool).
- `s.wildlife[]` — id, species (`Deer`/`Rabbit` = prey, `Wolf`/`Bear` = predator),
  name (named legendary beasts!), pos, state, emoji.
- `s.visitors[]` — id, kind (`Merchant`/`Wanderer`/`Bard`), name, pos, state.
- `s.raiders[]` — id, pos, state.
- `s.biome` — campfire, shelter, wood_stock, food_stock, granary, palisade.
- `s.resources` — wood/food/stone/fiber aggregates for HUD.
- `s.lore` — graveyard (epitaphs, beloved flag), monument (wood/stone/done/
  inscription/runes), patches, chronicle.
- `s.events[]` — per-tick events with `type`, `actor`, `target`, `description`;
  emotes/log filter `e.tick === s.tick - 1`.

## Design — procedural pixel-art system

- **New file `web/sprites.js`**, loaded in `index.html` before `app.js`.
- Sprite = array of equal-length strings (rows), each char maps to a palette
  color. `makeSprite(rows, palette)` renders once to an offscreen canvas; drawn
  scaled with `ctx.imageSmoothingEnabled = false` (crisp nearest-neighbor).
- Palettes per sprite group (ground, objects, pawns, fauna, visitors, raiders).
  Pawn hue variant: tint hair/tunic by `hashHue(name)` for variety.
- **Tiles:** pre-render each tile type to a canvas sized to the iso diamond
  footprint (2:1) with a textured ground (grass/water/stone/dirt patterns) plus
  object sprites standing on top (pine tree, rock pile, ruin wall, tent + campfire,
  farm sprouts, flame, ash).
- **Pawns:** standing pixel character (~16×24 px art, upscaled), variants for
  sex (hair/tunic), elder (grey, cane maybe), child (smaller). Idle + walk frames.
- **Fauna/visitors/raiders:** pixel sprites per species/kind; named legendary
  beasts (Wolf/Bear with `name`) get a dark "menacing" variant (Step 10).
- **Campfire:** 4-frame animated pixel flame sprite on the camp tile (Step 7).

## Parts to implement (one commit each; tick todo.md per part)

### Part A — Scale, depth & atmosphere (todo Step 6)
- [x] Zoom: bump geometry so island fills ~55–65% of stage height. Candidate:
  `TILE_W=200 TILE_H=100`, stage ~1200×900, ORIGIN centered (~600, ~360). Recheck
  `resize()` scale cap (currently `min(...,1)`) so the island reads big on large
  screens too. Compute final numbers in code; goal: island total (top face +
  thickness) ≈ 55–65% of screen height.
  **Done:** `TILE_W=168 TILE_H=84`, stage 1100×900, `ORIGIN=(550,212)`. Island
  spans y≈164→688 (524 px = 58% of 900); `resize()` cap raised `min(...,1)` →
  `MAX_ZOOM=1.6` so it stays ~58% up to 1440p windows.
- [x] 3D thickness: replace flat cutaway diamonds with a real dirt drop (20–30px),
  dark rock strata, dangling roots under the grass rim.
  **Done:** dirt lip (+18px + 46px dirt layer), 4 tapered rock strata
  (`#131a26`→`#33465c`), quadratic-curve roots with sway off the dirt band; two-tone
  grass rim.
- [x] Soft ground shadow: blurred dark oval beneath the island.
  **Done:** elliptical radial gradient (`scale(1,0.4)` circle) anchored just below
  the rock tip.
- [x] Atmospheric background: deep gradient (midnight navy winter, warm dusk
  summer), twinkling stars, distant mountain silhouette.
  **Done:** season/day sky gradient, 56 twinkling stars at night, two mountain
  ridges (snow-capped in winter days), horizon haze, sun/moon glow, lighter night
  tint.
- Commit msg: `Stage 6: diorama zoom, depth, shadow, atmosphere`.

### Part B — Pixel tile sprites (todo Step 7 first checkboxes)
- [x] `web/sprites.js` sprite factory + palettes.
  **Done:** `makeSprite(rows, palette)` rasterizes string-grid sprites to offscreen
  canvases; shared `SPRITE_PAL`; deterministic `hash2/hash3` for per-tile noise.
- [x] Ground textures per tile type + object sprites: pine 🌲, rock pile 🪨, ruin
  wall 💀, tent 🏕️, farm 🌾, flame 🔥, ash 🌫️, water shimmer 🌊, berry meadow 🫐.
  **Done:** coarse 28×14 ground canvases (grass/water/rock/dirt/ash/scorch/farm
  palettes with per-type rules) upscaled 6× nearest-neighbour, diamond-clipped,
  softly shaded; pixel sprites: pine, rock (programmatic rows), ruin wall, tent,
  campfire logs, 2-frame flame, sprouts, berry bush, ash mound, lily pad. Camp tile
  = tent + logs; flame stays live per-frame in app.js.
- [x] Rewire `drawIsland()` to draw pre-rendered tile sprites instead of colored
  diamonds + emoji glyphs.
  **Done:** `Sprites.getTile()` cache keyed by `type:x,y`, rebuilt only on grid
  signature change; water shimmer + wildfire flame/glow + campfire flame remain
  dynamic; `TILE_STYLE`/glyph loop removed.
- Commit: `Stage 7: procedural pixel tile sprites`.

### Part C — Pawn sprites (todo Step 7 + Step 8 "standing sprites")
- [ ] Standing pixel pawn sprites (sex/elder/child + hue variants, idle/walk).
- [ ] Replace circular `.ring` tokens; keep name labels + status badges (💤🌀🤰
  emoji stay — they're UI).
- Commit: `Stage 7: pixel pawn sprites`.

### Part D — Fauna, visitors, raiders, campfire (todo Step 7)
- [ ] Pixel sprites: deer, rabbit, wolf, bear (normal + named dark variant).
- [ ] Visitor sprites: merchant, wanderer, bard.
- [ ] Raider sprite.
- [ ] 4-frame animated campfire.
- Commit: `Stage 7: pixel fauna, visitors, raiders, campfire`.

### Part E — Un-stack the pawns (todo Step 8)
- [ ] Isometric slotting: multi-pawn tiles arrange in a small diamond formation
  (top-left, bottom-right, top-right…) instead of one overlapping blob.
- [ ] Per-pawn bubbles + 💤/badges float above the *individual* slot offset.
- [ ] Hover name pills (keep always-on option if simpler); crisp small labels.
- Commit: `Stage 8: pawn slotting + per-pawn bubbles`.

### Part F — HUD framing (todo Step 9)
- [ ] Top bar: wooden/slate banner, larger resource icons, tooltips, subtle winter
  frost texture along edges when season=Winter.
- [ ] Right-side roster drawer: mini card per colonist (portrait, name, health/
  energy bars, current action).
- [ ] Bottom log: parchment/dark-glass card; highlight AI Director narrative lines
  distinct from dry action lines.
- Commit: `Stage 9: HUD framing + roster drawer`.

### Part G — Ambient juice (todo Step 10)
- [ ] Drifting snow FX when Winter/Snow.
- [ ] Night campfire glow across tiles around camp while forest stays shadowed.
- [ ] Named legendary beasts render as menacing dark wolf/bear.
- Commit: `Stage 10: ambient snow, glow, legendary beasts`.

## Verification per part (AGENTS.md workflow)

- `node --check web/app.js` and `node --check web/sprites.js` on touched JS.
- `ruff check . && python -m pytest tests -q` — Python untouched, suite stays green.
- `python -m py_compile` on touched .py (unlikely — no Python changes expected).
- Live sanity check: `https://budget-universe-manila.ngrok-free.dev/` (ngrok must
  be running, feed enabled) — confirm zoom, sprites, slotting, HUD, snow/glow.

## Doc sync (same part/commit as the code)

- `todo.md` — tick each checkbox as its part lands (canonical checklist).
- `README.md` — client feature/run notes + note that the client now uses
  procedurally-generated pixel art (no external assets / no attribution needed;
  keep the "offline, zero runtime downloads" claim).
- `paper.txt` — update client description in §Implementation (currently claims
  "emoji and procedural drawing only"); change to procedural pixel-art sprites,
  emoji kept only for UI glyphs. Keep LaTeX valid; run `python check_paper.py`.
- `AGENTS.md` — update the Phase 6 client paragraph (the "emoji + procedural
  canvas" phrasing) once the pass is done.
- This `plan.md` — tick parts, record decisions/numbers as they land.

## Gotchas / reminders

- Python 3.10; `engine.py` unchanged — all numbers stay in Python, client is
  read-only display.
- `feed.py` content-type map already handles `.js`/`.css`/`.png`; sprites.js needs
  no server change.
- `resize()` currently caps scale at 1 — revisit for the zoom goal.
- Pawn DOM is positioned at iso coords and animated in `frame()`; sprite swap must
  keep the same anchor (feet) so slotting offsets compose cleanly.
- Keep zero-dependency: sprites.js is vanilla JS, no images fetched at runtime.
- Don't commit `%TEMP%\opencode\kenney\` or anything outside the repo.
