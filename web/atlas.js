/* eslint-env browser */
/**
 * atlas.js — vendored Serene Village tile atlas.
 *
 * Loads the three vendored PNGs (CC-BY 4.0, LimeZu "Serene Village — revamped")
 * and slices them into cached canvases keyed by name. All coordinates are the
 * user-verified pixel boxes from web/TILES.md (locked 2026-08-17).
 *
 * API:
 *   Atlas.ready          — Promise resolving when all sheets have loaded
 *   Atlas.onReady(cb)    — convenience: runs cb when ready (or immediately)
 *   Atlas.slice(name)    — native-size canvas for a named slice (cached)
 *   Atlas.scaled(name, s)– nearest-neighbour scaled canvas (cached per scale)
 *   Atlas.ground(type, x, y) — grass/dirt/water ground tile canvas (TILE×TILE)
 *   Atlas.waterFrame(i)  — water-wave frame canvas (14 frames)
 *   Atlas.fireFrame(i)   — campfire frame canvas (4 frames)
 *
 * Never smooth-scale: every draw uses nearest-neighbour (pixel art stays crisp).
 */
(function () {
  "use strict";

  const SHEETS = {
    master: "assets/Serene_Village_16x16.png",
    fire: "assets/campfire.png",
    water: "assets/water_waves.png",
  };

  // ---- Locked slice table (pixel boxes into the master sheet) ------------
  // x, y, w, h — source pixel coords in Serene_Village_16x16.png
  const SLICES = {
    tree1: { x: 144, y: 201, w: 32, h: 39 },
    tree2: { x: 177, y: 201, w: 32, h: 39 },
    tree3: { x: 208, y: 201, w: 32, h: 39 },
    bush: { x: 113, y: 194, w: 14, h: 14 },
    flowers: { x: 65, y: 194, w: 14, h: 13 },
    cottage: { x: 87, y: 404, w: 67, h: 55 },
    rocks: { x: 3, y: 298, w: 24, h: 22 },
    ruins: { x: 0, y: 48, w: 47, h: 32 },
    dirt: { x: 96, y: 16, w: 12, h: 48 },
    water: { x: 141, y: 84, w: 8, h: 8 },
    shoreN: { x: 59, y: 67, w: 74, h: 14 },
    shoreS: { x: 59, y: 94, w: 74, h: 14 },
    shoreE: { x: 126, y: 75, w: 12, h: 29 },
    shoreW: { x: 55, y: 75, w: 12, h: 29 },
    fenceH: { x: 64, y: 276, w: 48, h: 11 },
    fenceV: { x: 102, y: 244, w: 4, h: 43 },
    path: { x: 35, y: 158, w: 26, h: 15 },
    wellTop: { x: 191, y: 530, w: 8, h: 7 },
    wellBot: { x: 192, y: 537, w: 6, h: 4 },
    // Flat grass ground tile (tile 5,0 in the master sheet)
    grass: { x: 80, y: 0, w: 16, h: 16 },
  };

  // Frames on the animation strips (16×16 each)
  const FIRE_FRAMES = 4;   // campfire.png: 64×16
  const WATER_FRAMES = 14; // water_waves.png: 224×16

  const images = {};
  const sliceCache = {};      // name -> native canvas
  const scaledCache = {};     // name|scale -> canvas

  // ---- image loading -----------------------------------------------------
  function load(src) {
    return new Promise(function (resolve, reject) {
      const img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = function () { reject(new Error("atlas: failed to load " + src)); };
      img.src = src;
    });
  }

  const readyPromise = Promise.all(
    Object.keys(SHEETS).map(function (key) {
      return load(SHEETS[key]).then(function (img) { images[key] = img; });
    })
  ).then(function () {
    return true;
  });

  function onReady(cb) {
    readyPromise.then(cb).catch(function (err) { console.error(err); });
  }

  // ---- slicing -----------------------------------------------------------
  function makeCanvas(w, h) {
    const cv = document.createElement("canvas");
    cv.width = w;
    cv.height = h;
    return cv;
  }

  function drawSlice(dst, img, sx, sy, sw, sh, dx, dy) {
    const ctx = dst.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(img, sx, sy, sw, sh, dx, dy, sw, sh);
  }

  /** Native-size canvas for a named slice (cached). */
  function slice(name) {
    const spec = SLICES[name];
    if (!spec) { throw new Error("atlas: unknown slice '" + name + "'"); }
    if (!sliceCache[name]) {
      const cv = makeCanvas(spec.w, spec.h);
      drawSlice(cv, images.master, spec.x, spec.y, spec.w, spec.h, 0, 0);
      sliceCache[name] = cv;
    }
    return sliceCache[name];
  }

  /** Nearest-neighbour scaled canvas for a named slice (cached per scale). */
  function scaled(name, scale) {
    const key = name + "|" + scale;
    if (!scaledCache[key]) {
      const src = slice(name);
      const cv = makeCanvas(Math.max(1, Math.round(src.width * scale)),
                            Math.max(1, Math.round(src.height * scale)));
      const ctx = cv.getContext("2d");
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(src, 0, 0, src.width, src.height, 0, 0, cv.width, cv.height);
      scaledCache[key] = cv;
    }
    return scaledCache[key];
  }

  // ---- tiles -------------------------------------------------------------
  // Deterministic pseudo-noise per (type,x,y) so ground texture is stable.
  function noise(x, y) {
    let n = (x * 374761393 + y * 668265263) | 0;
    n = (n ^ (n >> 13)) * 1274126177;
    return ((n ^ (n >> 16)) >>> 0) / 4294967295;
  }

  const GRASS_TINTS = [
    [0, 0, 0, 0],          // none
    [-4, 4, -2, 0],        // slightly cooler
    [3, -2, 4, 0],         // slightly warmer
  ];

  function tinted(dst, r, g, b, a) {
    if (!r && !g && !b) { return; }
    const ctx = dst.getContext("2d");
    ctx.globalCompositeOperation = "source-atop";
    ctx.fillStyle = "rgba(" + r + "," + g + "," + b + "," + a + ")";
    ctx.fillRect(0, 0, dst.width, dst.height);
    ctx.globalCompositeOperation = "source-over";
  }

  function grassCanvas(x, y) {
    const cv = makeCanvas(16, 16);
    drawSlice(cv, images.master, SLICES.grass.x, SLICES.grass.y, 16, 16, 0, 0);
    // subtle deterministic tint variation so the map doesn't look flat
    const t = GRASS_TINTS[Math.floor(noise(x, y) * GRASS_TINTS.length)];
    tinted(cv, t[0], t[1], t[2], 26);
    return cv;
  }

  function dirtCanvas(x, y) {
    // dirt strip is 12×48; use a 12×16 window seeded per tile.
    // Cap the seed at 32 so (y + 16) never exceeds the 48px strip height
    // (seeds 33–35 would read out of bounds and leave the tile transparent).
    const cv = makeCanvas(16, 16);
    const seed = Math.floor(noise(x, y) * 33); // 0..32
    const src = images.master;
    const ctx = cv.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(src, SLICES.dirt.x, SLICES.dirt.y + seed, 12, 16, 2, 0, 12, 16);
    // patch the 2px side gutters with a strip repeat
    ctx.drawImage(cv, 2, 0, 2, 16, 0, 0, 2, 16);
    ctx.drawImage(cv, 2, 0, 2, 16, 14, 0, 2, 16);
    return cv;
  }

  function waterCanvas() {
    if (!sliceCache.waterTile) {
      const cv = makeCanvas(16, 16);
      drawSlice(cv, images.master, SLICES.water.x, SLICES.water.y, 8, 8, 4, 4);
      sliceCache.waterTile = cv;
    }
    return sliceCache.waterTile;
  }

  function farmCanvas(x, y) {
    // Tilled soil: dirt base + horizontal furrow rows (darker groove + ridge).
    const cv = dirtCanvas(x, y);
    const g = cv.getContext("2d");
    g.imageSmoothingEnabled = false;
    for (let f = 0; f < 4; f++) {
      const fy = 2 + f * 4; // rows 2, 6, 10, 14 of the 16px tile
      g.fillStyle = "rgba(50,32,16,0.55)";
      g.fillRect(0, fy, 16, 1);
      g.fillStyle = "rgba(255,232,185,0.16)";
      g.fillRect(0, fy + 1, 16, 1);
    }
    return cv;
  }

  function ashCanvas(x, y) {
    // Pale gray ash field (after a fire or miasma has passed).
    const cv = makeCanvas(16, 16);
    const g = cv.getContext("2d");
    g.imageSmoothingEnabled = false;
    for (let j = 0; j < 16; j++) {
      for (let i = 0; i < 16; i++) {
        const n = noise(x * 16 + i, y * 16 + j);
        const v = 66 + (n - 0.5) * 22 - (n > 0.8 ? 30 : 0);
        g.fillStyle = "rgb(" + Math.max(0, Math.round(v)) + "," +
          Math.max(0, Math.round(v * 0.9)) + "," + Math.max(0, Math.round(v * 0.84)) + ")";
        g.fillRect(i, j, 1, 1);
      }
    }
    return cv;
  }

  function scorchCanvas(x, y) {
    // Charred black earth with faint ember specks (wildfire tile).
    const cv = makeCanvas(16, 16);
    const g = cv.getContext("2d");
    g.imageSmoothingEnabled = false;
    for (let j = 0; j < 16; j++) {
      for (let i = 0; i < 16; i++) {
        const n = noise(x * 16 + i, y * 16 + j);
        let r, g2, b;
        if (n > 0.93) { r = 130; g2 = 62; b = 28; }       // ember speck
        else if (n > 0.86) { r = 74; g2 = 50; b = 36; }
        else { r = 42 - n * 14; g2 = 36 - n * 12; b = 32 - n * 10; }
        g.fillStyle = "rgb(" + Math.max(0, Math.round(r)) + "," +
          Math.max(0, Math.round(g2)) + "," + Math.max(0, Math.round(b)) + ")";
        g.fillRect(i, j, 1, 1);
      }
    }
    return cv;
  }

  /** 16×16 ground canvas for a tile type at grid (x,y). */
  function ground(type, x, y) {
    const key = "ground|" + type + "|" + x + "|" + y;
    if (!sliceCache[key]) {
      let tile16;
      if (type === "grass") { tile16 = grassCanvas(x, y); }
      else if (type === "dirt") { tile16 = dirtCanvas(x, y); }
      else if (type === "farm") { tile16 = farmCanvas(x, y); }
      else if (type === "ash") { tile16 = ashCanvas(x, y); }
      else if (type === "scorch") { tile16 = scorchCanvas(x, y); }
      else if (type === "water") { tile16 = waterCanvas(); }
      else { tile16 = grassCanvas(x, y); }
      sliceCache[key] = tile16;
    }
    return sliceCache[key];
  }

  // ---- animation frames ---------------------------------------------------
  function frameStrip(sheetKey, frames) {
    const arr = [];
    const img = images[sheetKey];
    for (let i = 0; i < frames; i++) {
      const cv = makeCanvas(16, 16);
      drawSlice(cv, img, i * 16, 0, 16, 16, 0, 0);
      arr.push(cv);
    }
    return arr;
  }

  let waterFramesCache = null;
  function waterFrame(i) {
    if (!waterFramesCache) { waterFramesCache = frameStrip("water", WATER_FRAMES); }
    return waterFramesCache[i % WATER_FRAMES];
  }

  let fireFramesCache = null;
  function fireFrame(i) {
    if (!fireFramesCache) { fireFramesCache = frameStrip("fire", FIRE_FRAMES); }
    return fireFramesCache[i % FIRE_FRAMES];
  }

  // ---- public API ---------------------------------------------------------
  window.Atlas = {
    ready: readyPromise,
    onReady: onReady,
    slice: slice,
    scaled: scaled,
    ground: ground,
    waterFrame: waterFrame,
    fireFrame: fireFrame,
    WATER_FRAMES: WATER_FRAMES,
    FIRE_FRAMES: FIRE_FRAMES,
    _sheets: SHEETS,
    _slices: SLICES,
  };
})();
