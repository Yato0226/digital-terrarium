# Plan — Top-Down Diorama Visual Polish

> Working plan + continuity anchor for the current client-polish round. Read this
> first after a compact. Canonical checklist is `todo.md`.

## Status (updated)
- Client is **live and rendering** (after the `top`→`tileXY` rename unblocked the
  browser parse-time `SyntaxError`).
- Remaining work this round: black tiles, pawn z-order, map size / zoom.

## Decisions already locked
- **Pixel-art source: VENDORED.** LimeZu "Serene Village — revamped" (CC-BY 4.0).
  World terrain/objects use the pack (`web/assets/`); pawns/creatures/visitors/
  raiders stay procedural in `web/sprites.js`. Emoji stay in HUD/UI.
- Slice table is locked (user-verified in GIMP, 2026-08-17) — see `web/TILES.md`.
- Delivery: Cloudflare Tunnel (ngrok free tier strips the WS upgrade).

## File map
- `web/index.html` — HUD bar, gauges, stock chips, stage (`#canvas` + `#sprites`
  DOM layer + emotes/chat/log), dossier, roster drawer, lore panel.
- `web/style.css` — dark theme, stage sizing, pawn/creature DOM sprites, HUD, panels.
- `web/app.js` — layout (`TILE`, `tileXY`, `drawWorld`), pawn/creature sprites,
  HUD, chat/log/dossier/lore, WebSocket → `applySnapshot` → `frame`.
- `web/objects.js` — DOM y-sorted standing objects; `Objects.depthZ(y)` bounded
  4..~32 (below the `#log`/`#chat` panels at z 40).
- `web/atlas.js` — vendored tile slices + `Atlas.ground/slice/scaled/waterFrame/
  fireFrame`.
- `web/sprites.js` — procedural pawn/creature sprites (`makePawnSprite`, etc.).
- `feed.py` — serves `web/` statically; no change needed for client work.

## Fixes

### 1. Black tiles (cause TBD — needs a screenshot)  — **BLOCKED: awaiting screenshot**
- **Symptom:** scattered solid-black cells. Reproduces on a fresh `!reset`, so the
  tile is *not* wildfire state — it is a ground-render issue.
- **Ruled out:** vendored object slices (trees/bush/cottage/rock/ruin) all have
  transparent backgrounds (verified via PIL on the master PNG), so they do NOT paint
  opaque black boxes over the ground.
- **Suspects:** `drawGroundTile` → `Atlas.ground(groundKey(tile), x, y)` for
  certain (type,x,y) producing an all-black 16×16, or an out-of-range `drawImage`
  window in `dirtCanvas`/`scorchCanvas`. The numbered tiles (2,4,6,9,10,13,16,17,23)
  don't map to a clean type/geometry pattern, so need a visual to pin it down.
- **Plan:** get a screenshot of the exact black tiles, map them to (x,y), then fix
  the specific draw path. Verify all 25 default-grid cells render grass/tree/etc.

### 2. Pawns hidden behind standing objects — **DONE**
- **Cause:** `Objects.depthZ(y)` uses each DOM sprite's anchor Y. Standing objects
  anchor at their *foot* (e.g. tree foot ≈ tileCenterY + 26), which is **below**
  the pawn's tile-center anchor. So `depthZ(treeFoot) > depthZ(pawn)` and the tree
  paints over the pawn → pawn looks "behind" / invisible.
- **Fix:** pawns/creatures now ride a z-band (33 + clamp(depthZ-4,0,5) = 33..38)
  above the object layer (4..32) but below the HUD (40). Always visible; objects
  still y-sort among themselves. Changed at `app.js` pawn loop + creature loop.

### 3. Map size + camera — **DONE (decided: 5×5 + pan/zoom)**
- User chose **Option A** (keep the 5×5 simulation; client-only pan/zoom). Option B
  (25×25 world rewrite) rejected as too risky/large for this pass.
- **Implemented in `app.js` (+ `index.html` / `style.css`):**
  - Board drawn under `ctx.save(); translate(panX,panY); scale(zoom,zoom); … restore`.
    Sky/background stays full-canvas (no transform) so zooming out shows no black gaps.
  - Night tint + snow veil drawn *after* restore (screen-space), so they cover the
    full viewport at any zoom.
  - `#sprites` + `#emotes` get the matching CSS `translate(...) scale(...)` transform
    (origin 0,0); they share the canvas coordinate space so they stay aligned.
  - Mouse-wheel zoom (cursor-anchored), drag-to-pan (with drag-vs-click guard so
    pawn select still works), and ＋/⤢/－ buttons (`#zoomCtl`). Range 0.4×–2.5×,
    `clampPan()` keeps the board centre on screen.

## Workflow
- `node --check web/app.js` (+ `atlas.js`, `objects.js`, `sprites.js`).
- `ruff check . && python -m pytest tests -q` — Python untouched, suite must stay green.
- Commit per fix; tick `todo.md`; keep `README.md`/`paper.txt` in sync only if a
  player-facing feature/command changes (these are pure client-polish fixes).
