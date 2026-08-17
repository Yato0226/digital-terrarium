/* Phase 6 Step 12: top-down sprite world client (vendored LimeZu tileset) + HUD.
 *
 * Timeline for each 60s tick (matches TICK_INTERVAL_SECONDS):
 *   0–4s   pawns whose tile changed walk across the board
 *   4–12s  speech (quote) and thoughts (inner_monologue) hit the corner chat box
 *   12–60s looping idle animation + periodic action emotes
 *   always floating smoke, animated river, swaying trees, night tint
 *
 * The world renders as a flat 5×5 top-down board: the wooden frame + ground
 * pass + animated water + effects are drawn on canvas; standing objects
 * (trees, cottage, campfire, …), pawns and creatures are DOM sprites y-sorted
 * by their footprint depth (z-index = anchorY * 10).
 *
 * World art is vendored from "Serene Village — revamped" by LimeZu (CC-BY 4.0,
 * web/assets/); pawns/creatures stay procedural (web/sprites.js).
 *
 * Zero runtime downloads: vanilla JS + Canvas2D + DOM overlays.
 */
"use strict";

const STAGE_W = 1100;
const STAGE_H = 900;
// Top-down board: a 5×5 tile map, each tile 128px (16px art × 8 nearest).
const TILE = 128;
const BOARD = 5;
const ORIGIN_X = 550;   // board centre x (stage centre)
const ORIGIN_Y = 430;   // board centre y
const FRAME = 34;       // wooden board frame thickness around the map
const MAX_ZOOM = 1.6;

// ---- camera: pan + zoom over the 5x5 board (client-only) ----
const ZOOM_MIN = 0.4, ZOOM_MAX = 2.5;
let view = { zoom: 1, panX: 0, panY: 0 };

// Debug overlay (text-only diagnosis when the URL has ?debug=1): labels every
// tile with its (x,y) grid coord + ground type so black-tile bugs can be
// reported by coordinate without a screenshot.
const DEBUG = new URLSearchParams(location.search).get("debug") === "1";

const WALK_SECONDS = 4;
const CREATURE_GLIDE = 1.2; // seconds for a creature to glide between tiles
const BUBBLE_DELAY = 4;
const BUBBLE_LIFE = 8;

// Top-down slot offsets (screen px) for stacked pawns on one tile, keyed by
// the pawn's sorted slot on that tile — stable across ticks, so a pawn keeps
// its corner while neighbours come and go (they shuffle over the walk window).
// Spread is tuned to a 128px tile so up to ~10 pawns don't overlap too much.
const SLOT_OFFSETS = [
  [0, 0],
  [-14, -8], [14, -8],
  [0, 10],
  [-14, -22], [14, -22],
  [0, -24],
  [-28, -8], [28, -8],
  [0, 26],
  [-28, -22], [28, -22],
];
function slotOffset(i) {
  return SLOT_OFFSETS[i] || [0, 0];
}

const ACTION_EMOTE = {
  Chop: "🪓", Forage: "🧺", Build: "🔨", Scout: "🔭", Attack: "⚔️",
  Share: "🍞", Mate: "💕", Interact: "✨", Rest: "💤",
};

const EMOTE_MAP = {
  mate: "💕", court: "💕", romance: "💕", birth: "🍼", break: "💢",
  attack: "⚔️", bite: "⚔️", chop: "🪓", forage: "🧺", gather: "🧺",
  gather_herbs: "🧺", salve: "💊", heal: "💊", craft: "🔨", build: "🔨",
  eat: "🍎", death: "🪦", fire_start: "🔥", fire_spread: "🔥", flood: "🌊",
  totem: "🪵", quest_complete: "✨", goal: "✨", shrine_offering: "🙏",
  sermon: "🙏", pray: "🙏", feast: "🎉", tradition: "🏷️", rune: "🗿",
  raid: "🥷", visitor: "🎒", recruit: "🤝", share: "🍞", starve: "🥀",
  legend_slain: "🏆", rest: "💤", sleep: "💤", interact: "✨",
  frenzy: "💥", starve_break: "🥀", worship: "🕯️", world: "🌍",
};

const RES_EMOJI = { wood: "🪵", food: "🍎", stone: "🪨", fiber: "🧶" };
const VITAL_LABEL = {
  hp: "❤️ Health", energy: "⚡ Energy", hunger: "🍖 Hunger",
  warmth: "🔥 Warmth", morale: "😊 Morale",
};
// Log lines that read as AI-Director narrative prose (LLM-written world beats)
// rather than dry mechanical actions.
const NARRATIVE_TYPES = new Set([
  "world", "chronicle", "patch", "monument_complete", "legend",
  "tradition", "season", "feast", "council",
]);

// ---- DOM refs ----
const stage = document.getElementById("stage");
const hud = document.getElementById("hud");
const canvas = document.getElementById("island");
const ctx = canvas.getContext("2d");
const spritesEl = document.getElementById("sprites");
Objects.attach(spritesEl);
const chatEl = document.getElementById("chat");
const emoteLayer = document.getElementById("emotes");
const titleEl = document.getElementById("title");
const connEl = document.getElementById("conn");
const logEl = document.getElementById("log");
const gCampfire = document.getElementById("gCampfire");
const gShelter = document.getElementById("gShelter");
const stockChips = {
  wood: document.getElementById("sWood"),
  food: document.getElementById("sFood"),
  stone: document.getElementById("sStone"),
  fiber: document.getElementById("sFiber"),
};
const loreBtn = document.getElementById("loreBtn");
const dossierEl = document.getElementById("dossier");
const dossierBody = document.getElementById("dossierBody");
const dossierClose = document.getElementById("dossierClose");
const loreEl = document.getElementById("lore");
const loreBody = document.getElementById("loreBody");
const loreClose = document.getElementById("loreClose");
const rosterBtn = document.getElementById("rosterBtn");
const rosterEl = document.getElementById("roster");
const rosterBody = document.getElementById("rosterBody");
const rosterClose = document.getElementById("rosterClose");

// ---- live state ----
let snap = null;
let snapTime = 0;
const pawns = new Map();       // id -> pawn record
const creatures = new Map();   // "type:id" -> creature record
const particles = [];
const snow = [];          // drifting snowflakes (Winter / snow weather)
let snowing = false;
let reconnectTimer = null;
let selectedId = null;
let lastSnapTick = -1;
let lastLogTick = -1;
let lastChatTick = -1;
let loreTab = "graveyard";
let rosterSig = null;
const rosterCards = new Map();  // pawn id -> roster card element

