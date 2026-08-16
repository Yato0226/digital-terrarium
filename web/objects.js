/* Phase 6 Step 12 Part C: DOM y-sorted standing objects (vendored tiles).
 *
 * Builds per-tile DOM sprites from the vendored atlas (trees, bush, flowers,
 * rocks, ruins, cottage + animated campfire, well, fences) plus procedural
 * sprouts (farm) and ash mounds, all into the shared #sprites layer so they
 * y-sort against pawns/creatures: z-index = Objects.depthZ(anchorY) keeps a
 * bounded 4..35 band (below the #log/#chat panels at z-40, above the canvas).
 *
 * The layer rebuilds only when the grid signature changes; the campfire pit
 * animates per-frame via Objects.tick() (flame frames when lit, a stone pit
 * when not). Deterministic per-tile noise keeps jitter/variants stable.
 */
"use strict";

window.Objects = (function () {
  const els = [];
  let container = null;
  let lastSig = null;
  let lit = false;
  let campfireObj = null; // { g, w, h, lastFrame, drawnLit }
  let atlasOk = false;
  let pending = null;     // { grid, topFn } deferred until Atlas.ready

  /** Bounded depth z-index for a screen anchor Y (stays under #log z-40). */
  function depthZ(y) {
    return 4 + Math.round((y - 150) / 20);
  }

  // Deterministic per-tile noise (same family as atlas.js).
  function n(x, y, salt) {
    let h = (x * 374761393 + y * 668265263 + salt * 1442695041) | 0;
    h = (h ^ (h >> 13)) * 1274126177;
    return ((h ^ (h >> 16)) >>> 0) / 4294967295;
  }

  function scaledCanvas(src, scale) {
    const cv = document.createElement("canvas");
    cv.width = Math.max(1, Math.round(src.width * scale));
    cv.height = Math.max(1, Math.round(src.height * scale));
    const g = cv.getContext("2d");
    g.imageSmoothingEnabled = false;
    g.drawImage(src, 0, 0, src.width, src.height, 0, 0, cv.width, cv.height);
    return cv;
  }

  /** Create a positioned object sprite anchored bottom-centre at (x, y).
   *  Returns { div, c, g } so animated sprites can redraw their canvas. */
  function add(cv, x, y, cls, delay) {
    const div = document.createElement("div");
    div.className = "obj" + (cls ? " " + cls : "");
    if (delay !== undefined) div.style.animationDelay = delay + "s";
    const c = document.createElement("canvas");
    c.className = "obj-cv";
    c.width = cv.width;
    c.height = cv.height;
    const g = c.getContext("2d");
    g.imageSmoothingEnabled = false;
    g.drawImage(cv, 0, 0);
    div.appendChild(c);
    div.style.marginLeft = -(cv.width / 2) + "px";
    div.style.marginTop = -cv.height + "px";
    div.style.left = x + "px";
    div.style.top = y + "px";
    div.style.zIndex = String(depthZ(y));
    container.appendChild(div);
    els.push(div);
    return { div, c, g };
  }

  // ---- per-tile builders --------------------------------------------------

  function buildTree(x, y, cx, cy) {
    const v = 1 + Math.floor(n(x, y, 3) * 3); // tree1..tree3
    const cv = Atlas.scaled("tree" + v, 4);   // 32×39 → 128×156
    const jx = (n(x, y, 7) - 0.5) * 26;
    const jy = (n(x, y, 11) - 0.5) * 18;
    add(cv, cx + jx, cy + 26 + jy, "sway", -n(x, y, 5) * 5);
  }

  function buildBush(x, y, cx, cy) {
    const jx = (n(x, y, 13) - 0.5) * 22;
    add(Atlas.scaled("bush", 5), cx + jx, cy + 30);          // 14×14 → 70×70
    if (n(x, y, 19) > 0.5) {
      add(Atlas.scaled("flowers", 4), cx + jx + 24, cy + 34); // 14×13 → 56×52
    }
  }

  function buildRocks(x, y, cx, cy) {
    const jx = (n(x, y, 23) - 0.5) * 18;
    add(Atlas.scaled("rocks", 5), cx + jx, cy + 32);          // 24×22 → 120×110
    if (n(x, y, 29) > 0.5) {
      add(Atlas.scaled("rocks", 3), cx + jx + 36, cy + 20);   // depth rock
    }
  }

  function buildRuins(x, y, cx, cy) {
    const jx = (n(x, y, 31) - 0.5) * 12;
    add(Atlas.scaled("ruins", 3), cx + jx, cy + 30);          // 47×32 → 141×96
  }

  function buildFarm(x, y, cx, cy) {
    const sprout = Sprites.SPRITES.sprout;                    // 12×4 → 60×20
    for (let i = 0; i < 3; i++) {
      const jx = (n(x, y, 37 + i) - 0.5) * 64;
      const jy = 18 + Math.floor(n(x, y, 41 + i) * 40);
      add(scaledCanvas(sprout, 5), cx + jx, cy + jy, "sway", -n(x, y, 43 + i) * 4);
    }
  }

  function buildAsh(x, y, cx, cy) {
    const mound = Sprites.SPRITES.ashmound;                   // 11×4 → 55×20
    for (let i = 0; i < 2; i++) {
      const jx = (n(x, y, 47 + i) - 0.5) * 60;
      const jy = 22 + Math.floor(n(x, y, 53 + i) * 34);
      add(scaledCanvas(mound, 5), cx + jx, cy + jy);
    }
  }

  function drawCold(o) {
    const g = o.g;
    g.clearRect(0, 0, o.w, o.h);
    g.imageSmoothingEnabled = false;
    const r = o.w * 0.38;
    const cy = o.h * 0.8;
    g.fillStyle = "#4a3a2c";
    g.beginPath();
    g.arc(o.w / 2, cy, r, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = "#241a10";
    g.beginPath();
    g.arc(o.w / 2, cy, r * 0.62, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = "#5a4430";
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * Math.PI * 2;
      g.beginPath();
      g.arc(o.w / 2 + Math.cos(a) * r * 0.8, cy + Math.sin(a) * r * 0.4, o.w * 0.05, 0, Math.PI * 2);
      g.fill();
    }
  }

  function buildCamp(x, y, cx, cy) {
    // Cottage: 67×55 → 134×110, anchored just below tile centre.
    add(Atlas.scaled("cottage", 2), cx, cy + 26);
    // Well: top (8×7) + base (6×4) composed 8×11, then 6× → 48×66.
    const well = document.createElement("canvas");
    well.width = 8;
    well.height = 11;
    const wg = well.getContext("2d");
    wg.imageSmoothingEnabled = false;
    wg.drawImage(Atlas.slice("wellBot"), 1, 7);
    wg.drawImage(Atlas.slice("wellTop"), 0, 0);
    add(scaledCanvas(well, 6), cx - 32, cy - 22);
    // Animated campfire pit: 16×16 frame at 5× → 80×80, redrawn by tick()
    // onto the *displayed* canvas (add() returns the live canvas context).
    const pit = document.createElement("canvas");
    pit.width = 80;
    pit.height = 80;
    const fg = pit.getContext("2d");
    fg.imageSmoothingEnabled = false;
    fg.drawImage(Atlas.fireFrame(0), 0, 0, 80, 80);
    const placed = add(pit, cx + 18, cy + 30);
    campfireObj = { g: placed.g, w: 80, h: 80, lastFrame: 0, drawnLit: lit };
    if (!lit) drawCold(campfireObj);
    // Fence rail along the camp tile's north edge + corner posts.
    add(Atlas.scaled("fenceH", 3), cx, cy - 52);      // 48×11 → 144×33
    add(Atlas.scaled("fenceV", 2), cx - 72, cy - 52); // 4×43 → 8×86
    add(Atlas.scaled("fenceV", 2), cx + 72, cy - 52);
  }

  // ---- layer lifecycle ----------------------------------------------------

  function build(grid, topFn) {
    if (!container) return;
    for (const el of els) {
      if (el.parentNode === container) container.removeChild(el);
    }
    els.length = 0;
    campfireObj = null;

    for (let y = 0; y < grid.length; y++) {
      for (let x = 0; x < grid[y].length; x++) {
        const tile = grid[y][x];
        const c = topFn(x, y);
        if (tile === "🌲") buildTree(x, y, c.x, c.y);
        else if (tile === "🫐") buildBush(x, y, c.x, c.y);
        else if (tile === "🪨") buildRocks(x, y, c.x, c.y);
        else if (tile === "💀") buildRuins(x, y, c.x, c.y);
        else if (tile === "🏕️") buildCamp(x, y, c.x, c.y);
        else if (tile === "🌾") buildFarm(x, y, c.x, c.y);
        else if (tile === "🌫️") buildAsh(x, y, c.x, c.y);
      }
    }
  }

  /** Called on every snapshot: rebuild when the grid changed, else just
   *  refresh the campfire lit/unlit state. Builds are deferred until the
   *  vendored tiles have decoded (mirrors app.js's `atlasReady` guard). */
  function sync(grid, topFn, campfireGauge) {
    lit = (campfireGauge || 0) > 0;
    if (!container || !grid) return;
    const sig = grid.join("\n");
    if (sig === lastSig) return;
    lastSig = sig;
    if (!atlasOk) { pending = { grid, topFn }; return; }
    build(grid, topFn);
  }

  /** Per-frame animation: campfire flame frames (or cold pit when unlit). */
  function tick(now) {
    if (!campfireObj) return;
    const o = campfireObj;
    if (!lit) {
      if (o.drawnLit) { drawCold(o); o.drawnLit = false; }
      return;
    }
    const frame = Math.floor(now / 120) % 4;
    if (o.drawnLit && frame === o.lastFrame) return;
    o.lastFrame = frame;
    o.drawnLit = true;
    o.g.clearRect(0, 0, o.w, o.h);
    o.g.imageSmoothingEnabled = false;
    o.g.drawImage(Atlas.fireFrame(frame), 0, 0, o.w, o.h);
  }

  // Build the deferred layer as soon as the vendored tiles are available.
  Atlas.onReady(() => {
    atlasOk = true;
    if (pending) {
      const { grid, topFn } = pending;
      pending = null;
      build(grid, topFn);
    }
  });

  return {
    attach: (el) => { container = el; },
    sync,
    tick,
    depthZ,
  };
})();
