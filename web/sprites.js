"use strict";
/* Phase 6 Step 7: procedural pixel-art sprite system (zero dependencies).
 *
 * Sprites are authored as arrays of equal-length strings; each character maps
 * to a hex color in a palette (`.` or space = transparent). makeSprite()
 * rasterizes once to an offscreen canvas; every scaled draw uses nearest-
 * neighbour (imageSmoothingEnabled=false) so the art stays crisp.
 *
 * Tiles are pre-rendered to a TILE_W x TILE_H canvas: a coarse 28x14 ground
 * texture (deterministic per (type,x,y)) is upscaled 6x with nearest-neighbour,
 * clipped to the iso diamond, softly shaded, then object sprites are composited
 * on top. app.js draws the cached tile canvases each frame and keeps only the
 * dynamic effects live (water shimmer, flame animation, glow).
 *
 * Exposes window.Sprites = { getTile, resetTiles, drawFlame, drawSpriteAt }.
 * Relies on TILE_W / TILE_H defined by app.js (referenced at call time only).
 */

// ---- palette (shared across sprites) ----
const SPRITE_PAL = {
  g: "#3d8b40", G: "#2c6a31", L: "#7fce7d",      // greens
  b: "#6b4a2f", B: "#4a3120",                    // browns
  d: "#8b9096", D: "#6d7278", s: "#7a7f85",      // stone greys
  w: "#eef4ff", y: "#ffd23f", o: "#ff8c2e",      // flame
  r: "#e2574d", t: "#c9a06a",                    // berries / tent tan
  a: "#56585e", k: "#10141c",                    // ash
  W: "#59b3e6",                                  // water highlight
};

