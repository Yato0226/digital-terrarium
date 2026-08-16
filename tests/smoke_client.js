// Regression smoke test for the live web client.
//
// Boots the real web/app.js + web/sprites.js against a stubbed DOM, feeds a
// series of realistic snapshots (stacked pawns, night/winter/snow, wildlife,
// visitors, raiders, deaths, resets), runs the animation loop, and asserts on
// what the client must have produced. Any runtime error (e.g. a querySelector
// that no longer matches a created element) aborts with a non-zero exit.
//
// Run: node tests/smoke_client.js   (cwd = repo root, or anywhere)
// Wrapped by tests/test_web_client.py for `python -m pytest tests -q`.
const fs = require("fs");
const path = require("path");

// ---------- canvas 2d context stub ----------
function grad() { return { addColorStop: () => {} }; }
const ctxStub = () => ({
  arc: () => {}, beginPath: () => {}, clearRect: () => {}, clip: () => {},
  closePath: () => {}, createLinearGradient: grad, createRadialGradient: grad,
  drawImage: () => {}, fill: () => {}, fillRect: () => {},
  lineTo: () => {}, moveTo: () => {}, quadraticCurveTo: () => {},
  restore: () => {}, save: () => {}, scale: () => {}, stroke: () => {},
  translate: () => {},
  createImageData: (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) }),
  putImageData: () => {},
  fillStyle: "", strokeStyle: "", lineWidth: 1, lineCap: "", globalAlpha: 1,
  globalCompositeOperation: "source-over", imageSmoothingEnabled: false,
});

function makeClassList() {
  const set = new Set();
  return {
    add: (...cs) => cs.forEach((c) => set.add(c)),
    remove: (...cs) => cs.forEach((c) => set.delete(c)),
    toggle: (c, force) => {
      if (force === undefined) {
        if (set.has(c)) { set.delete(c); return false; }
        set.add(c); return true;
      }
      if (force) set.add(c); else set.delete(c);
      return force;
    },
    contains: (c) => set.has(c),
    has: (c) => set.has(c),
    clear: () => set.clear(),
  };
}

// ---------- element + canvas stubs ----------
function attachClassList(obj) {
  const cl = makeClassList();
  Object.defineProperty(obj, "classList", { get: () => cl, set: () => {} });
  Object.defineProperty(obj, "className", {
    get: () => [...cl].join(" "),
    set(v) {
      cl.clear();
      for (const c of String(v).split(/\s+/).filter(Boolean)) cl.add(c);
    },
  });
  return cl;
}

function makeEl(tag) {
  const el = {
    tag,
    style: {},
    dataset: {},
    children: [],
    _text: "",
    _html: "",
    title: "",
    id: "",
    _query: new Map(),
    addEventListener: () => {},
    removeEventListener: () => {},
    appendChild(c) { el.children.push(c); return c; },
    append(...cs) { for (const c of cs) el.appendChild(c); },
    prepend(c) { el.children.unshift(c); },
    remove() {
      const parent = el._parent;
      if (parent) parent.children = parent.children.filter((c) => c !== el);
    },
    querySelector(sel) {
      if (el._query.has(sel)) return el._query.get(sel);
      if (sel.startsWith(".")) {
        const cls = sel.slice(1);
        const stack = [...el.children];
        while (stack.length) {
          const c = stack.pop();
          if (c.classList && c.classList.has(cls)) return c;
          if (c.children) stack.push(...c.children);
        }
        return null;
      }
      return null;
    },
    querySelectorAll() { return []; },
    get textContent() { return el._text; },
    set textContent(v) {
      el._text = String(v);
      el.children.length = 0; // real DOM replaces children on textContent set
    },
    get innerHTML() { return el._html; },
    set innerHTML(v) { el._html = String(v); },
    get lastChild() { return el.children[el.children.length - 1] || null; },
  };
  el._parent = null;
  const origAppend = el.appendChild;
  el.appendChild = (c) => { c._parent = el; return origAppend(c); };
  attachClassList(el);
  return el;
}

function makeCanvas() {
  const cv = makeEl("canvas");
  cv.width = 0;
  cv.height = 0;
  cv.getContext = ctxStub;
  return cv;
}

// ---------- document stub ----------
const byId = {};
function seeded(id, make) { return (byId[id] ||= make ? make() : makeEl("div")); }
global.document = {
  getElementById(id) {
    if (byId[id]) return byId[id];
    return (byId[id] = id === "island" ? makeCanvas() : makeEl("div"));
  },
  createElement(tag) {
    return tag === "canvas" ? makeCanvas() : makeEl(tag);
  },
};