// ---- small helpers ----
/** Tile-centre screen point for grid (x, y) — top-down 5×5 board. */
function tileXY(x, y) {
  return {
    x: ORIGIN_X + (x - (BOARD - 1) / 2) * TILE,
    y: ORIGIN_Y + (y - (BOARD - 1) / 2) * TILE,
  };
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

/** Apply the camera pan/zoom to the DOM sprite + emote layers (share the
 *  canvas coordinate space, so they stay aligned with the canvas board). */
function applyView() {
  const t = `translate(${view.panX}px, ${view.panY}px) scale(${view.zoom})`;
  spritesEl.style.transformOrigin = "0 0";
  spritesEl.style.transform = t;
  emoteLayer.style.transformOrigin = "0 0";
  emoteLayer.style.transform = t;
}

/** Keep the board centre comfortably within the stage viewport. */
function clampPan() {
  const cx = view.panX + ORIGIN_X * view.zoom;
  const cy = view.panY + ORIGIN_Y * view.zoom;
  const minX = 220, maxX = STAGE_W - 220, minY = 150, maxY = STAGE_H - 120;
  view.panX -= (cx - clamp(cx, minX, maxX));
  view.panY -= (cy - clamp(cy, minY, maxY));
}

function easeInOut(t) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function spawnEmote(emoji, x, y) {
  const el = document.createElement("div");
  el.className = "emote";
  el.textContent = emoji;
  el.style.left = x + "px";
  el.style.top = y + "px";
  emoteLayer.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function spawnSmoke(cx, cy) {
  if (particles.length > 40 || Math.random() > 0.14) return;
  particles.push({
    x: cx + (Math.random() - 0.5) * 6,
    y: cy,
    vx: (Math.random() - 0.5) * 0.15,
    vy: -0.45 - Math.random() * 0.25,
    size: 4 + Math.random() * 3,
    life: 0,
    max: 2000 + Math.random() * 1200,
    seed: Math.random() * 7,
  });
}

function spawnSnow() {
  if (snow.length >= 130) return;
  snow.push({
    x: Math.random() * STAGE_W,
    y: -8 - Math.random() * 50,
    vx: (Math.random() - 0.5) * 0.5,
    vy: 0.5 + Math.random() * 0.9,
    size: 1 + Math.random() * 2.2,
    seed: Math.random() * 7,
    sway: 0.25 + Math.random() * 0.7,
  });
}

function isSnowing(s) {
  const season = String((s && s.season) || "").toLowerCase();
  const weather = String((s && s.weather) || "").toLowerCase();
  return season.includes("winter") || weather.includes("snow");
}

// ---- resize ----
function resize() {
  const scale = Math.min(
    (window.innerWidth - 10) / STAGE_W,
    (window.innerHeight - 10) / STAGE_H,
    MAX_ZOOM
  );
  stage.style.transform = `scale(${scale})`;
}
window.addEventListener("resize", resize);

// ---- camera: wheel zoom (cursor-anchored) + drag-to-pan ----
let drag = null;
let suppressClick = false;   // set briefly after a drag so it doesn't count as a select
stage.addEventListener("wheel", (e) => {
  e.preventDefault();
  const rect = stage.getBoundingClientRect();
  const mx = (e.clientX - rect.left) / (rect.width / STAGE_W);
  const my = (e.clientY - rect.top) / (rect.height / STAGE_H);
  const nz = clamp(view.zoom * (e.deltaY < 0 ? 1.12 : 1 / 1.12), ZOOM_MIN, ZOOM_MAX);
  view.panX = mx - (mx - view.panX) * (nz / view.zoom);
  view.panY = my - (my - view.panY) * (nz / view.zoom);
  view.zoom = nz;
  clampPan();
}, { passive: false });

stage.addEventListener("mousedown", (e) => {
  if (e.target.closest(".panel") || e.target.closest("#zoomCtl")) return;
  drag = { x: e.clientX, y: e.clientY, px: view.panX, py: view.panY, moved: false };
});
window.addEventListener("mousemove", (e) => {
  if (!drag) return;
  const rect = stage.getBoundingClientRect();
  const dx = (e.clientX - drag.x) / (rect.width / STAGE_W);
  const dy = (e.clientY - drag.y) / (rect.height / STAGE_H);
  if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 3) drag.moved = true;
  view.panX = drag.px + dx;
  view.panY = drag.py + dy;
  clampPan();
});
window.addEventListener("mouseup", () => {
  if (drag && drag.moved) {
    suppressClick = true;
    setTimeout(() => { suppressClick = false; }, 60);
  }
  drag = null;
});

// ---- atmospheric background helpers ----
function skyColors(season, day) {
  const s = String(season || "").toLowerCase();
  const winter = s.includes("winter");
  if (day === 0) {
    return winter ? ["#060a1a", "#152140"] : ["#0a1026", "#1e2c58"];
  }
  if (winter) return ["#7fa6cc", "#e2eef7"];
  if (s.includes("autumn")) return ["#4670b4", "#e9cba4"];
  if (s.includes("summer")) return ["#3d7cc6", "#c2e4f3"];
  return ["#5a8cc2", "#d6ebf5"];
}

function drawStars(now, day) {
  if (day !== 0) return;
  for (let i = 0; i < 56; i++) {
    const x = (Math.sin(i * 127.1 + 311.7) * 0.5 + 0.5) * STAGE_W;
    const y = (Math.sin(i * 269.5 + 183.3) * 0.5 + 0.5) * 0.4 * STAGE_H;
    const tw = 0.25 + 0.75 * Math.abs(Math.sin(now / 700 + i * 1.73));
    ctx.globalAlpha = tw;
    ctx.fillStyle = i % 4 === 0 ? "#cfe0ff" : "#ffffff";
    ctx.fillRect(x, y, i % 6 === 0 ? 2.5 : 2, i % 6 === 0 ? 2.5 : 2);
  }
  ctx.globalAlpha = 1;
}

function drawRidge(baseY, amp, color, seed, snow) {
  const n = 16;
  ctx.beginPath();
  ctx.moveTo(-12, STAGE_H);
  const peaks = [];
  for (let i = 0; i <= n; i++) {
    const x = (i / n) * (STAGE_W + 24) - 12;
    const y =
      baseY - amp * (0.55 + 0.45 * Math.sin(seed + i * 2.1) * Math.sin(seed * 1.3 + i * 0.9));
    ctx.lineTo(x, y);
    peaks.push([x, y]);
  }
  ctx.lineTo(STAGE_W + 12, STAGE_H);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
  if (snow) {
    ctx.fillStyle = "rgba(240,248,255,0.85)";
    for (let i = 1; i < n; i++) {
      const [x, y] = peaks[i];
      if (y < peaks[i - 1][1] - 6 && y < peaks[i + 1][1] - 6) {
        ctx.beginPath();
        ctx.moveTo(x - 17, y + 6);
        ctx.lineTo(x, y);
        ctx.lineTo(x + 17, y + 6);
        ctx.closePath();
        ctx.fill();
      }
    }
  }
}

function drawMountains(season, day) {
  const night = day === 0;
  const winter = String(season || "").toLowerCase().includes("winter");
  drawRidge(470, 88, night ? "rgba(15,24,50,0.8)" : "rgba(100,128,168,0.45)", 12.9, false);
  drawRidge(545, 120, night ? "rgba(6,14,32,0.95)" : "rgba(56,82,118,0.85)", 3.7, winter && !night);
}

// ---- canvas: the top-down board ----
let atlasReady = false;
Atlas.onReady(() => { atlasReady = true; });

/** Map pixel bounds (the 5×5 tile area). */
function mapBounds() {
  const min = tileXY(0, 0);
  const max = tileXY(BOARD - 1, BOARD - 1);
  return {
    x: min.x - TILE / 2,
    y: min.y - TILE / 2,
    w: max.x - min.x + TILE,
    h: max.y - min.y + TILE,
  };
}

function roundRectPath(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}

/** Season-tinted overlay colour for the map area. */
function groundTint(season) {
  const s = String(season || "").toLowerCase();
  if (s.includes("winter")) return "rgba(205,225,250,0.16)";
  if (s.includes("autumn")) return "rgba(255,166,80,0.10)";
  if (s.includes("summer")) return "rgba(255,244,170,0.06)";
  return "rgba(190,255,180,0.07)"; // spring
}

function isWaterTile(tile) { return tile === "🌊"; }

/** Ground-type key for Atlas.ground() from a grid emoji. */
function groundKey(tile) {
  if (tile === "🪨" || tile === "💀") return "dirt";
  if (tile === "🌾") return "farm";
  if (tile === "🌫️") return "ash";
  if (tile === "🔥") return "scorch";
  return "grass";
}

/** [x, y, w, h] band rect along one edge of a TILE-sized tile. */
function edgeBand(edge, px, py, size) {
  if (edge === 0) return [px, py, TILE, size];              // N
  if (edge === 1) return [px, py + TILE - size, TILE, size]; // S
  if (edge === 2) return [px, py, size, TILE];              // W
  return [px + TILE - size, py, size, TILE];                // E
}

function drawWorld(now) {
  ctx.clearRect(0, 0, STAGE_W, STAGE_H);
  if (!snap) return;
  const grid = snap.grid;
  const t = now;
  const season = snap.season;
  const day = snap.day;

  // --- atmospheric sky ---
  const [skyTop, skyBot] = skyColors(season, day);
  const sky = ctx.createLinearGradient(0, 0, 0, STAGE_H);
  sky.addColorStop(0, skyTop);
  sky.addColorStop(1, skyBot);
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, STAGE_W, STAGE_H);

  drawStars(t, day);
  drawMountains(season, day);

  // Soft haze above the horizon.
  const haze = ctx.createLinearGradient(0, STAGE_H * 0.55, 0, STAGE_H);
  haze.addColorStop(0, "rgba(200,220,245,0)");
  haze.addColorStop(0.4, day ? "rgba(212,228,246,0.18)" : "rgba(64,84,140,0.14)");
  haze.addColorStop(1, day ? "rgba(212,228,246,0.3)" : "rgba(56,76,132,0.22)");
  ctx.fillStyle = haze;
  ctx.fillRect(0, 0, STAGE_W, STAGE_H);

  // Sun / moon glow in the upper sky.
  if (day === 0) {
    const mx = STAGE_W * 0.76, my = STAGE_H * 0.16;
    const mg = ctx.createRadialGradient(mx, my, 4, mx, my, 90);
    mg.addColorStop(0, "rgba(220,230,255,0.5)");
    mg.addColorStop(1, "rgba(220,230,255,0)");
    ctx.fillStyle = mg;
    ctx.fillRect(mx - 90, my - 90, 180, 180);
    ctx.fillStyle = "#e8edff";
    ctx.beginPath();
    ctx.arc(mx, my, 14, 0, Math.PI * 2);
    ctx.fill();
  } else {
    const sx = STAGE_W * 0.8, sy = STAGE_H * 0.14;
    const sg = ctx.createRadialGradient(sx, sy, 6, sx, sy, 110);
    sg.addColorStop(0, "rgba(255,236,180,0.55)");
    sg.addColorStop(1, "rgba(255,236,180,0)");
    ctx.fillStyle = sg;
    ctx.fillRect(sx - 110, sy - 110, 220, 220);
    ctx.fillStyle = "#fff3c4";
    ctx.beginPath();
    ctx.arc(sx, sy, 22, 0, Math.PI * 2);
    ctx.fill();
  }

  // --- board (frame + ground + effects) under the camera transform ---
  ctx.save();
  ctx.translate(view.panX, view.panY);
  ctx.scale(view.zoom, view.zoom);

  // --- wooden board frame: the diorama sits on a tabletop ---
  const m = mapBounds();
  const f = { x: m.x - FRAME, y: m.y - FRAME, w: m.w + FRAME * 2, h: m.h + FRAME * 2 };
  ctx.save();
  ctx.fillStyle = "rgba(0,0,0,0.45)";
  roundRectPath(f.x + 12, f.y + 18, f.w, f.h, 20);
  ctx.fill();
  ctx.restore();
  // dark outer wood, warm inner planks, subtle top-light bevel
  ctx.fillStyle = "#3b2a1c";
  roundRectPath(f.x, f.y, f.w, f.h, 16);
  ctx.fill();
  ctx.fillStyle = "#573d26";
  roundRectPath(f.x + 6, f.y + 6, f.w - 12, f.h - 12, 11);
  ctx.fill();
  ctx.fillStyle = "#6e4f33";
  roundRectPath(f.x + 10, f.y + 10, f.w - 20, f.h - 20, 8);
  ctx.fill();
  ctx.strokeStyle = "rgba(255,220,160,0.22)";
  ctx.lineWidth = 2;
  roundRectPath(f.x + 11, f.y + 11, f.w - 22, f.h - 22, 7);
  ctx.stroke();
  // recessed map well inside the frame
  ctx.fillStyle = "#241a10";
  roundRectPath(m.x - 3, m.y - 3, m.w + 6, m.h + 6, 3);
  ctx.fill();

  // --- ground pass: flat Atlas tiles, 8× nearest-neighbour upscale ---
  for (let y = 0; y < grid.length; y++) {
    for (let x = 0; x < grid[y].length; x++) {
      drawGroundTile(grid[y][x], x, y, grid, t);
    }
  }

  // --- standing objects: DOM y-sorted layer (objects.js), appended above ---

  // Living effects over the tiles: wildfire glow + flame.
  for (let y = 0; y < grid.length; y++) {
    for (let x = 0; x < grid[y].length; x++) {
      if (grid[y][x] === "🔥") {
        const c = tileXY(x, y);
        const a = 0.14 + 0.09 * Math.sin(t / 140 + x * 2);
        // Top-down: wildfire glow centered on the tile.
        const g = ctx.createRadialGradient(c.x, c.y, 4, c.x, c.y, 60);
        g.addColorStop(0, `rgba(255,120,40,${a})`);
        g.addColorStop(1, "rgba(255,120,40,0)");
        ctx.fillStyle = g;
        ctx.fillRect(c.x - 60, c.y - 60, 120, 120);
        Sprites.drawFlame(ctx, c.x, c.y + 34, t);
      }
    }
  }

  // Campfire glow + smoke (flame is a DOM object in objects.js; camp = (2,2)).
  const campfire = (snap.biome && snap.biome.campfire) || 0;
  if (campfire > 0) {
    const camp = tileXY(2, 2);
    const flick = 0.55 + 0.2 * Math.sin(t / 90) + 0.1 * Math.sin(t / 47 + 2);
    // Top-down: glow centered on the camp tile itself.
    const g = ctx.createRadialGradient(camp.x, camp.y, 2, camp.x, camp.y, 54);
    g.addColorStop(0, `rgba(255,170,60,${0.5 * flick})`);
    g.addColorStop(1, "rgba(255,120,30,0)");
    ctx.fillStyle = g;
    ctx.fillRect(camp.x - 54, camp.y - 54, 108, 108);
    spawnSmoke(camp.x, camp.y - 8);
  }

  // Rising smoke.
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.x += p.vx + Math.sin(t / 130 + p.seed) * 0.2;
    p.y += p.vy;
    p.life += 16;
    if (p.life >= p.max) {
      particles.splice(i, 1);
      continue;
    }
    const a = (1 - p.life / p.max) * 0.35;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.size * (1 + p.life / p.max), 0, Math.PI * 2);
    ctx.fillStyle = `rgba(190,190,200,${a})`;
    ctx.fill();
  }

  // Seasonal ground tint over the map.
  const tint = groundTint(season);
  if (tint) {
    ctx.fillStyle = tint;
    ctx.fillRect(m.x, m.y, m.w, m.h);
  }

  // (board-space drawing ends here; restore before screen-space overlays)
  ctx.restore();

  // Night tint (lighter — the sky itself is already dark).
  if (snap.day === 0) {
    ctx.fillStyle = "rgba(10, 14, 40, 0.22)";
    ctx.fillRect(0, 0, STAGE_W, STAGE_H);
    if (campfire > 0) {
      const camp = tileXY(2, 2);
      const flick = 0.75 + 0.25 * Math.sin(t / 150) * Math.sin(t / 61);
      // Screen-blend warm pools over the dark tint: a wide falloff keeps the
      // outer forest in shadow while a bright ring lights camp + neighbours.
      ctx.globalCompositeOperation = "screen";
      const wg = ctx.createRadialGradient(camp.x, camp.y, 30, camp.x, camp.y, 210);
      wg.addColorStop(0, `rgba(255,160,60,${0.13 * flick})`);
      wg.addColorStop(1, "rgba(255,150,50,0)");
      ctx.fillStyle = wg;
      ctx.fillRect(0, 0, STAGE_W, STAGE_H);
      const ng = ctx.createRadialGradient(camp.x, camp.y, 8, camp.x, camp.y, 98);
      ng.addColorStop(0, `rgba(255,180,80,${0.3 * flick})`);
      ng.addColorStop(1, "rgba(255,150,50,0)");
      ctx.fillStyle = ng;
      ctx.fillRect(0, 0, STAGE_W, STAGE_H);
      ctx.globalCompositeOperation = "source-over";
    }
  }

  // Drifting snow: a soft particle veil in front of everything (Winter / snow).
  if (snowing) {
    for (let i = 0; i < 3; i++) spawnSnow();
    for (let i = snow.length - 1; i >= 0; i--) {
      const f = snow[i];
      f.x += f.vx + Math.sin(t / 420 + f.seed) * f.sway;
      f.y += f.vy;
      if (f.y > STAGE_H + 6) {
        f.y = -8;
        f.x = Math.random() * STAGE_W;
      }
      const tw = 0.5 + 0.5 * Math.sin(t / 300 + f.seed * 3);
      ctx.beginPath();
      ctx.arc(f.x, f.y, f.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(235,242,255,${0.3 + 0.35 * tw})`;
      ctx.fill();
    }
  }
}

// ---- ground tile pass ----
function drawGroundTile(tile, x, y, grid, t) {
  const c = tileXY(x, y);
  const px = c.x - TILE / 2;
  const py = c.y - TILE / 2;
  if (isWaterTile(tile)) {
    // Animated river: 14-frame subtle wave strip, phase-offset per tile.
    const frame = Atlas.waterFrame(Math.floor(t / 120) + x * 5 + y * 2);
    ctx.drawImage(frame, 0, 0, 16, 16, px, py, TILE, TILE);
  } else if (atlasReady) {
    const g = Atlas.ground(groundKey(tile), x, y);
    ctx.drawImage(g, 0, 0, 16, 16, px, py, TILE, TILE);
  } else {
    ctx.fillStyle = "#3c5a2e"; // pre-atlas fallback
    ctx.fillRect(px, py, TILE, TILE);
  }
  drawBankLips(tile, x, y, px, py, grid);
}

/** River banks: foam rim on water edges + earthy lip on land edges. */
function drawBankLips(tile, x, y, px, py, grid) {
  const water = isWaterTile(tile);
  const dirs = [[0, -1, 0], [0, 1, 1], [-1, 0, 2], [1, 0, 3]];
  for (const [dx, dy, edge] of dirs) {
    const nx = x + dx, ny = y + dy;
    if (ny < 0 || nx < 0 || ny >= grid.length || nx >= grid[ny].length) continue;
    const nTile = grid[ny][nx];
    if (water && nTile !== "🌊") {
      const [bx, by, bw, bh] = edgeBand(edge, px, py, 12);
      ctx.fillStyle = "rgba(215,240,255,0.5)";
      ctx.fillRect(bx, by, bw, bh);
    } else if (!water && nTile === "🌊") {
      const [bx, by, bw, bh] = edgeBand(edge, px, py, 12);
      ctx.fillStyle = "rgba(42,58,34,0.55)";
      ctx.fillRect(bx, by, bw, bh);
    }
  }
}

// ---- pawn & creature sprites ----
function makePawnEl() {
  const el = document.createElement("div");
  el.className = "pawn";
  const cv = document.createElement("canvas");
  cv.className = "psprite";
  cv.width = Sprites.PAWN_CV_W;
  cv.height = Sprites.PAWN_CV_H;
  const name = document.createElement("span");
  name.className = "name";
  el.appendChild(cv);
  el.appendChild(name);
  return el;
}

function syncPawns(s) {
  const seen = new Set();
  // Slot stacked pawns in a small diamond formation inside their tile. Sort by
  // id per tile so each pawn keeps a stable corner across ticks.
  const tiles = new Map();
  for (const p of s.pawns) {
    const key = p.pos[0] + "," + p.pos[1];
    if (!tiles.has(key)) tiles.set(key, []);
    tiles.get(key).push(p);
  }
  for (const list of tiles.values()) list.sort((a, b) => (a.id < b.id ? -1 : 1));
  const slots = new Map();
  for (const list of tiles.values()) {
    for (let i = 0; i < list.length; i++) slots.set(list[i].id, slotOffset(i));
  }
  for (const p of s.pawns) {
    seen.add(p.id);
    let rec = pawns.get(p.id);
    if (!rec) {
      const el = makePawnEl();
      spritesEl.appendChild(el);
      rec = {
        id: p.id,
        el,
        cv: el.querySelector(".psprite"),
        name: el.querySelector(".name"),
        idleCv: null, walkA: null, walkB: null,
        spriteSig: null, drawn: "",
        action: null,
        nextEmote: 0,
        phase: Math.random() * 7,
        px: 0, py: 0, x: 0, y: 0, moving: false,
        lastSlot: [0, 0],
      };
      pawns.set(p.id, rec);
      rec.el.addEventListener("click", (ev) => {
        if (suppressClick) return;
        ev.stopPropagation();
        selectPawn(p.id);
      });
    }
    // Re-render the pixel sprite only when its characteristics change.
    const hue = Sprites.hueFromName(p.name);
    const sig = `${p.sex}|${p.elder}|${p.child}|${hue}`;
    if (rec.spriteSig !== sig) {
      rec.spriteSig = sig;
      rec.idleCv = Sprites.makePawnSprite(p.sex, p.elder, p.child, hue, (hue + 150) % 360, 0, 0);
      rec.walkA = Sprites.makePawnSprite(p.sex, p.elder, p.child, hue, (hue + 150) % 360, 1, 1);
      rec.walkB = Sprites.makePawnSprite(p.sex, p.elder, p.child, hue, (hue + 150) % 360, 0, 0);
      rec.drawn = "";
    }
    const label = p.title ? `${p.name} ${p.title}` : p.name;
    if (rec.name.textContent !== label) rec.name.textContent = label;
    rec.el.classList.remove("leaving");

    const slot = slots.get(p.id) || [0, 0];
    const from = tileXY(p.prev_pos[0], p.prev_pos[1]);
    const to = tileXY(p.pos[0], p.pos[1]);
    // Start the walk from the pawn's previous *slot* so re-slotting (a neighbour
    // leaving the tile) reads as a little shuffle instead of a teleport.
    rec.px = from.x + (rec.lastSlot ? rec.lastSlot[0] : slot[0]);
    rec.py = from.y + (rec.lastSlot ? rec.lastSlot[1] : slot[1]);
    rec.x = to.x + slot[0];
    rec.y = to.y + slot[1];
    rec.lastSlot = slot;
    rec.moving = rec.px !== rec.x || rec.py !== rec.y;
    if (rec.action !== p.action) {
      rec.action = p.action;
      rec.nextEmote = 0;
    }

    const zzz = rec.el.querySelector(".zzz");
    if (p.action === "Rest" && p.status === "active") {
      if (!zzz) {
        const z = document.createElement("span");
        z.className = "zzz";
        z.textContent = "💤";
        rec.el.appendChild(z);
      }
    } else if (zzz) {
      zzz.remove();
    }
    const spiral = rec.el.querySelector(".spiral");
    if (p.mental_break && p.status === "active") {
      if (!spiral) {
        const sp = document.createElement("span");
        sp.className = "spiral";
        sp.textContent = "🌀";
        rec.el.appendChild(sp);
      }
    } else if (spiral) {
      spiral.remove();
    }
    const badge = rec.el.querySelector(".badge");
    if (p.pregnant && !badge) {
      const b = document.createElement("span");
      b.className = "badge";
      b.textContent = "🤰";
      rec.el.appendChild(b);
    } else if (!p.pregnant && badge) {
      badge.remove();
    }
  }
  for (const [id, rec] of pawns) {
    if (seen.has(id)) continue;
    rec.el.classList.add("leaving");
    setTimeout(() => rec.el.remove(), 650);
    pawns.delete(id);
  }
}

function syncCreatures(s) {
  const entries = [];
  for (const w of s.wildlife || []) {
    entries.push({
      dom: "w:" + w.id, key: w.id,
      species: String(w.species || "deer").toLowerCase(),
      dark: !!w.name, // legendary-named beasts get the dark palette
      label: w.name || w.species, pos: w.pos,
    });
  }
  for (const v of s.visitors || []) {
    entries.push({
      dom: "v:" + v.id, key: v.id,
      species: String(v.kind || "wanderer").toLowerCase(),
      dark: false,
      label: v.name || v.kind, pos: v.pos,
    });
  }
  for (const r of s.raiders || []) {
    entries.push({ dom: "r:" + r.id, key: r.id, species: "raider", dark: false, label: "", pos: r.pos });
  }
  const seen = new Set();
  // Slot stacked creatures per tile (stable by dom key) so wildlife/visitors/
  // raiders on one tile don't pile up at the exact centre.
  const tiles = new Map();
  for (const e of entries) {
    const key = e.pos[0] + "," + e.pos[1];
    if (!tiles.has(key)) tiles.set(key, []);
    tiles.get(key).push(e);
  }
  for (const list of tiles.values()) list.sort((a, b) => (a.dom < b.dom ? -1 : 1));
  const slots = new Map();
  for (const list of tiles.values()) {
    for (let i = 0; i < list.length; i++) slots.set(list[i].dom, slotOffset(i));
  }
  for (const e of entries) {
    seen.add(e.dom);
    let rec = creatures.get(e.dom);
    if (!rec) {
      const el = document.createElement("div");
      el.className = "creature";
      const cv = document.createElement("canvas");
      cv.className = "psprite";
      cv.width = Sprites.CREATURE_CV_W;
      cv.height = Sprites.CREATURE_CV_H;
      const name = document.createElement("span");
      name.className = "name";
      el.appendChild(cv);
      el.appendChild(name);
      spritesEl.appendChild(el);
      rec = { dom: e.dom, key: e.key, el, cv, name, sig: "", px: 0, py: 0, x: 0, y: 0, phase: Math.random() * 7, moving: false, created: false };
      creatures.set(e.dom, rec);
    }
    const sig = `${e.species}|${e.dark ? 1 : 0}`;
    if (rec.sig !== sig) {
      rec.sig = sig;
      const src = Sprites.makeCreatureSprite(e.species, e.dark);
      const g = rec.cv.getContext("2d");
      g.clearRect(0, 0, Sprites.CREATURE_CV_W, Sprites.CREATURE_CV_H);
      g.drawImage(src, 0, 0);
    }
    rec.name.textContent = e.label;
    rec.name.style.display = e.label ? "block" : "none";
    const slot = slots.get(e.dom) || [0, 0];
    const c = tileXY(e.pos[0], e.pos[1]);
    const nx = c.x + slot[0];
    const ny = c.y + slot[1];
    if (!rec.created) {
      // First appearance: land directly (no glide from the origin corner).
      rec.px = nx; rec.py = ny; rec.x = nx; rec.y = ny;
      rec.moving = false; rec.created = true;
    } else {
      rec.px = rec.x; rec.py = rec.y;
      rec.x = nx; rec.y = ny;
      // Re-slotting (a neighbour leaving the tile) reads as a short shuffle.
      rec.moving = rec.px !== rec.x || rec.py !== rec.y;
    }
    rec.el.classList.remove("leaving");
  }
  for (const [dom, rec] of creatures) {
    if (seen.has(dom)) continue;
    rec.el.classList.add("leaving");
    setTimeout(() => rec.el.remove(), 650);
    creatures.delete(dom);
  }
}

// ---- corner chat box (speech + thoughts instead of floating bubbles) ----
const CHAT_MAX = 8;
const chatLines = new Set();   // `${pawnId}@${tick}:${kind}` keys already shown

function updateChat(s) {
  if (s.tick === lastChatTick) return;
  if (s.tick < lastChatTick) {
    chatEl.textContent = "";
    chatLines.clear();
    lastChatTick = s.tick;     // fresh world: fall through and show its lines
  } else {
    lastChatTick = s.tick;
  }
  const names = new Map(s.pawns.map((p) => [p.id, p.name]));
  const rows = [];
  for (const p of s.pawns) {
    if (p.quote) rows.push({ id: p.id, kind: "speech", text: p.quote });
    if (p.inner_monologue) rows.push({ id: p.id, kind: "thought", text: p.inner_monologue });
  }
  for (const row of rows) {
    const key = `${row.id}@${s.tick}:${row.kind}`;
    if (chatLines.has(key)) continue;
    chatLines.add(key);
    const el = document.createElement("div");
    el.className = "chat-row " + row.kind;
    const name = names.get(row.id) || row.id;
    const chip = document.createElement("b");
    chip.className = "chat-name";
    chip.textContent = name;
    chip.style.color = `hsl(${Sprites.hueFromName(name)} 62% 68%)`;
    const text = document.createElement("span");
    text.className = "chat-text";
    text.textContent = row.text;
    el.append(chip, text);
    chatEl.prepend(el);
  }
  while (chatEl.children.length > CHAT_MAX) chatEl.lastChild.remove();
  chatEl.classList.toggle("hidden", chatEl.children.length === 0);
}

// ---- per-tick emotes ----
function findActorSpot(id) {
  const p = pawns.get(id);
  if (p) return { x: p.x, y: p.y - 46 };
  for (const c of creatures.values()) {
    if (c.key === id) return { x: c.x, y: c.y - 26 };
  }
  return null;
}

function addEmotes(s) {
  const tickEvents = (s.events || []).filter((e) => e.tick === s.tick - 1);
  for (const ev of tickEvents) {
    const emoji = EMOTE_MAP[ev.type];
    if (!emoji) continue;
    const spot = findActorSpot(ev.actor || ev.target);
    if (spot) spawnEmote(emoji, spot.x, spot.y);
  }
}

// ---- HUD: top bar, roster drawer, narrative log, dossier, lore ----
function updateHud(s) {
  const phase = s.day ? "Day" : "Night";
  titleEl.textContent =
    `${s.colony} — ${s.season} · ${s.weather} · ${phase} · tick ${s.tick}`;
  const r = s.resources || {};
  for (const k of ["wood", "food", "stone", "fiber"]) {
    stockChips[k].innerHTML = `${RES_EMOJI[k]} ${r[k] ?? 0}`;
  }
  const b = s.biome || {};
  setGauge(gCampfire, "Campfire", b.campfire);
  setGauge(gShelter, "Shelter", b.shelter);
  // Winter frost: icy edging on the banner + the stage's top/bottom rim.
  const winter = String(s.season || "").toLowerCase().includes("winter");
  hud.classList.toggle("frost", winter);
  stage.classList.toggle("frost", winter);
}

function actionLabel(p) {
  const a = p.action;
  if (!a) return "idle";
  if (a === "Move") return `🚶 ${p.direction || ""}`.trim();
  if (a === "Attack") return `⚔️ ${esc(p.target || "")}`;
  if (a === "Interact") return `✨ ${esc(p.flavor || "interact")}`;
  return `${ACTION_EMOTE[a] || "•"} ${a}`;
}

// ---- right-side colonist roster drawer ----
function updateRoster(s) {
  const pawns = s.pawns || [];
  const sig = pawns.map((p) => `${p.id}:${p.sex}:${p.elder ? 1 : 0}:${p.child ? 1 : 0}`).join("|");
  if (rosterSig !== sig) {
    rosterSig = sig;
    rosterBody.textContent = "";
    rosterCards.clear();
    for (const p of pawns) {
      const card = makeRosterCard(p);
      rosterCards.set(p.id, card);
      rosterBody.appendChild(card);
    }
  }
  // Refresh vitals + action each tick without rebuilding the DOM.
  for (const p of pawns) {
    const card = rosterCards.get(p.id);
    if (!card) continue;
    const v = p.vitals || {};
    card.querySelector(".r-hp").style.width = clampPct(v.hp) + "%";
    card.querySelector(".r-en").style.width = clampPct(v.energy) + "%";
    card.querySelector(".r-act").textContent = actionLabel(p);
    card.classList.toggle("bad", p.status !== "active");
    card.classList.toggle("sel", p.id === selectedId);
  }
}

function clampPct(v) {
  return Math.max(0, Math.min(100, Math.round(v ?? 0)));
}

function makeRosterCard(p) {
  const card = document.createElement("div");
  card.className = "r-card";
  card.dataset.id = p.id;
  const cv = document.createElement("canvas");
  cv.className = "r-port";
  cv.width = 26;
  cv.height = 39;
  const hue = Sprites.hueFromName(p.name);
  const src = Sprites.makePawnSprite(p.sex, p.elder, p.child, hue, (hue + 150) % 360, 0, 0);
  const g = cv.getContext("2d");
  g.imageSmoothingEnabled = false;
  g.drawImage(src, 1, 1, 24, 36);
  const info = document.createElement("div");
  info.className = "r-info";
  const name = document.createElement("div");
  name.className = "r-name";
  name.textContent = p.title ? `${p.name} ${p.title}` : p.name;
  const hp = document.createElement("div");
  hp.className = "r-bar";
  const hpFill = document.createElement("i");
  hpFill.className = "r-hp";
  hp.appendChild(hpFill);
  const en = document.createElement("div");
  en.className = "r-bar";
  const enFill = document.createElement("i");
  enFill.className = "r-en";
  en.appendChild(enFill);
  const act = document.createElement("div");
  act.className = "r-act";
  act.textContent = actionLabel(p);
  info.append(name, hp, en, act);
  card.append(cv, info);
  card.addEventListener("click", () => selectPawn(p.id));
  return card;
}

function setGauge(el, name, val) {
  const pct = Math.max(0, Math.min(100, Math.round(val ?? 0)));
  el.querySelector(".fill").style.width = pct + "%";
  el.title = `${name} ${pct}%`;
}

function updateLog(s) {
  // Events carry the pre-increment tick, so a snapshot at tick N contains
  // events with tick <= N-1 (matches the emote filter below).
  if (s.tick === lastSnapTick) return;          // same-tick re-broadcast
  if (s.tick < lastSnapTick) {                  // fresh world (e.g. !reset)
    logEl.textContent = "";
    lastLogTick = s.tick - 1;
  }
  lastSnapTick = s.tick;
  const fresh = (s.events || []).filter((e) => e.tick > lastLogTick && e.description);
  lastLogTick = s.tick - 1;
  for (const ev of fresh) {
    const row = document.createElement("div");
    row.className = "log-row" + (NARRATIVE_TYPES.has(ev.type) ? " narrative" : "");
    const em = document.createElement("span");
    em.className = "log-emoji";
    em.textContent = EMOTE_MAP[ev.type] || "•";
    const tx = document.createElement("span");
    tx.className = "log-text";
    tx.textContent = ev.description;
    row.appendChild(em);
    row.appendChild(tx);
    logEl.prepend(row);
  }
  while (logEl.children.length > 8) logEl.lastChild.remove();
}

function selectPawn(id) {
  selectedId = id;
  for (const [pid, rec] of pawns) rec.el.classList.toggle("selected", pid === id);
  const p = snap && (snap.pawns || []).find((x) => x.id === id);
  if (p) {
    renderDossier(p);
    dossierEl.classList.remove("hidden");
  }
}

function deselectPawn() {
  selectedId = null;
  for (const rec of pawns.values()) rec.el.classList.remove("selected");
  dossierEl.classList.add("hidden");
}

function vitClass(v) {
  if (v >= 60) return "ok";
  if (v >= 25) return "warn";
  return "bad";
}

function renderDossier(p) {
  const byId = new Map((snap.pawns || []).map((x) => [x.id, x]));
  const nm = (id) => (byId.has(id) ? byId.get(id).name : id);
  const v = p.vitals || {};
  const inv = p.inventory || {};
  const gear = p.gear || {};
  const sk = p.skills || {};
  const rel = p.relationships || {};
  const goal = p.goal || null;

  const bars = ["hp", "energy", "hunger", "warmth", "morale"].map((k) => {
    const val = Math.max(0, Math.min(100, v[k] ?? 0));
    return `<div class="vital"><div class="vlabel"><span>${VITAL_LABEL[k]}</span><span>${val}</span></div>` +
      `<div class="track"><span class="fill ${vitClass(val)}" style="width:${val}%"></span></div></div>`;
  }).join("");

  const ruck = ["wood", "food", "stone", "fiber"].map(
    (k) => `<span>${RES_EMOJI[k]} ${inv[k] ?? 0}</span>`
  ).join("");
  const gearChips = [];
  if (gear.main_hand) gearChips.push(`<span>🪓 ${esc(gear.main_hand)}</span>`);
  if (gear.body) gearChips.push(`<span>🧥 ${esc(gear.body)}</span>`);

  const skillRows = Object.entries(sk)
    .sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([k, val]) => `<span>${esc(k)} ${val}</span>`).join("");

  const partners = p.partners || [];
  const relRows = Object.entries(rel)
    .sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([id, val]) =>
      `<div class="rel-row"><span>${esc(nm(id))}${partners.includes(id) ? " 💞" : ""}</span>` +
      `<b class="${val < 0 ? "neg" : ""}">${val >= 0 ? "+" : ""}${val}</b></div>`
    ).join("");

  const fam = [];
  if (p.mother_id) fam.push(`<span>mother: ${esc(nm(p.mother_id))}</span>`);
  if (p.father_id) fam.push(`<span>father: ${esc(nm(p.father_id))}</span>`);
  if (p.partner_id) fam.push(`<span>partner: ${esc(nm(p.partner_id))}</span>`);

  const tags = [];
  if (p.elder) tags.push("👵 elder");
  if (p.pregnant) tags.push("🤰 pregnant");
  if (p.child) tags.push("👶 child");
  if (p.mental_break) tags.push(`💢 ${esc(p.mental_break)}`);
  if (p.traits && p.traits.length) tags.push(p.traits.map(esc).join(", "));

  const head =
    `<div class="dossier-head">` +
    `<div class="big">${esc(p.title ? `${p.name} ${p.title}` : p.name)}</div>` +
    `<div class="sub">${esc(p.job || "colonist")} · ${p.sex === "F" ? "♀" : "♂"}` +
    (tags.length ? ` · ${tags.join(" · ")}` : "") + `</div>` +
    `<span class="status${p.status !== "active" ? " bad" : ""}">${esc(p.status || "active")}</span>` +
    `</div>`;

  const goalBlock = goal
    ? `<div class="goal">🎯 ${esc(goal.text || goal.kind)}` +
      `<div class="gbar"><i style="width:${goal.needed ? Math.min(100, Math.round(100 * (goal.progress || 0) / goal.needed)) : 0}%"></i></div></div>`
    : `<div class="kv"><span>none yet</span></div>`;

  dossierBody.innerHTML =
    head +
    `<div class="dossier-block">${bars}</div>` +
    `<div class="dossier-block"><div class="h">Gear</div><div class="kv">${gearChips.length ? gearChips.join("") : "<span>bare hands</span>"}</div></div>` +
    `<div class="dossier-block"><div class="h">Rucksack</div><div class="kv">${ruck}</div></div>` +
    (skillRows ? `<div class="dossier-block"><div class="h">Skills</div><div class="kv">${skillRows}</div></div>` : "") +
    `<div class="dossier-block"><div class="h">Goal</div>${goalBlock}</div>` +
    (relRows ? `<div class="dossier-block"><div class="h">Relationships</div>${relRows}</div>` : "") +
    (fam.length ? `<div class="dossier-block"><div class="h">Family</div><div class="kv">${fam.join("")}</div></div>` : "");
}

function toggleLore() {
  if (loreEl.classList.contains("hidden")) {
    loreEl.classList.remove("hidden");
    renderLore(loreTab);
  } else {
    loreEl.classList.add("hidden");
  }
}

function setLoreTab(tab) {
  loreTab = tab;
  for (const t of loreEl.querySelectorAll(".tab")) {
    t.classList.toggle("active", t.dataset.tab === tab);
  }
  renderLore(tab);
}

function renderLore(tab) {
  const l = (snap && snap.lore) || {};
  const body = [];
  if (tab === "graveyard") {
    const g = l.graveyard || [];
    if (!g.length) body.push('<div class="lore-empty">🪦 The graveyard is empty.</div>');
    for (const e of g) {
      const bel = e.beloved ? " 💖" : "";
      body.push(
        `<div class="lore-item">` +
        `<div class="lore-title">🪦 ${esc(e.name)}${e.title ? " " + esc(e.title) : ""}${bel} <span class="tick">· died tick ${e.died_tick}</span></div>` +
        `<div class="lore-sub">${esc(e.cause || "unknown cause")} · born tick ${e.born_tick ?? "?"}</div>` +
        (e.epitaph ? `<div class="lore-text">“${esc(e.epitaph)}”</div>` : "") +
        `</div>`
      );
    }
  } else if (tab === "monument") {
    const m = l.monument || {};
    body.push('<div class="lore-headline">🗿 The Monolith</div>');
    body.push(
      `<div class="lore-meta">wood ${m.wood}/20 · stone ${m.stone}/15 · ` +
      `${m.done ? "✅ finished" : "🏗️ under construction"}</div>`
    );
    if (m.inscription) {
      body.push(`<div class="lore-item"><div class="lore-text">“${esc(m.inscription)}”</div></div>`);
    } else if (m.done) {
      body.push('<div class="lore-empty">No inscription has been carved yet.</div>');
    }
    for (const r of m.runes || []) {
      body.push(
        `<div class="lore-item"><div class="lore-title">✍️ ${esc(r.title)} <span class="tick">· tick ${r.tick}</span></div>` +
        `<div class="lore-text">${esc(r.text)}</div></div>`
      );
    }
  } else if (tab === "chronicle") {
    const c = l.chronicle || [];
    if (!c.length) body.push('<div class="lore-empty">📜 No seasons have been chronicled yet.</div>');
    for (const e of c) {
      body.push(
        `<div class="lore-item"><div class="lore-title">${esc(e.season)} — ${esc(e.title)} <span class="tick">· tick ${e.tick}</span></div>` +
        `<div class="lore-text">${esc(e.text)}</div></div>`
      );
    }
  } else if (tab === "patches") {
    const p = l.patches || [];
    if (!p.length) body.push('<div class="lore-empty">⚙️ The Architect has not patched the world yet.</div>');
    for (const e of p) {
      const notes = Array.isArray(e.notes) ? e.notes : [];
      const n = notes.length
        ? `<div class="lore-sub">${notes.map(esc).join(" · ")}</div>`
        : "";
      body.push(
        `<div class="lore-item"><div class="lore-title">⚙️ ${esc(e.version)} — ${esc(e.title || "balance pass")} <span class="tick">· tick ${e.tick}</span></div>${n}` +
        (e.text ? `<div class="lore-text">${esc(e.text)}</div>` : "") +
        `</div>`
      );
    }
  }
  loreBody.innerHTML = body.join("");
}

// ---- snapshot apply ----
function applySnapshot(s) {
  snap = s;
  snapTime = performance.now();
  snowing = isSnowing(s);
  if (!snowing) snow.length = 0;
  Objects.sync(s.grid, tileXY, (s.biome && s.biome.campfire) || 0);
  syncPawns(s);
  syncCreatures(s);
  updateChat(s);
  addEmotes(s);
  updateHud(s);
  updateRoster(s);
  updateLog(s);
  if (selectedId) {
    const p = (s.pawns || []).find((x) => x.id === selectedId);
    if (p) renderDossier(p);
    else deselectPawn();
  }
}

// ---- animation loop ----
function frame(now) {
  applyView();
  if (snap) {
    const elapsed = (now - snapTime) / 1000;
    for (const rec of pawns.values()) {
      let x = rec.x;
      let y = rec.y;
      if (rec.moving && elapsed < WALK_SECONDS) {
        const t = Math.min(1, elapsed / WALK_SECONDS);
        x = rec.px + (rec.x - rec.px) * easeInOut(t);
        y = rec.py + (rec.y - rec.py) * t - Math.sin(t * Math.PI) * 10;
        if (elapsed >= WALK_SECONDS) rec.moving = false;
      } else {
        let bobAmp = 2.5, bobFreq = 520, spriteRot = 0;
        switch (rec.action) {
          case "Chop": bobAmp = 4; bobFreq = 230; spriteRot = 0.16; break;
          case "Forage": bobAmp = 4; bobFreq = 300; spriteRot = 0.08; break;
          case "Build": bobAmp = 3; bobFreq = 340; break;
          case "Scout": bobAmp = 3; bobFreq = 700; spriteRot = 0.06; break;
          case "Rest": bobAmp = 1.5; bobFreq = 900; break;
          case "Attack": bobAmp = 4; bobFreq = 180; spriteRot = 0.2; break;
        }
        const bob = Math.abs(Math.sin(now / bobFreq + rec.phase)) * bobAmp;
        y -= bob;
        rec.cv.style.transform = spriteRot
          ? `translateX(-50%) rotate(${Math.sin(now / bobFreq + rec.phase) * spriteRot}rad)`
          : "";
        if (elapsed > BUBBLE_DELAY + BUBBLE_LIFE && now > rec.nextEmote) {
          const emo = ACTION_EMOTE[rec.action];
          if (emo) spawnEmote(emo, x, y - 46);
          rec.nextEmote = now + 4000 + Math.random() * 4000;
        }
      }
      // Animated sprite: idle stance, or alternating walk stride while moving.
      const want = rec.moving ? (Math.floor(now / 170) % 2 === 0 ? "a" : "b") : "i";
      if (rec.drawn !== want) {
        rec.drawn = want;
        const src = want === "i" ? rec.idleCv : want === "a" ? rec.walkA : rec.walkB;
        const g = rec.cv.getContext("2d");
        g.clearRect(0, 0, Sprites.PAWN_CV_W, Sprites.PAWN_CV_H);
        if (src) g.drawImage(src, 0, 0);
      }
      rec.el.style.left = x + "px";
      rec.el.style.top = y + "px";
      // Pawns ride a z-band just above the standing-object layer (objects 4..~32)
      // so they're never hidden behind trees/rocks, but still below the HUD (z 40).
      rec.el.style.zIndex = String(33 + Math.min(5, Math.max(0, Objects.depthZ(y) - 4)));
    }
    for (const rec of creatures.values()) {
      const bob = Math.abs(Math.sin(now / 700 + rec.phase)) * 3;
      let cx = rec.x, cy = rec.y;
      // Glide between tiles (wildlife/visitors/raiders have no prev_pos in the
      // snapshot, so we animate the delta we saw on the previous snapshot).
      if (rec.moving) {
        if (elapsed < CREATURE_GLIDE) {
          const t = Math.min(1, elapsed / CREATURE_GLIDE);
          cx = rec.px + (rec.x - rec.px) * easeInOut(t);
          cy = rec.py + (rec.y - rec.py) * easeInOut(t);
        } else {
          rec.moving = false;
        }
      }
      rec.el.style.left = cx + "px";
      rec.el.style.top = cy - bob + "px";
      rec.el.style.zIndex = String(33 + Math.min(5, Math.max(0, Objects.depthZ(cy) - 4)));
    }
    Objects.tick(now);
    drawWorld(now);
  } else {
    ctx.clearRect(0, 0, STAGE_W, STAGE_H);
  }
  requestAnimationFrame(frame);
}

// ---- websocket ----
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/`);
  ws.onopen = () => {
    connEl.textContent = "● live";
    connEl.classList.add("live");
  };
  ws.onmessage = (ev) => {
    let msg;
    try {
      msg = JSON.parse(ev.data);
    } catch (e) {
      return;
    }
    if (msg && msg.type === "world") applySnapshot(msg);
  };
  ws.onclose = () => {
    connEl.textContent = "○ reconnecting";
    connEl.classList.remove("live");
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 2000);
  };
  ws.onerror = () => {
    try {
      ws.close();
    } catch (e) { /* already closed */ }
  };
}

