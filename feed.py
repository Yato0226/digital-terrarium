"""Phase 6 (Step 1): ultra-lightweight world-state broadcast, zero deps.

A hand-rolled RFC 6455 WebSocket server plus a static-file HTTP server, both
on asyncio, keeping the repo's zero-framework ethos (no `websockets`, no
aiohttp). After each deterministic tick completes, `core.run_tick` builds a
clean JSON snapshot via `build_snapshot()` and calls `broadcast()`; browsers
open at ``web/`` subscribe to it and animate the world as a live diorama.

Memory footprint is deliberately tiny: one asyncio task per connected client
plus a small per-client queue (a single serialized frame per tick), so it idles
quietly on the 2 GB LXC container.

Wire format (server -> client): a single JSON object with ``type == "world"``
carrying the whole snapshot. Clients may send ``{"type": "snapshot"}`` to ask
for an immediate copy (e.g. after a god edit between ticks).
"""

import asyncio
import base64
import hashlib
import json
from pathlib import Path

import config
import engine
import state

WEB_DIR = Path(__file__).resolve().parent / "web"

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

_server = None
_port = None
_server_loop = None
clients = set()
_prev_positions = {}


class _Client:
    """One connected browser: its socket plus the frames still queued to send."""

    __slots__ = ("writer", "queue", "task")

    def __init__(self, writer):
        self.writer = writer
        self.queue = asyncio.Queue(maxsize=16)
        self.task = None


def reset():
    """Drop every client and the movement history (tests, server restarts)."""
    for c in list(clients):
        try:
            c.writer.close()
        except OSError:
            pass
    clients.clear()
    _prev_positions.clear()


# --------------------------------------------------------------------------
# RFC 6455 frame helpers (pure, unit-testable).
# --------------------------------------------------------------------------

def _frame_encode(payload, opcode=0x1):
    """Encode a single WebSocket frame (server->client: never masked)."""
    n = len(payload)
    if n < 126:
        head = bytes([0x80 | opcode, n])
    elif n < 65536:
        head = bytes([0x80 | opcode, 126]) + n.to_bytes(2, "big")
    else:
        head = bytes([0x80 | opcode, 127]) + n.to_bytes(8, "big")
    return head + payload


async def _recv_frame(reader):
    """Read one WebSocket frame (client->server: always masked). Returns (opcode, payload)."""
    b0, b1 = await reader.readexactly(2)
    opcode = b0 & 0x0F
    length = b1 & 0x7F
    masked = bool(b1 & 0x80)
    if length == 126:
        length = int.from_bytes(await reader.readexactly(2), "big")
    elif length == 127:
        length = int.from_bytes(await reader.readexactly(8), "big")
    mask = await reader.readexactly(4) if masked else None
    payload = await reader.readexactly(length)
    if mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload


# --------------------------------------------------------------------------
# HTTP request parsing + static serving.
# --------------------------------------------------------------------------

async def _read_http_request(reader):
    """Read the request head byte-by-byte so nothing past CRLFCRLF is consumed."""
    raw = bytearray()
    while not raw.endswith(b"\r\n\r\n"):
        raw += await reader.readexactly(1)
        if len(raw) > 16 * 1024:
            raise ValueError("request head too large")
    lines = raw.decode("latin-1").split("\r\n")
    method, path, _version = lines[0].split(" ", 2)
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return {"method": method, "path": path, "headers": headers}


_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


def _write_http(writer, status, ctype, body):
    reason = {200: "OK", 403: "Forbidden", 404: "Not Found", 500: "Server Error"}.get(status, "OK")
    writer.write(
        f"HTTP/1.1 {status} {reason}\r\n"
        f"Content-Type: {ctype}\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Cache-Control: no-cache\r\n"
        f"Connection: close\r\n\r\n".encode("ascii")
        + body
    )


