"""Stage 26 tests: Phase 6 Step 1 — the zero-dependency world feed.

Covers the RFC 6455 frame codec, the client snapshot shape, and the live
HTTP/WebSocket server end-to-end over localhost sockets (fully offline).
"""

import asyncio
import json

import pytest

import config
import events
import feed
import state

pytestmark = pytest.mark.usefixtures("fresh_world")


@pytest.fixture(autouse=True)
def fresh_world(monkeypatch):
    state.reset_world()
    events.LOGGING = False
    feed.reset()
    monkeypatch.setattr(config, "FEED_ENABLED", True)
    monkeypatch.setattr(config, "FEED_PORT", 0)
    yield
    feed.reset()
    try:
        _run(feed.stop())
    except Exception:
        pass
    events.LOGGING = True


def _run(coro):
    return asyncio.run(coro)


def client_frame(payload, opcode=0x1):
    """A client->server frame (RFC 6455 requires masking)."""
    mask = b"\x00\x01\x02\x03"
    n = len(payload)
    if n < 126:
        head = bytes([opcode, 0x80 | n])
    elif n < 65536:
        head = bytes([opcode, 0x80 | 126]) + n.to_bytes(2, "big")
    else:
        head = bytes([opcode, 0x80 | 127]) + n.to_bytes(8, "big")
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return head + mask + masked


async def _read_http_head(reader):
    raw = b""
    while not raw.endswith(b"\r\n\r\n"):
        raw += await reader.readexactly(1)
    return raw.decode("latin-1")


async def _open_ws(port, path="/"):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    key = "dGhlIHNhbXBsZSBub25jZQ=="
    writer.write(
        f"GET {path} HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n".encode("ascii")
    )
    await writer.drain()
    head = await _read_http_head(reader)
    return reader, writer, head


# ---- Frame codec ----


def test_frame_encode_small():
    assert feed._frame_encode(b"hi") == b"\x81\x02hi"


def test_frame_encode_medium():
    payload = b"x" * 300
    assert feed._frame_encode(payload)[:4] == b"\x81\x7e\x01\x2c"


def test_frame_encode_large():
    payload = b"y" * 70000
    assert feed._frame_encode(payload)[:10] == b"\x81\x7f" + (70000).to_bytes(8, "big")


async def _decode(payload_bytes):
    reader = asyncio.StreamReader()
    reader.feed_data(payload_bytes)
    reader.feed_eof()
    opcode, payload = await feed._recv_frame(reader)
    return opcode, payload


def test_frame_roundtrip_masked():
    msg = json.dumps({"type": "world", "tick": 7}).encode()
    opcode, payload = _run(_decode(client_frame(msg)))
    assert opcode == 0x1
    assert json.loads(payload) == {"type": "world", "tick": 7}


def test_frame_decode_unmasked_server_push():
    opcode, payload = _run(_decode(feed._frame_encode(b"hello")))
    assert opcode == 0x1
    assert payload == b"hello"


# ---- Snapshot builder ----


def test_snapshot_shape():
    snap = feed.build_snapshot()
    for key in (
        "tick", "season", "weather", "day", "extinct", "colony", "biome",
        "grid", "pawns", "wildlife", "visitors", "raiders", "events",
    ):
        assert key in snap
    assert snap["grid"] == state.DEFAULT_GRID
    assert snap["tick"] == state.world_state["tick"]
    p = snap["pawns"][0]
    for key in ("id", "name", "pos", "prev_pos", "vitals", "inventory", "action",
                "flavor", "quote", "inner_monologue", "traits"):
        assert key in p
    assert p["prev_pos"] == p["pos"]  # nothing moved yet


def test_snapshot_tracks_movement():
    first = feed.build_snapshot()
    pawn_1 = state.world_state["pawns"]["pawn_1"]
    pawn_1["pos"] = [0, 0]
    second = feed.build_snapshot()
    by_id = {p["id"]: p for p in second["pawns"]}
    assert by_id["pawn_1"]["pos"] == [0, 0]
    assert by_id["pawn_1"]["prev_pos"] == first["pawns"][0]["pos"]


def test_snapshot_includes_decisions():
    snap = feed.build_snapshot(
        {"pawn_1": {"action": "Chop", "quote": "timber!", "inner_monologue": "more wood"}}
    )
    p = next(x for x in snap["pawns"] if x["id"] == "pawn_1")
    assert p["action"] == "Chop"
    assert p["quote"] == "timber!"
    assert p["inner_monologue"] == "more wood"


def test_snapshot_events_carried():
    events.add_event("feast", description="A feast is held.")
    snap = feed.build_snapshot()
    assert any(e["type"] == "feast" for e in snap["events"])