resize();
connect();
requestAnimationFrame(frame);

// ---- HUD event wiring ----
loreBtn.addEventListener("click", toggleLore);
dossierClose.addEventListener("click", deselectPawn);
loreClose.addEventListener("click", () => loreEl.classList.add("hidden"));
for (const t of loreEl.querySelectorAll(".tab")) {
  t.addEventListener("click", () => setLoreTab(t.dataset.tab));
}
rosterBtn.addEventListener("click", () => rosterEl.classList.toggle("hidden"));
rosterClose.addEventListener("click", () => rosterEl.classList.add("hidden"));
stage.addEventListener("click", () => { if (!suppressClick) deselectPawn(); });

// ---- zoom control buttons ----
const zoomInBtn = document.getElementById("zoomIn");
const zoomOutBtn = document.getElementById("zoomOut");
const zoomResetBtn = document.getElementById("zoomReset");
function zoomBy(f) {
  view.zoom = clamp(view.zoom * f, ZOOM_MIN, ZOOM_MAX);
  clampPan();
}
zoomInBtn.addEventListener("click", () => zoomBy(1.2));
zoomOutBtn.addEventListener("click", () => zoomBy(1 / 1.2));
zoomResetBtn.addEventListener("click", () => { view.zoom = 1; view.panX = 0; view.panY = 0; });