// Seed the HUD/panel elements.
seeded("stage");
seeded("hud");
seeded("island", () => makeCanvas());
seeded("sprites");
seeded("bubbles");
seeded("emotes");
seeded("title");
seeded("conn");
const logEl = seeded("log");
const chatEl = seeded("chat");
for (const id of ["gCampfire", "gShelter"]) {
  const g = seeded(id);
  const track = makeEl("span");
  const fill = makeEl("span");
  fill.className = "fill";
  track.appendChild(fill);
  g.appendChild(track);
  g._query.set(".fill", fill);
}
for (const id of ["sWood", "sFood", "sStone", "sFiber"]) seeded(id);
seeded("loreBtn");
seeded("dossier"); seeded("dossierBody"); seeded("dossierClose");
seeded("lore"); seeded("loreBody"); seeded("loreClose");
seeded("rosterBtn"); seeded("roster"); seeded("rosterBody"); seeded("rosterClose");

global.window = global;
global.location = { protocol: "http:", host: "localhost:8900" };
global.addEventListener = () => {};
global.innerWidth = 1280;
global.innerHeight = 800;
let wsInst = null;
class WS {
  constructor(url) { this.url = url; wsInst = this; }
}
global.WebSocket = WS;
let rafCb = null;
global.requestAnimationFrame = (cb) => { rafCb = cb; return 1; };

// ---------- load the real client ----------
const root = path.join(__dirname, "..");
const clientSrc =
  fs.readFileSync(path.join(root, "web", "sprites.js"), "utf8") +
  "\n;\n" +
  fs.readFileSync(path.join(root, "web", "app.js"), "utf8");
eval(clientSrc);

if (!rafCb) { console.log("FAIL: requestAnimationFrame never registered"); process.exit(1); }

// ---------- realistic snapshots ----------
const grid = [
  "🌲🌲🌊🌲🌲".split(""),
  "🌲🌲🌊🌲🌲".split(""),
  "🌊🌊🫐🌲🌲".split(""),
  "🌲🌲🌲💀🌲".split(""),
  "🌲🪨🌲🌲🌲".split(""),
];
function pawn(id, name, sex, pos, opts) {
  return {
    id, name, sex, pos, prev_pos: [...pos], title: "", job: "colonist",
    elder: 0, child: 0, pregnant: 0, mental_break: null,
    status: "active", traits: [], partners: [],
    mother_id: null, father_id: null, partner_id: null,
    vitals: { hp: 80, energy: 60, hunger: 40, warmth: 70, morale: 50 },
    inventory: { wood: 2, food: 3, stone: 0, fiber: 1 },
    gear: { main_hand: null, body: null },
    skills: { woodcutting: 3, scouting: 1, combat: 2, farming: 1, crafting: 1, social: 1 },
    relationships: {}, counters: {}, goal: null,
    action: "Rest", flavor: "", direction: "N", quote: "", inner_monologue: "",
    ...opts,
  };
}
const snap1 = {
  type: "world",
  tick: 41, season: "Summer", weather: "Clear", day: 1, extinct: false,
  colony: "Fernhold", biome: { campfire: 80, shelter: 50 },
  resources: { wood: 12, food: 8, stone: 3, fiber: 2 },
  grid,
  pawns: [
    pawn("p1", "Fern", "F", [2, 2], { title: "the Builder", action: "Build", quote: "Nice beams today", inner_monologue: "The roof needs work.", goal: { kind: "gather wood", needed: 10, progress: 4, text: "Gather 10 wood" } }),
    pawn("p2", "Bram", "M", [2, 2], { action: "Chop" }),
    pawn("p3", "Ivy", "F", [1, 3], { action: "Move", direction: "W", prev_pos: [1, 4] }),
    pawn("p4", "Oak", "M", [2, 2], { action: "Rest", status: "incapacitated" }),
  ],
  wildlife: [
    { id: "wl1", species: "Deer", name: null, pos: [0, 0], state: "idle" },
    { id: "wl2", species: "Wolf", name: "The Grey Terror", pos: [4, 4], state: "stalking" },
    { id: "wl3", species: "Rabbit", name: null, pos: [3, 0], state: "fleeing" },
  ],
  visitors: [{ id: "visit_1", kind: "Merchant", name: "Tilly", pos: [4, 0], state: "visiting" }],
  raiders: [{ id: "scavenger_1", pos: [0, 4], state: "marching" }],
  events: [
    { tick: 40, type: "chop", actor: "p2", target: null, description: "Bram fells a tree (+2 wood).", data: {} },
    { tick: 40, type: "world", actor: null, target: null, description: "The forest murmurs of old things.", data: {} },
  ],
  lore: { graveyard: [], monument: { wood: 3, stone: 2, done: false, inscription: "", runes: "" }, patches: [], chronicle: [] },
};

function send(s) {
  if (wsInst && typeof wsInst.onmessage === "function") wsInst.onmessage({ data: JSON.stringify(s) });
  else throw new Error("WebSocket never connected; client onmessage not wired");
}
function frames(n, now) {
  for (let i = 0; i < n; i++) { rafCb(now); now += 16.7; }
  return now;
}