// ---- rasterizer ----
function makeSprite(rows, palette) {
  const h = rows.length;
  let w = 0;
  for (const row of rows) w = Math.max(w, row.length);
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const g = c.getContext("2d");
  const img = g.createImageData(w, h);
  const d = img.data;
  for (let y = 0; y < h; y++) {
    const row = rows[y] || "";
    for (let x = 0; x < w; x++) {
      const ch = row[x];
      if (!ch || ch === "." || ch === " ") continue;
      const hex = palette[ch];
      if (!hex) continue;
      const o = (y * w + x) * 4;
      d[o] = parseInt(hex.slice(1, 3), 16);
      d[o + 1] = parseInt(hex.slice(3, 5), 16);
      d[o + 2] = parseInt(hex.slice(5, 7), 16);
      d[o + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  return c;
}

// ---- deterministic hashing ----
function hash2(a, b) {
  let h = (a * 374761393 + b * 668265263) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h = h ^ (h >>> 16);
  return (h >>> 0) / 4294967296;
}
function hash3(a, b, c) {
  let h = (a * 374761393 + b * 668265263 + c * 2246822519) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h = h ^ (h >>> 16);
  return (h >>> 0) / 4294967296;
}

// ---- sprite library ----
const SPRITES = {
  // Pine tree (11x16).
  pine: makeSprite([
    "....GGG....",
    "...GGGGG...",
    "..GGgggGG..",
    ".GGgggggGG.",
    ".GGggLggGG.",
    ".GGggLggGG.",
    "GGgggggggGG",
    "GGgggggggGG",
    ".GGgggggGG.",
    ".GGgggggGG.",
    "..GGgggGG..",
    "...GGGGG...",
    ".....bbb...",
    "....bbbbb..",
    "....bbbbb..",
    ".......b...",
  ], SPRITE_PAL),

  // Rock pile (13x8) — built with repetition so row widths are guaranteed.
  // Art:
  //   ...DDDDDDD...
  //   ..DddddddddD.
  //   .DddddddddddD
  //   .DdddLLdddddD
  //   DddddddddddddD
  //   DddddddddddddD
  //   .DddddddddddD.
  //   ..DDDDDDDD...
  rock: (() => {
    const dot = ".";
    return makeSprite([
      dot.repeat(3) + "D".repeat(7) + dot.repeat(3),
      dot.repeat(2) + "D" + "d".repeat(8) + "D" + dot,
      dot + "D" + "d".repeat(10) + "D",
      dot + "D" + "d".repeat(3) + "LL" + "d".repeat(5) + "D",
      "D" + "d".repeat(11) + "D",
      "D" + "d".repeat(11) + "D",
      dot + "D" + "d".repeat(9) + "D" + dot,
      dot.repeat(2) + "D".repeat(8) + dot.repeat(3),
    ], SPRITE_PAL);
  })(),

  // Ruined wall fragment (14x12).
  ruin: makeSprite([
    ".sssss..sssss.",
    "ssssss..ssssss",
    "ssssss..ssssss",
    "ssssss..ssssss",
    "ssssss...sssss",
    "ssssss....sss.",
    "ssssss.....ss.",
    ".sssss......s.",
    "..ssss........",
    "...sss........",
    "....ss........",
    "..............",
  ], SPRITE_PAL),

  // Tent (13x10).
  tent: makeSprite([
    "......t......",
    ".....ttt.....",
    "....trtrt....",
    "...trrrrrt...",
    "..trrrrrrrt..",
    ".trrrtttrrrt.",
    ".trrt...trrt.",
    ".trrt.tt.trt.",
    ".ttttttttttt.",
    ".ttttttttttt.",
  ], SPRITE_PAL),

  // Campfire logs (13x5).
  logs: makeSprite([
    "..bbbbbbbbbb.",
    ".bbbbbbbbbbbb",
    "bbbbbbbbbbbbb",
    ".bbbbbbbbbbbb",
    "..bbbbbbbbbb.",
  ], SPRITE_PAL),

  // Flame frames (9x12) — frames alternate in drawFlame() (4-frame campfire).
  flame0: makeSprite([
    "....o....",
    "...ooo...",
    "..oyyyo..",
    ".oyyyyyo.",
    ".oyyyyyyo",
    "oyyyyyyyo",
    "oyyyyyyyo",
    ".oyyyyyyo",
    ".oyyyyyyo",
    "..oyyyyo.",
    "...oyyo..",
    "....o....",
  ], SPRITE_PAL),
  flame1: makeSprite([
    ".....o...",
    "....ooo..",
    "...oyyyo.",
    "..oyyyyyo",
    "..oyyyyyo",
    ".oyyyyyyo",
    ".oyyyyyyo",
    ".oyyyyyyo",
    "..oyyyyo.",
    "...oyyo..",
    "....o....",
    ".........",
  ], SPRITE_PAL),
  flame2: makeSprite([
    "...ooo...",
    "..oyyyo..",
    ".oyyyyyo.",
    ".oyyyyyyo",
    "oyyyyyyyo",
    "oyyyyyyyo",
    "oyyyyyyyo",
    ".oyyyyyyo",
    ".oyyyyyyo",
    "..oyyyyo.",
    "...oyyo..",
    "....o....",
  ], SPRITE_PAL),
  flame3: makeSprite([
    "....o....",
    "...oyyo..",
    "..oyyyyo.",
    "..oyyyyyo",
    ".oyyyyyyo",
    "oyyyyyyyo",
    "oyyyyyyyo",
    ".oyyyyyyo",
    "..oyyyyyo",
    "..oyyyyo.",
    "...oyyo..",
    "....o....",
  ], SPRITE_PAL),

  // Farm sprouts (11x4).
  sprout: makeSprite([
    "...g....g..",
    "..gLg..gLg.",
    "...g....g..",
    "...........",
  ], SPRITE_PAL),

  // Berry bush (9x6).
  berry: makeSprite([
    "..ggggg..",
    ".ggrgrgg.",
    "ggggggggg",
    "ggrgggrgg",
    "ggggggggg",
    ".ggggggg.",
  ], SPRITE_PAL),

  // Ash mound (11x4).
  ashmound: makeSprite([
    "..DDDDDDD..",
    ".DDdddddDD.",
    "DDdddddddDD",
    "DDdddddddDD",
  ], SPRITE_PAL),

  // Lily pad (7x4).
  lily: makeSprite([
    ".GGGGG.",
    "GGgggGG",
    "GGgggGG",
    ".GGGGG.",
  ], SPRITE_PAL),
};

const FLAME_FRAMES = [SPRITES.flame0, SPRITES.flame1, SPRITES.flame2, SPRITES.flame3];

// ---- ground texture (28x14 coarse canvas, upscaled 6x) ----
const GROUND = {
  grass: ["#3f8f42", "#478f46", "#377a3a", "#4d9d4d", "#36713a"],
  water: ["#1e7fc6", "#2281c2", "#1a70b2", "#2b8cd2"],
  rock: ["#8f9499", "#82878c", "#9aa0a5", "#767b80"],
  dirt: ["#7d5c3e", "#77583c", "#836043", "#6f5237"],
  ash: ["#2c2c30", "#27272b", "#333338", "#3d3d42"],
  scorch: ["#3b2c1d", "#34251a", "#433120", "#2c2014"],
  farm: ["#6d5136", "#74583c", "#674c30", "#5d452e"],
};

function pick(arr, r) {
  return arr[Math.floor(r * arr.length) % arr.length];
}

function cellColor(type, i, j, x, y) {
  const r = hash3(i * 31 + x * 7, j * 17 + y * 11, type.charCodeAt(0) * 13 + type.length);
  switch (type) {
    case "🌊":
      if (i % 9 === 0 && r > 0.45) return "#58b3e6";
      return pick(GROUND.water, (j % 2 === 0 ? r + 0.3 : r));
    case "🪨":
      if (r > 0.88) return "#5c6166";
      return pick(GROUND.rock, r);
    case "💀":
      if (r > 0.82) return "#8f9499";
      if (r > 0.62) return "#6f5237";
      return pick(GROUND.dirt, r);
    case "🌾":
      if (j % 3 === 0) return "#4e3a24";
      return pick(GROUND.farm, r);
    case "🔥":
      if (r > 0.75) return "#3d2a18";
      return pick(GROUND.scorch, r);
    case "🌫️":
      if (r > 0.85) return "#3a3a40";
      return pick(GROUND.ash, r);
    case "🏕️":
      if (r > 0.92) return "#3f8f42";
      return pick(GROUND.dirt, r);
    case "🫐":
      if (r > 0.96) return "#e8f0e0";
      if (r > 0.93) return "#e7c3d0";
      return pick(GROUND.grass, r);
    default:
      if (r > 0.93) return "#6cc26e";
      return pick(GROUND.grass, r);
  }
}

function groundCanvas(type, x, y) {
  const c = document.createElement("canvas");
  c.width = 28;
  c.height = 14;
  const g = c.getContext("2d");
  for (let j = 0; j < 14; j++) {
    for (let i = 0; i < 28; i++) {
      g.fillStyle = cellColor(type, i, j, x, y);
      g.fillRect(i, j, 1, 1);
    }
  }
  return c;
}

// ---- tile assembly ----
const TILE_OBJECTS = {
  "🌲": { n: "pine", scale: 3, dy: 26 },
  "🫐": { n: "berry", scale: 3, dy: 34 },
  "🪨": { n: "rock", scale: 3, dy: 36 },
  "💀": { n: "ruin", scale: 3, dy: 34 },
  "🌾": { n: "sprout", scale: 3, dy: 38 },
  "🌫️": { n: "ashmound", scale: 3, dy: 38 },
};

function drawSpriteAt(ctx, cv, cx, cyBottom, scale) {
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(
    cv,
    cx - (cv.width * scale) / 2,
    cyBottom - cv.height * scale,
    cv.width * scale,
    cv.height * scale
  );
}

function makeTile(type, x, y) {
  const c = document.createElement("canvas");
  c.width = TILE_W;
  c.height = TILE_H;
  const g = c.getContext("2d");
  const cx = TILE_W / 2;
  const cy = TILE_H / 2;

  // Ground texture (coarse -> nearest-neighbour upscale).
  const coarse = groundCanvas(type, x, y);
  g.imageSmoothingEnabled = false;
  g.drawImage(coarse, 0, 0, 28, 14, 0, 0, TILE_W, TILE_H);

  // Diamond clip + subtle top-light / bottom-shadow + edge.
  g.save();
  g.beginPath();
  g.moveTo(cx, 0);
  g.lineTo(TILE_W, cy);
  g.lineTo(cx, TILE_H);
  g.lineTo(0, cy);
  g.closePath();
  g.clip();
  const shade = g.createLinearGradient(0, 0, 0, TILE_H);
  shade.addColorStop(0, "rgba(255,255,255,0.09)");
  shade.addColorStop(0.5, "rgba(0,0,0,0)");
  shade.addColorStop(1, "rgba(0,0,0,0.17)");
  g.fillStyle = shade;
  g.fillRect(0, 0, TILE_W, TILE_H);
  g.strokeStyle = "rgba(0,0,0,0.22)";
  g.lineWidth = 2;
  g.stroke();
  g.restore();

  // Object sprites standing on the tile.
  if (type === "🏕️") {
    drawSpriteAt(g, SPRITES.tent, cx, cy + 32, 3);
    drawSpriteAt(g, SPRITES.logs, cx, cy + 26, 3);
  } else if (type === "🌊") {
    if (hash2(x * 3 + y, 7) < 0.45) {
      const lx = cx + (hash2(x, y) * 2 - 1) * 24;
      const ly = cy + (hash2(y, x) * 2 - 1) * 8;
      drawSpriteAt(g, SPRITES.lily, lx, ly + 10, 2);
    }
  } else {
    const o = TILE_OBJECTS[type];
    if (o) drawSpriteAt(g, SPRITES[o.n], cx, cy + o.dy, o.scale);
  }
  return c;
}

// ---- tile cache (reset whenever the grid changes) ----
const tileCache = new Map();

function getTile(type, x, y) {
  const key = type + ":" + x + "," + y;
  let cv = tileCache.get(key);
  if (!cv) {
    cv = makeTile(type, x, y);
    tileCache.set(key, cv);
  }
  return cv;
}

function resetTiles() {
  tileCache.clear();
}

// ---- animated flame (4 frames, ~150 ms each) ----
function drawFlame(ctx, x, yBottom, now) {
  const frame = Math.floor(now / 150) % FLAME_FRAMES.length;
  ctx.imageSmoothingEnabled = false;
  const cv = FLAME_FRAMES[frame];
  const scale = 3;
  ctx.drawImage(
    cv,
    x - (cv.width * scale) / 2,
    yBottom - cv.height * scale,
    cv.width * scale,
    cv.height * scale
  );
}

// ---- pawn sprites (standing pixel characters, hue-varied per name) ----
// Native canvas 48x72 (12x18 art at scale 4). Chars: h/H hair, f face, Y eyes,
// t/T tunic, b belt, L pants, s shoes. 'h' and 't' are recoloured per pawn.
const PAWN_CV_W = 48;
const PAWN_CV_H = 72;

const IDLE_M = [
  "....hhhh....",
  "...hhhhhh...",
  "...hhHHhh...",
  "..hffffffh..",
  "..ffYffYff..",
  "..ffffffff..",
  "..tttttttt..",
  ".tttttttttt.",
  ".tttttttttt.",
  ".tttttttttt.",
  "..tttttttt..",
  "..bTTTTTTb..",
  "..LLLLLLLL..",
  "..LLLLLLLL..",
  "...LL..LL...",
  "...LL..LL...",
  "...ss..ss...",
  "...ss..ss...",
];

const IDLE_F = [
  "....hhhh....",
  "...hhhhhh...",
  "..hhhhhhhh..",
  "..hffffffh..",
  "..ffYffYff..",
  "..hfffffhh..",
  ".hhttttthh..",
  ".hhtttttthh.",
  ".hhtttttthh.",
  ".tttttttttt.",
  "..tttttttt..",
  "..bTTTTTTb..",
  "..LLLLLLLL..",
  "..LLLLLLLL..",
  "...LL..LL...",
  "...LL..LL...",
  "...ss..ss...",
  "...ss..ss...",
];

// Walk frames: rows 14-17 become a mid-stride stance.
const WALK_M = [
  ...IDLE_M.slice(0, 14),
  "...LL.LL....",
  "...LL.LL....",
  "...ss.ss....",
  "...ss.ss....",
];

const WALK_F = [
  ...IDLE_F.slice(0, 14),
  "...LL.LL....",
  "...LL.LL....",
  "...ss.ss....",
  "...ss.ss....",
];

const CHILD = [
  "....hhhh....",
  "...hhhhhh...",
  "..hhhhhhhh..",
  "..ffffffff..",
  "..fYffYff...",
  "..ffffffff..",
  ".tttttttttt.",
  ".tttttttttt.",
  ".tttttttttt.",
  "..tttttttt..",
  "..LLLLLLLL..",
  "..LLLLLLLL..",
  "...LL..LL...",
  "...ss..ss...",
];

function hueFromName(name) {
  let h = 0;
  for (const ch of String(name)) h = (h * 31 + ch.codePointAt(0)) % 360;
  return h;
}

function hsl(h, s, l) {
  return `hsl(${h}, ${s}%, ${l}%)`;
}

// frame: 0 = idle stance, 1 = walk stride. bobY lifts the art 1px (walk bob).
function makePawnSprite(sex, elder, child, hairHue, tunicHue, frame, bobY) {
  let rows;
  if (child) {
    rows = CHILD;
  } else if (frame === 1) {
    rows = sex === "F" ? WALK_F : WALK_M;
  } else {
    rows = sex === "F" ? IDLE_F : IDLE_M;
  }
  const hair = elder ? "#aab2bd" : hsl(hairHue, 45, 40);
  const sheen = elder ? "#c8cfd8" : hsl(hairHue, 45, 58);
  const pal = {
    h: hair,
    H: sheen,
    f: "#eec49c",
    Y: "#1f1f24",
    t: hsl(tunicHue, 42, 42),
    T: hsl(tunicHue, 42, 60),
    b: "#4a3120",
    L: "#46505e",
    s: "#33261a",
  };
  const src = makeSprite(rows, pal);
  const scale = child ? 3 : 4;
  const c = document.createElement("canvas");
  c.width = PAWN_CV_W;
  c.height = PAWN_CV_H;
  const g = c.getContext("2d");
  g.imageSmoothingEnabled = false;
  const w = src.width * scale;
  const h = src.height * scale;
  g.drawImage(src, (PAWN_CV_W - w) / 2, PAWN_CV_H - h - (bobY || 0), w, h);
  return c;
}

// ---- creature / visitor / raider sprites ----
// mk() pads every row to W dots so hand-authored art can't misalign.
function mk(W, rows) {
  return rows.map((r) => String(r).padEnd(W, ".").slice(0, W));
}

// Canvas shared by all creatures: wildlife, visitors, raiders.
const CREATURE_CV_W = 72;
const CREATURE_CV_H = 68;

const CREATURE_ROWS = {
  // Deer — side view, facing left, antlers + 4 legs (18 wide).
  deer: mk(18, [
    "..aa...aa",
    "..aa...aa",
    ".aaaa..aa",
    ".aaaa....",
    ".hhhhhhh.",
    ".hhhehhhh",
    ".hhhhhhhhh",
    ".hhhhhhhhhhhh",
    "hhhhhhhhhhhhhh",
    "hhhhhhhhhhhhhhh",
    "hhhhhhhhhhhhhh",
    ".hhhhhhhhhhhh",
    ".bbbbbbbbbbbb",
    ".bb..bb..bb..bb",
    ".bb..bb..bb..bb",
    ".bb..bb..bb..bb",
  ]),
  // Wolf — side view, ears + tail (18 wide).
  wolf: mk(18, [
    "..ww.w",
    ".www.w........w",
    ".wwwwww.ww.....w",
    ".wwewwwwww.....w",
    "wwwwwwwwwwwww..w",
    "wwwwwwwwwwwwwww.",
    ".wwwwwwwwwwwwwww",
    ".wwwwwwwwwwwwww.",
    "..wwwwwwwwwwww..",
    "..wwww.wwwwwww..",
    ".wwww...wwwww...",
    ".wwww...wwwww...",
    ".wwww...wwwww...",
    ".ww.....wwww....",
  ]),
  // Bear — bulky body, small ears (18 wide).
  bear: mk(18, [
    ".....ww",
    "....wwww",
    "...wwwwww",
    "..wwwwwwwww",
    ".wwwwwwwwwww",
    ".wwwwwwwwwwww",
    "wwwwwwwwwwwwww",
    "wwwwwwwwwwwwwww",
    "wwwwwwwwwwwwwww",
    ".wwwwwwwwwwwwww",
    ".wwwwwwwwwwwwww",
    ".wwwwwwwwwwwwww",
    ".wwww...wwwwww",
    ".www.....wwww",
    ".www.....wwww",
  ]),
  // Rabbit — long ears, small body (12 wide).
  rabbit: mk(12, [
    "..rr.rrrr",
    "..rr..rrr",
    ".rrr.rrrr",
    ".rrrrrrrr",
    "rrrrrrrrr",
    "rrrrrrrr.",
    ".rrrrrrr.",
    ".rr.rrr..",
    "..r..r...",
    ".....r...",
  ]),
  // Merchant — wide hat + pack (14 wide).
  merchant: mk(14, [
    "..hhhhhhhhhh",
    "..hhhhhhhhhh",
    "...tttttttt",
    "...tttttttt",
    "...ffffffff",
    "...fYffYff",
    "..tttttttttt",
    ".ttttttttttt",
    ".ttttttttttt",
    ".ttttttttttt",
    "..tttttttttt",
    "..tttttttttt",
    "..bbbbbbbbbb",
    "...LL..LL",
    "...LL..LL",
    "...ss..ss",
    "...ss..ss",
  ]),
  // Wanderer — hooded traveller (14 wide).
  wanderer: mk(14, [
    "....gggg",
    "...gggggg",
    "...gggggg",
    "...ggffgg",
    "...fffffff",
    "...fYffYff",
    "..ggggggggg",
    ".ggggggggggg",
    ".ggggggggggg",
    ".ggggggggggg",
    "..ggggggggg",
    "..ggggggggg",
    "..bbbbbbbbbb",
    "...LL...LL",
    "...LL...LL",
    "...ss...ss",
    "...ss...ss",
  ]),
  // Bard — feathered cap + lute (14 wide).
  bard: mk(14, [
    "......rr",
    ".....rrrr",
    "...rrrrrrrr",
    "...rrrrrrrr",
    "...ffttttff",
    "...fYttttYf",
    "..pppppppppp",
    ".pppppppppppp",
    ".pppppppppppp",
    ".pppppppppppp",
    "..pppppppppp",
    ".llppppppppp",
    "..llppppppp.",
    "...LL..LL",
    "...LL..LL",
    "...ss..ss",
    "...ss..ss",
  ]),
  // Raider — dark hood + red bandana (14 wide).
  raider: mk(14, [
    ".....dd",
    "....dddd",
    "....dddd",
    "....dddd",
    "....rrrr",
    "...drrdrr",
    "..ddddddddd",
    ".ddddddddddd",
    ".ddddddddddd",
    ".ddddddddddd",
    "..ddddddddd",
    "..bbbbbbbbb",
    "..LLLLLLLLL",
    "...LL...LL",
    "...LL...LL",
    "...ss...ss",
    "...ss...ss",
  ]),
};

const CREATURE_PALS = {
  deer: {
    pal: { h: "#a9744f", a: "#c9a06a", b: "#6b4a2f", e: "#1a1a1a" },
    dark: { h: "#3d2b20", a: "#2f221a", b: "#241812", e: "#000000" },
  },
  wolf: {
    pal: { w: "#8d949e", e: "#1a1a1a" },
    dark: { w: "#3c4048", e: "#000000" },
  },
  bear: {
    pal: { w: "#7a5238", e: "#1a1a1a" },
    dark: { w: "#3a251a", e: "#000000" },
  },
  rabbit: {
    pal: { r: "#cfd4da", e: "#1a1a1a" },
    dark: { r: "#6e727a", e: "#000000" },
  },
  merchant: {
    pal: { h: "#8a5a3b", t: "#c9a06a", f: "#eec49c", Y: "#1f1f24", b: "#6b4a2f", L: "#46505e", s: "#33261a" },
  },
  wanderer: {
    pal: { g: "#4a7a3a", f: "#eec49c", Y: "#1f1f24", b: "#6b4a2f", L: "#46505e", s: "#33261a" },
  },
  bard: {
    pal: { r: "#b03a48", p: "#6a4a8a", l: "#8a6a4a", f: "#eec49c", Y: "#1f1f24", L: "#46505e", s: "#33261a" },
  },
  raider: {
    pal: { d: "#3a3a40", r: "#a03030", b: "#2a2a30", L: "#46505e", s: "#1f1f24" },
  },
};

const CREATURE_SCALE = {
  deer: 3, wolf: 3, bear: 3, rabbit: 4,
  merchant: 4, wanderer: 4, bard: 4, raider: 4,
};

// species: deer/rabbit/wolf/bear/merchant/wanderer/bard/raider.
// dark: legendary-named wildlife get the darker palette.
function makeCreatureSprite(species, dark) {
  const rows = CREATURE_ROWS[species] || CREATURE_ROWS.deer;
  const entry = CREATURE_PALS[species] || CREATURE_PALS.deer;
  const pal = dark && entry.dark ? entry.dark : entry.pal;
  const src = makeSprite(rows, pal);
  const scale = CREATURE_SCALE[species] || 3;
  const c = document.createElement("canvas");
  c.width = CREATURE_CV_W;
  c.height = CREATURE_CV_H;
  const g = c.getContext("2d");
  g.imageSmoothingEnabled = false;
  const w = src.width * scale;
  const h = src.height * scale;
  g.drawImage(src, (CREATURE_CV_W - w) / 2, CREATURE_CV_H - h, w, h);
  return c;
}

window.Sprites = {
  getTile,
  resetTiles,
  drawFlame,
  drawSpriteAt,
  SPRITES,
  PAWN_CV_W,
  PAWN_CV_H,
  makePawnSprite,
  hueFromName,
  PAWN_ROWS: { IDLE_M, IDLE_F, WALK_M, WALK_F, CHILD },
  CREATURE_CV_W,
  CREATURE_CV_H,
  makeCreatureSprite,
  CREATURE_ROWS,
};