def test_snapshot_wildlife_and_entities():
    state.world_state["wildlife"].append(
        {"id": "w1", "species": "Deer", "pos": [1, 1], "state": "active"}
    )
    snap = feed.build_snapshot()
    assert snap["wildlife"][0]["species"] == "Deer"
    assert snap["wildlife"][0]["emoji"] == "🦌"


def test_broadcast_no_clients():
    _run(feed.broadcast(feed.build_snapshot()))  # must not raise


def test_forget_positions_disables_walks():
    feed.build_snapshot()
    pawn_1 = state.world_state["pawns"]["pawn_1"]
    pawn_1["pos"] = [0, 0]
    assert feed.build_snapshot()["pawns"][0]["prev_pos"] != [0, 0]
    feed.forget_positions()
    snap = feed.build_snapshot()
    assert snap["pawns"][0]["prev_pos"] == snap["pawns"][0]["pos"]


# ---- Live HTTP server ----


async def _http_get(port, path):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    head = await _read_http_head(reader)
    body = await reader.read()
    writer.close()
    return head, body


def test_http_serves_index():
    async def go():
        port = await feed.start()
        head, body = await _http_get(port, "/")
        assert "200 OK" in head.split("\r\n")[0]
        assert b"<!DOCTYPE html>" in body
        await feed.stop()

    _run(go())


def test_http_snapshot_json():
    async def go():
        port = await feed.start()
        head, body = await _http_get(port, "/snapshot.json")
        assert "200 OK" in head.split("\r\n")[0]
        snap = json.loads(body)
        assert snap["tick"] == state.world_state["tick"]
        assert snap["season"] in ("Spring", "Summer", "Autumn", "Winter")
        await feed.stop()

    _run(go())


def test_http_404():
    async def go():
        port = await feed.start()
        head, _body = await _http_get(port, "/nope.js")
        assert "404 Not Found" in head.split("\r\n")[0]
        await feed.stop()

    _run(go())


def test_http_path_traversal_blocked():
    async def go():
        port = await feed.start()
        head, _body = await _http_get(port, "/../config.py")
        assert "403 Forbidden" in head.split("\r\n")[0]
        await feed.stop()

    _run(go())


# ---- Live WebSocket server ----


async def _ws_exchange(port, send=None, expect_snapshot=True):
    reader, writer, head = await _open_ws(port)
    assert "101 Switching Protocols" in head.split("\r\n")[0]
    assert "Sec-WebSocket-Accept:" in head
    frames = []
    if expect_snapshot:
        opcode, payload = await feed._recv_frame(reader)
        frames.append(json.loads(payload))
    if send is not None:
        writer.write(client_frame(json.dumps(send).encode()))
        await writer.drain()
        opcode, payload = await feed._recv_frame(reader)
        frames.append(json.loads(payload))
    writer.close()
    return frames


def test_websocket_handshake_pushes_snapshot():
    async def go():
        port = await feed.start()
        frames = await _ws_exchange(port)
        assert frames[0]["type"] == "world"
        assert frames[0]["tick"] == state.world_state["tick"]
        assert len(frames[0]["pawns"]) == len(state.world_state["pawns"])
        await feed.stop()

    _run(go())


def test_websocket_request_snapshot():
    async def go():
        port = await feed.start()
        frames = await _ws_exchange(port, send={"type": "snapshot"})
        assert frames[0]["type"] == "world"
        assert frames[1]["type"] == "world"
        assert frames[1]["tick"] == state.world_state["tick"]
        await feed.stop()

    _run(go())


def test_websocket_ping_pong():
    async def go():
        port = await feed.start()
        reader, writer, head = await _open_ws(port)
        await feed._recv_frame(reader)  # initial snapshot
        writer.write(client_frame(b"", opcode=0x9))  # ping
        await writer.drain()
        opcode, payload = await feed._recv_frame(reader)
        assert opcode == 0xA  # pong
        writer.close()
        await feed.stop()

    _run(go())


def test_broadcast_fans_out_to_all():
    async def go():
        port = await feed.start()
        reader_a, writer_a, _ = await _open_ws(port)
        reader_b, writer_b, _ = await _open_ws(port)
        await feed._recv_frame(reader_a)
        await feed._recv_frame(reader_b)
        state.world_state["tick"] = 42
        await feed.broadcast(feed.build_snapshot())
        snap_a = json.loads((await feed._recv_frame(reader_a))[1])
        snap_b = json.loads((await feed._recv_frame(reader_b))[1])
        assert snap_a["tick"] == 42
        assert snap_b["tick"] == 42
        writer_a.close()
        writer_b.close()
        await feed.stop()

    _run(go())
