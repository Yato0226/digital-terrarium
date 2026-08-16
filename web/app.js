/* Phase 6 Steps 2–3: the floating isometric diorama client.
 *
 * Timeline for each 60s tick (matches TICK_INTERVAL_SECONDS):
 *   0–4s   pawns whose tile changed walk diagonally across the island
 *   4–12s  comic speech (quote) and thought (inner_monologue) bubbles
 *   12–60s looping idle animation + periodic action emotes
 *   always floating smoke, river shimmer, swaying trees, night tint
 *
 * Zero dependencies: vanilla JS + Canvas2D + DOM overlays.
 */
"use strict";

const STAGE_W = 1000;
const STAGE_H = 640;
const TILE_W = 120;
const TILE_H = 60;
const ORIGIN_X = 500;
const ORIGIN_Y = 250;

const WALK_SECONDS = 4;
const BUBBLE_DELAY = 4;
const BUBBLE_LIFE = 8;

const TILE_STYLE = {
  "🌲": { fill: "#2e7d32", edge: "#1b5e20" },
  "🌊": { fill: "#1e88e5", edge: "#0d47a1" },
  "🫐": { fill: "#8bc34a", edge: "#558b2f" },
  "🪨": { fill: "#9e9e9e", edge: "#616161" },
  "💀": { fill: "#607d8b", edge: "#37474f" },
  "🏕️": { fill: "#f9a825", edge: "#f57f17" },
  "🔥": { fill: "#ef6c00", edge: "#bf360c" },
  "🌫️": { fill: "#bcaaa4", edge: "#8d6e63" },
};

const VISITOR_EMOJI = { Merchant: "🧳", Wanderer: "🥾", Bard: "🎻" };

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
  frenzy: "💥", starve_break: "🥀", worship: "🕯️",
};

// ---- DOM refs ----
const stage = document.getElementById("stage");
const canvas = document.getElementById("island");
const ctx = canvas.getContext("2d");
const spritesEl = document.getElementById("sprites");
const bubbleLayer = document.getElementById("bubbles");
const emoteLayer = document.getElementById("emotes");
const titleEl = document.getElementById("title");
const connEl = document.getElementById("conn");
const tickerEl = document.getElementById("ticker");

// ---- live state ----
let snap = null;
let snapTime = 0;
const pawns = new Map();       // id -> pawn record
const creatures = new Map();   // "type:id" -> creature record
const bubbles = new Map();     // key -> {el, rec, kind}
const particles = [];
let reconnectTimer = null;

// ---- small helpers ----
function iso(x, y) {
  return {
    x: ORIGIN_X + (x - y) * (TILE_W / 2),
    y: ORIGIN_Y + (x + y) * (TILE_H / 2),
  };
}

function hashHue(name) {
  let h = 0;
  for (const ch of String(name)) h = (h * 31 + ch.codePointAt(0)) % 360;
  return h;
}

function easeInOut(t) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

function pawnFigure(p) {
  if (p.child) return "👶";
  if (p.elder) return p.sex === "F" ? "👵" : "👴";
  return p.sex === "F" ? "👩" : "👨";
}