// ---------- run the scenario ----------
let err = null;
try {
  let now = 100;

  send(snap1);
  const title1 = byId.title._text;
  if (!title1.includes("Fernhold")) throw new Error(`HUD title not set: "${title1}"`);
  if (byId.rosterBody.children.length !== 4) throw new Error(`roster cards expected 4, got ${byId.rosterBody.children.length}`);
  if (logEl.children.length !== 2) throw new Error(`log rows expected 2, got ${logEl.children.length}`);
  if (byId.sprites.children.length !== 9) throw new Error(`pawn+creature els expected 9, got ${byId.sprites.children.length}`);
  now = frames(20, now);

  // The roster bars must actually get widths (regression for the .r-hp/.r-en
  // class mismatch that nuked applySnapshot on every tick).
  const hpW = byId.rosterBody.querySelector(".r-hp") && byId.rosterBody.querySelector(".r-hp").style.width;
  const enW = byId.rosterBody.querySelector(".r-en") && byId.rosterBody.querySelector(".r-en").style.width;
  if (hpW !== "80%") throw new Error(`roster hp bar width expected 80%, got ${hpW}`);
  if (enW !== "60%") throw new Error(`roster energy bar width expected 60%, got ${enW}`);

  // Corner chat box: Fern's quote + thought become rows (newest on top), and
  // the panel is visible.
  if (chatEl.children.length !== 2) throw new Error(`chat rows expected 2, got ${chatEl.children.length}`);
  const chatQuote = chatEl.children[1] && chatEl.children[1].children[1] && chatEl.children[1].children[1]._text;
  if (chatQuote !== "Nice beams today") throw new Error(`chat quote row missing, got "${chatQuote}"`);
  if (chatEl.classList.contains("hidden")) throw new Error("chat should be visible while it has rows");

  // Second snapshot: night + winter + snow, pawns walking, three stacked on a
  // tile, a new child pawn, a death, farm/weather events.
  const snap2 = JSON.parse(JSON.stringify(snap1));
  snap2.tick = 42;
  snap2.season = "Winter";
  snap2.weather = "Snow";
  snap2.day = 0;
  snap2.pawns[0].prev_pos = [2, 1];
  snap2.pawns[0].pos = [2, 2];
  snap2.pawns[1].pos = [2, 2];
  snap2.pawns[1].action = "Rest";
  snap2.pawns[2].pos = [2, 2];
  snap2.pawns.push(pawn("p5", "Soot", "M", [2, 2], { child: 1, action: "Interact", flavor: "play" }));
  snap2.pawns[3].status = "dead";
  snap2.wildlife = [];
  snap2.events = [
    { tick: 41, type: "mate", actor: "p1", target: "p2", description: "Fern and Bram court by the fire.", data: {} },
    { tick: 41, type: "death", actor: "p4", target: null, description: "Oak passes into the winter dark.", data: {} },
    { tick: 41, type: "farm_ready", actor: null, target: null, description: "A plot of berries ripens.", data: {} },
  ];
  send(snap2);
  if (byId.rosterBody.children.length !== 5) throw new Error(`roster cards expected 5 after birth, got ${byId.rosterBody.children.length}`);
  if (logEl.children.length !== 5) throw new Error(`log rows expected 5, got ${logEl.children.length}`);
  if (chatEl.children.length !== 4) throw new Error(`chat rows expected 4 after second tick, got ${chatEl.children.length}`);
  now = frames(60, now);

  // Third snapshot: world reset (tick drops) — log and roster must reset.
  const snap3 = JSON.parse(JSON.stringify(snap2));
  snap3.tick = 1;
  snap3.season = "Spring";
  snap3.weather = "Clear";
  snap3.day = 1;
  snap3.pawns = snap3.pawns.slice(0, 2);
  snap3.events = [{ tick: 0, type: "birth", actor: "p1", target: "p5", description: "A child is born.", data: {} }];
  send(snap3);
  if (byId.rosterBody.children.length !== 2) throw new Error(`roster cards expected 2 after reset, got ${byId.rosterBody.children.length}`);
  if (logEl.children.length !== 0) throw new Error(`log rows expected 0 after reset, got ${logEl.children.length}`);
  // Reset clears the chat history but the fresh world's dialogue still lands.
  if (chatEl.children.length !== 2) throw new Error(`chat rows expected 2 after reset, got ${chatEl.children.length}`);
  if (chatEl.classList.contains("hidden")) throw new Error("chat should be visible after reset with fresh dialogue");
  now = frames(10, now);

  console.log("OK: client booted; 3 snapshots + 90 frames; HUD/roster/log/slots all correct");
  console.log(`OK: roster bar widths hp=${hpW} en=${enW}; roster cards=${byId.rosterBody.children.length}; log rows=${logEl.children.length}`);
  process.exit(0);
} catch (e) {
  err = e;
  console.log("FAIL:", e && e.stack ? e.stack.split("\n").slice(0, 6).join("\n") : e);
  process.exit(1);
}