async def _serve_http(writer, request):
    """Plain GET over HTTP: the static client, or /snapshot.json for debugging."""
    path = request["path"].split("?", 1)[0]
    if path == "/snapshot.json":
        body = json.dumps(build_snapshot(), ensure_ascii=False).encode("utf-8")
        _write_http(writer, 200, "application/json; charset=utf-8", body)
        await writer.drain()
        return
    rel = (path.lstrip("/") or "index.html")
    target = (WEB_DIR / rel).resolve()
    if not str(target).startswith(str(WEB_DIR.resolve())):
        _write_http(writer, 403, "text/plain; charset=utf-8", b"Forbidden")
        await writer.drain()
        return
    if not target.is_file():
        _write_http(writer, 404, "text/plain; charset=utf-8", b"Not found")
        await writer.drain()
        return
    _write_http(
        writer,
        200,
        _CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream"),
        target.read_bytes(),
    )
    await writer.drain()


# --------------------------------------------------------------------------
# WebSocket session + fan-out.
# --------------------------------------------------------------------------

def _accept_key(key):
    digest = hashlib.sha1((key + WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _world_frame(snapshot):
    payload = json.dumps({"type": "world", **snapshot}, ensure_ascii=False).encode("utf-8")
    return _frame_encode(payload)


async def _writer_loop(client):
    try:
        while True:
            frame = await client.queue.get()
            client.writer.write(frame)
            await client.writer.drain()
    except (ConnectionError, OSError, asyncio.CancelledError):
        pass
    finally:
        clients.discard(client)
        try:
            client.writer.close()
        except OSError:
            pass


async def _ws_session(reader, writer, request):
    """Run the RFC 6455 handshake, then the reader (control frames + requests)."""
    key = request["headers"].get("sec-websocket-key")
    if not key:
        writer.close()
        return
    writer.write(
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {_accept_key(key)}\r\n\r\n".encode("ascii")
    )
    await writer.drain()
    client = _Client(writer)
    clients.add(client)
    client.task = asyncio.create_task(_writer_loop(client))
    try:
        # Push the current world immediately so the client isn't blank on open.
        client.queue.put_nowait(_world_frame(build_snapshot()))
        while True:
            opcode, payload = await _recv_frame(reader)
            if opcode == 0x8:  # close
                writer.write(_frame_encode(payload, opcode=0x8))
                await writer.drain()
                break
            elif opcode == 0x9:  # ping -> pong
                writer.write(_frame_encode(payload, opcode=0xA))
                await writer.drain()
            elif opcode == 0x1:  # text: client messages
                try:
                    msg = json.loads(payload.decode("utf-8"))
                except ValueError:
                    continue
                if isinstance(msg, dict) and msg.get("type") == "snapshot":
                    client.queue.put_nowait(_world_frame(build_snapshot()))
    except (ConnectionError, OSError, asyncio.IncompleteReadError):
        pass
    finally:
        clients.discard(client)
        if client.task is not None:
            client.task.cancel()
        try:
            writer.close()
        except OSError:
            pass


async def _handle_connection(reader, writer):
    try:
        request = await _read_http_request(reader)
    except (ValueError, asyncio.IncompleteReadError):
        writer.close()
        return
    try:
        if request["headers"].get("upgrade", "").lower() == "websocket":
            await _ws_session(reader, writer, request)
        else:
            await _serve_http(writer, request)
    finally:
        try:
            writer.close()
        except OSError:
            pass


# --------------------------------------------------------------------------
# Snapshot building + broadcast.
# --------------------------------------------------------------------------

def build_snapshot(decisions=None):
    """A clean, client-safe JSON snapshot of the world.

    ``decisions`` optionally maps pawn id -> {action, flavor, direction, quote,
    inner_monologue} for the tick that just completed (used for bubbles and
    looping animations). Positions are tracked across calls so the client can
    walk pawns from their previous tile.
    """
    ws = state.world_state
    biome = ws["biome"]
    now = {}
    pawns = []
    decisions = decisions or {}
    for pid, p in ws["pawns"].items():
        pos = list(p["pos"])
        now[pid] = pos
        d = decisions.get(pid, {})
        pawns.append(
            {
                "id": pid,
                "name": p["name"],
                "job": p.get("job"),
                "title": p.get("title"),
                "sex": p.get("sex"),
                "status": p.get("status"),
                "pos": pos,
                "prev_pos": list(_prev_positions.get(pid, pos)),
                "vitals": {
                    k: p["vitals"][k]
                    for k in ("hp", "energy", "hunger", "warmth", "morale")
                },
                "inventory": {
                    k: p["inventory"][k] for k in ("wood", "food", "stone", "fiber")
                },
                "action": d.get("action"),
                "flavor": d.get("flavor"),
                "direction": d.get("direction"),
                "quote": d.get("quote"),
                "inner_monologue": d.get("inner_monologue"),
                "mental_break": p.get("mental_break"),
                "traits": p.get("traits", []),
                "pregnant": p.get("pregnant_ticks", 0) > 0,
                "child": p.get("child_ticks", 0) > 0,
                "elder": engine.is_elder(p),
            }
        )
    _prev_positions.clear()
    _prev_positions.update(now)
    return {
        "tick": ws["tick"],
        "season": biome["season"],
        "weather": biome["weather"],
        "day": biome.get("day", 0),
        "extinct": ws.get("extinct", False),
        "colony": ws.get("colony", {}).get("name", "The Settlers"),
        "biome": {
            k: biome.get(k)
            for k in ("campfire", "shelter", "wood_stock", "food_stock", "granary", "palisade")
        },
        "grid": [row[:] for row in ws["grid"]],
        "pawns": pawns,
        "wildlife": [
            {
                "id": w["id"],
                "species": w["species"],
                "name": w.get("name"),
                "pos": list(w["pos"]),
                "state": w.get("state"),
                "emoji": engine.WILDLIFE.get(w["species"], {}).get("emoji", "🐾"),
            }
            for w in ws.get("wildlife", [])
        ],
        "visitors": [
            {
                "id": v["id"],
                "kind": v["kind"],
                "name": v.get("name"),
                "pos": list(v["pos"]),
                "state": v.get("state"),
            }
            for v in ws.get("visitors", [])
        ],
        "raiders": [
            {"id": r["id"], "pos": list(r["pos"]), "state": r.get("state")}
            for r in ws.get("raiders", [])
        ],
        "events": [dict(ev) for ev in ws["history"]],
    }


async def broadcast(snapshot=None):
    """Serialize once and queue a frame to every connected client (non-blocking)."""
    if not clients:
        return
    if snapshot is None:
        snapshot = build_snapshot()
    frame = _world_frame(snapshot)
    for client in list(clients):
        try:
            client.queue.put_nowait(frame)
        except asyncio.QueueFull:
            # A client too slow to keep up is dropped; it reconnects on its own.
            clients.discard(client)
            if client.task is not None:
                client.task.cancel()


async def start():
    """Bind the HTTP/WebSocket server. Returns the listening port, or None if disabled."""
    global _server, _port, _server_loop
    if _server is not None:
        return _port
    if not config.FEED_ENABLED:
        return None
    _server = await asyncio.start_server(_handle_connection, config.FEED_HOST, config.FEED_PORT)
    _port = _server.sockets[0].getsockname()[1]
    _server_loop = asyncio.get_running_loop()
    host = "localhost" if config.FEED_HOST in ("0.0.0.0", "::") else config.FEED_HOST
    print(f"📡 World feed live at http://{host}:{_port}/ (ws://{host}:{_port}/)")
    return _port


async def stop():
    """Close the server and every connection (shutdown path).

    Safe to call from a different event loop (tests that fail mid-connection):
    the old loop's teardown already closed its sockets, so we only null the
    globals then, never awaiting a server owned by a dead loop.
    """
    global _server, _port, _server_loop
    reset()
    srv, _server = _server, None
    _port = None
    loop, _server_loop = _server_loop, None
    if srv is None:
        return
    if loop is not None and loop is asyncio.get_running_loop():
        try:
            srv.close()
            await srv.wait_closed()
        except Exception:
            pass