function diamond(cx, cy, w, h) {
  ctx.moveTo(cx, cy - h / 2);
  ctx.lineTo(cx + w / 2, cy);
  ctx.lineTo(cx, cy + h / 2);
  ctx.lineTo(cx - w / 2, cy);
  ctx.closePath();
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

// ---- resize ----
function resize() {
  const scale = Math.min(
    (window.innerWidth - 10) / STAGE_W,
    (window.innerHeight - 10) / STAGE_H,
    1
  );
  stage.style.transform = `scale(${scale})`;
}
window.addEventListener("resize", resize);

// ---- canvas: the floating island ----
function drawIsland(now) {
  ctx.clearRect(0, 0, STAGE_W, STAGE_H);
  if (!snap) return;
  const grid = snap.grid;
  const t = now;

  // Cutaway layers underneath (bottom -> top: stone to dirt).
  const layers = [
    { cy: 370 + 54, scale: 1.18, fill: "#263238", edge: "#1b232a" },
    { cy: 370 + 40, scale: 1.12, fill: "#37474f", edge: "#263238" },
    { cy: 370 + 26, scale: 1.06, fill: "#4e342e", edge: "#3e2723" },
    { cy: 370 + 12, scale: 1.00, fill: "#5d4037", edge: "#4e342e" },
  ];
  for (const L of layers) {
    ctx.beginPath();
    diamond(ORIGIN_X, L.cy, 240 * L.scale, 120 * L.scale);
    ctx.fillStyle = L.fill;
    ctx.fill();
    ctx.strokeStyle = L.edge;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
  // Grass rim around the top face.
  ctx.beginPath();
  diamond(ORIGIN_X, 370, 240, 120);
  ctx.strokeStyle = "#33691e";
  ctx.lineWidth = 4;
  ctx.stroke();

  // Tile diamonds.
  for (let y = 0; y < grid.length; y++) {
    for (let x = 0; x < grid[y].length; x++) {
      const tile = grid[y][x];
      const style = TILE_STYLE[tile] || { fill: "#8d6e63", edge: "#5d4037" };
      const c = iso(x, y);
      ctx.beginPath();
      diamond(c.x, c.y, TILE_W, TILE_H);
      ctx.fillStyle = style.fill;
      ctx.fill();
      ctx.strokeStyle = style.edge;
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
  }

  // Tile glyphs + living effects.
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (let y = 0; y < grid.length; y++) {
    for (let x = 0; x < grid[y].length; x++) {
      const tile = grid[y][x];
      const c = iso(x, y);
      if (tile === "🌊") {
        ctx.font = "26px serif";
        ctx.fillText("🌊", c.x, c.y);
        ctx.fillStyle = "rgba(255,255,255,0.5)";
        for (let i = 0; i < 3; i++) {
          const phase = ((t / 900) * (0.6 + (x + y) * 0.06) + i * 0.33) % 1;
          ctx.beginPath();
          ctx.arc(c.x + (phase - 0.5) * 64, c.y + (i - 1) * 9, 2.4, 0, Math.PI * 2);
          ctx.fill();
        }
        continue;
      }
      if (tile === "🔥") {
        const a = 0.12 + 0.08 * Math.sin(t / 140 + x * 2);
        const g = ctx.createRadialGradient(c.x, c.y, 4, c.x, c.y, 44);
        g.addColorStop(0, `rgba(255,120,40,${a})`);
        g.addColorStop(1, "rgba(255,120,40,0)");
        ctx.fillStyle = g;
        ctx.fillRect(c.x - 44, c.y - 44, 88, 88);
        ctx.font = "26px serif";
        ctx.fillText("🔥", c.x, c.y);
        continue;
      }
      if (tile === "🌲") {
        ctx.save();
        ctx.translate(c.x, c.y);
        ctx.rotate(Math.sin(t / 1100 + x * 0.8 + y * 1.3) * 0.045);
        ctx.font = "30px serif";
        ctx.fillText("🌲", 0, 0);
        ctx.restore();
        continue;
      }
      ctx.font = "26px serif";
      ctx.fillText(tile, c.x, c.y);
    }
  }

  // Campfire flame + smoke (camp is always the (2,2) tile).
  const campfire = (snap.biome && snap.biome.campfire) || 0;
  if (campfire > 0) {
    const camp = iso(2, 2);
    const flick = 0.55 + 0.2 * Math.sin(t / 90) + 0.1 * Math.sin(t / 47 + 2);
    const g = ctx.createRadialGradient(camp.x + 14, camp.y - 10, 2, camp.x + 14, camp.y - 10, 34);
    g.addColorStop(0, `rgba(255,170,60,${0.5 * flick})`);
    g.addColorStop(1, "rgba(255,120,30,0)");
    ctx.fillStyle = g;
    ctx.fillRect(camp.x + 14 - 34, camp.y - 10 - 34, 68, 68);
    ctx.font = "20px serif";
    ctx.fillText("🔥", camp.x + 14, camp.y - 10);
    spawnSmoke(camp.x + 10, camp.y - 14);
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

  // Night tint.
  if (snap.day === 0) {
    ctx.fillStyle = "rgba(10, 14, 40, 0.3)";
    ctx.fillRect(0, 0, STAGE_W, STAGE_H);
    if (campfire > 0) {
      const camp = iso(2, 2);
      const ng = ctx.createRadialGradient(camp.x, camp.y, 10, camp.x, camp.y, 130);
      ng.addColorStop(0, "rgba(255,150,50,0.16)");
      ng.addColorStop(1, "rgba(255,150,50,0)");
      ctx.fillStyle = ng;
      ctx.fillRect(0, 0, STAGE_W, STAGE_H);
    }
  }
}

// ---- pawn & creature sprites ----
function makePawnEl() {
  const el = document.createElement("div");
  el.className = "pawn";
  const ring = document.createElement("div");
  ring.className = "ring";
  const figure = document.createElement("span");
  figure.className = "figure";
  const name = document.createElement("span");
  name.className = "name";
  ring.appendChild(figure);
  el.appendChild(ring);
  el.appendChild(name);
  return el;
}

function syncPawns(s) {
  const seen = new Set();
  for (const p of s.pawns) {
    seen.add(p.id);
    let rec = pawns.get(p.id);
    if (!rec) {
      const el = makePawnEl();
      spritesEl.appendChild(el);
      rec = {
        id: p.id,
        el,
        ring: el.querySelector(".ring"),
        figure: el.querySelector(".figure"),
        name: el.querySelector(".name"),
        action: null,
        nextEmote: 0,
        phase: Math.random() * 7,
        px: 0, py: 0, x: 0, y: 0, moving: false,
      };
      pawns.set(p.id, rec);
    }
    const hue = hashHue(p.name);
    rec.ring.style.background =
      `radial-gradient(circle at 30% 30%, hsl(${hue} 65% 62%), hsl(${hue} 55% 38%))`;
    const fig = pawnFigure(p);
    if (rec.figure.textContent !== fig) rec.figure.textContent = fig;
    const label = p.title ? `${p.name} ${p.title}` : p.name;
    if (rec.name.textContent !== label) rec.name.textContent = label;
    rec.el.classList.remove("leaving");

    const from = iso(p.prev_pos[0], p.prev_pos[1]);
    const to = iso(p.pos[0], p.pos[1]);
    rec.px = from.x; rec.py = from.y;
    rec.x = to.x; rec.y = to.y;
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
    entries.push({ dom: "w:" + w.id, key: w.id, emoji: w.emoji || "🐾", label: w.name || w.species, pos: w.pos });
  }
  for (const v of s.visitors || []) {
    entries.push({ dom: "v:" + v.id, key: v.id, emoji: VISITOR_EMOJI[v.kind] || "🎒", label: v.name || v.kind, pos: v.pos });
  }
  for (const r of s.raiders || []) {
    entries.push({ dom: "r:" + r.id, key: r.id, emoji: "🥷", label: "", pos: r.pos });
  }
  const seen = new Set();
  for (const e of entries) {
    seen.add(e.dom);
    let rec = creatures.get(e.dom);
    if (!rec) {
      const el = document.createElement("div");
      el.className = "creature";
      const fig = document.createElement("span");
      fig.className = "fig";
      const name = document.createElement("span");
      name.className = "name";
      el.appendChild(fig);
      el.appendChild(name);
      spritesEl.appendChild(el);
      rec = { dom: e.dom, key: e.key, el, fig, name, x: 0, y: 0, phase: Math.random() * 7 };
      creatures.set(e.dom, rec);
    }
    rec.fig.textContent = e.emoji;
    rec.name.textContent = e.label;
    rec.name.style.display = e.label ? "block" : "none";
    const p = iso(e.pos[0], e.pos[1]);
    rec.x = p.x;
    rec.y = p.y;
    rec.el.classList.remove("leaving");
  }
  for (const [dom, rec] of creatures) {
    if (seen.has(dom)) continue;
    rec.el.classList.add("leaving");
    setTimeout(() => rec.el.remove(), 650);
    creatures.delete(dom);
  }
}

// ---- bubbles (comic speech + thought) ----
function addBubbles(s) {
  for (const [, b] of bubbles) b.el.remove();
  bubbles.clear();
  for (const p of s.pawns) {
    const rec = pawns.get(p.id);
    if (!rec) continue;
    if (p.quote) addBubble(p.id + ".speech", "speech", p.quote, rec);
    if (p.inner_monologue) addBubble(p.id + ".thought", "thought", p.inner_monologue, rec);
  }
}

function addBubble(key, kind, text, rec) {
  const el = document.createElement("div");
  el.className = "bubble " + kind;
  el.textContent = text;
  bubbleLayer.appendChild(el);
  bubbles.set(key, { el, rec, kind });
  el.addEventListener("animationend", () => el.remove());
}

// ---- per-tick emotes + world ticker ----
function findActorSpot(id) {
  const p = pawns.get(id);
  if (p) return { x: p.x, y: p.y - 34 };
  for (const c of creatures.values()) {
    if (c.key === id) return { x: c.x, y: c.y - 26 };
  }
  return null;
}

function addEmotes(s) {
  const tickEvents = (s.events || []).filter((e) => e.tick === s.tick - 1);
  let worldDesc = null;
  for (const ev of tickEvents) {
    if (ev.type === "world" && ev.description) worldDesc = ev.description;
    const emoji = EMOTE_MAP[ev.type];
    if (!emoji) continue;
    const spot = findActorSpot(ev.actor || ev.target);
    if (spot) spawnEmote(emoji, spot.x, spot.y);
  }
  if (worldDesc) {
    tickerEl.textContent = worldDesc;
    tickerEl.classList.remove("hidden");
    tickerEl.style.animation = "none";
    void tickerEl.offsetWidth; // restart the animation
    tickerEl.style.animation = "";
  } else {
    tickerEl.classList.add("hidden");
  }
}

function updateCaption(s) {
  const phase = s.day ? "Day" : "Night";
  titleEl.textContent =
    `${s.colony} — ${s.season} · ${s.weather} · ${phase} · tick ${s.tick}`;
}

// ---- snapshot apply ----
function applySnapshot(s) {
  snap = s;
  snapTime = performance.now();
  syncPawns(s);
  syncCreatures(s);
  addBubbles(s);
  addEmotes(s);
  updateCaption(s);
}

// ---- animation loop ----
function frame(now) {
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
        let bobAmp = 2.5, bobFreq = 520, ringRot = 0;
        switch (rec.action) {
          case "Chop": bobAmp = 4; bobFreq = 230; ringRot = 0.18; break;
          case "Forage": bobAmp = 4; bobFreq = 300; ringRot = 0.1; break;
          case "Build": bobAmp = 3; bobFreq = 340; break;
          case "Scout": bobAmp = 3; bobFreq = 700; ringRot = 0.07; break;
          case "Rest": bobAmp = 1.5; bobFreq = 900; break;
          case "Attack": bobAmp = 4; bobFreq = 180; ringRot = 0.22; break;
        }
        const bob = Math.abs(Math.sin(now / bobFreq + rec.phase)) * bobAmp;
        y -= bob;
        rec.ring.style.transform = ringRot
          ? `rotate(${Math.sin(now / bobFreq + rec.phase) * ringRot}rad)`
          : "";
        if (elapsed > BUBBLE_DELAY + BUBBLE_LIFE && now > rec.nextEmote) {
          const emo = ACTION_EMOTE[rec.action];
          if (emo) spawnEmote(emo, x, y - 42);
          rec.nextEmote = now + 4000 + Math.random() * 4000;
        }
      }
      rec.el.style.left = x + "px";
      rec.el.style.top = y + "px";
    }
    for (const rec of creatures.values()) {
      const bob = Math.abs(Math.sin(now / 700 + rec.phase)) * 3;
      rec.el.style.left = rec.x + "px";
      rec.el.style.top = rec.y - bob + "px";
    }
    for (const [, b] of bubbles) {
      const lift = b.kind === "thought" ? 112 : 86;
      b.el.style.left = b.rec.x + "px";
      b.el.style.top = b.rec.y - lift + "px";
    }
    drawIsland(now);
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
