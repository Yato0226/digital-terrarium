# Terrarium Client — Visual Polish Tracker

> Live diorama client is `web/` (vanilla JS, zero deps). `feed.py` broadcasts a
> JSON snapshot per tick; the client is read-only display. World sim stays 5×5.

## Shipped
- [x] Phase 6 top-down sprite diorama (vendored LimeZu "Serene Village" tileset + procedural pawns/creatures/visitors/raiders).
- [x] Live via Cloudflare tunnel; the `top`→`tileXY` rename fixed the browser `SyntaxError` that froze the client on "connecting…".

## This round — client fixes
- [ ] **Black tiles** — scattered solid-black cells; reproducible after `!reset` (so it is *not* wildfire state, it is a ground-render bug). Object sprites confirmed transparent (ruled out opaque-bg box). Need a screenshot to pin exact tiles/cause, then fix in `drawGroundTile` / `Atlas.ground` / object-sprite composite. **BLOCKED: awaiting screenshot from user.**
- [x] **Pawns hidden behind objects** — y-sort anchored standing objects at their *foot* Y (below pawn tile-center), so objects painted over pawns. Fixed: pawns/creatures now ride a z-band (33–38) above the object layer (4–32) but below the HUD (40) — always visible.
- [x] **Map size + camera** — user chose **5×5 + pan/zoom** (not a 25×25 engine rewrite). Implemented: mouse-wheel zoom (cursor-anchored), drag-to-pan (with drag-vs-click guard so pawn select still works), and ＋/⤢/－ buttons; canvas board drawn under `ctx` transform, `#sprites`/`#emotes` get the matching CSS transform. Range 0.4×–2.5×.

## Workflow (per fix)
- `node --check` each touched `.js`; full `ruff check . && python -m pytest tests -q` stays green (Python untouched by client work).
- Commit per fix; tick the box above when landed.
