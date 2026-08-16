# Tile Coordinates — GIMP Reference Sheet (LOCKED)

> All coordinates verified against the master sheet `Serene_Village_16x16.png` (304×720 px).
> Locked into the atlas on 2026-08-17. Used by `atlas.js`.

## 1. World tiles

### Tree (forest 🌲) — 3 variants at y=201, 32×39 each
- [x] Tree variant 1: `x=144, y=201, w=32, h=39` (green canopy + trunk)
- [x] Tree variant 2: `x=177, y=201, w=32, h=39` (green canopy + trunk)
- [x] Tree variant 3: `x=208, y=201, w=32, h=39` (blue-tinted canopy + trunk)

### Bush / flowers (meadow 🫐)
- [x] Bush: `x=113, y=194, w=14, h=14` (rounded green bush, gray base)
- [x] Flowers: `x=65, y=194, w=14, h=13` (colorful flower patch)

### Cottage (camp 🏕️) — complete pre-composed house
- [x] Cottage (whole): `x=87, y=404, w=67, h=55` (roof, walls, door, windows, stone foundation, yard)

### Rocks / stone (quarry 🪨)
- [x] Rock cluster: `x=3, y=298, w=24, h=22` (2-rock overlay — fine at scale)

### Ruins (💀) — stone rubble cluster
- [x] Ruin rubble: `x=0, y=48, w=47, h=32` (scatter of small gray stones)

### Farm soil (🌾) — plain dirt, furrows painted procedurally
- [x] Dirt/soil: `x=96, y=16, w=12, h=48` (brown soil strip w/ flecks)

### Water + shore (river 🌊)
- [x] Water tile: `x=141, y=84, w=8, h=8` (flat blue water)
- [x] Shore N: `x=59, y=67, w=74, h=14`
- [x] Shore S: `x=59, y=94, w=74, h=14`
- [x] Shore E: `x=126, y=75, w=12, h=29`
- [x] Shore W: `x=55, y=75, w=12, h=29`

## 2. Decor

### Fence
- [x] Horizontal rail: `x=64, y=276, w=48, h=11` (3 posts + rails)
- [x] Vertical post: `x=102, y=244, w=4, h=43`

### Path / dirt
- [x] Cobblestone path: `x=35, y=158, w=26, h=15`

### Not found in pack (procedural fallbacks)
- [x] Well — **FOUND + locked** ✅ (two parts: round top + bottom, below)
- [ ] Campfire — **not found** → keep existing `campfire.png` (4-frame animated)
- [ ] Sprout row — **not found** → procedural sprouts over dirt
- [ ] Ruins fallback piece — **not needed** (rubble cluster found)

### Well — round top + bottom (two parts, verified)
- [x] Well — round top: `x=191, y=530, w=8, h=7`
- [x] Well — bottom part: `x=192, y=537, w=6, h=4`
- Note: a wider crop catches the cottage roof — always stack exactly these two.

## Notes

- Ground grass tiles for forest/meadow/camp ground: use the pack's flat grass (verified
  earlier at tile `(5,0)` / 16×16) + the tiled canopy textures (rows 33–34) for variety.
- All slices are drawn with nearest-neighbour scaling — never smooth.
