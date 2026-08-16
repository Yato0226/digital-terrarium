"""Stage 10 tests: living memory, biographies & generational sagas (Phase 2)."""

import asyncio
import json

import pytest

import core
import engine
import events
import state

pytestmark = pytest.mark.usefixtures("fresh_world")


@pytest.fixture(autouse=True)
def fresh_world():
    state.reset_world()
    events.LOGGING = False
    yield
    events.LOGGING = True


def pawn(pawn_id):
    return state.world_state["pawns"][pawn_id]


def _write_log(tmp_path, rows):
    log = tmp_path / "log.jsonl"
    for row in rows:
        log.open("a", encoding="utf-8").write(json.dumps(row, ensure_ascii=False) + "\n")
    return str(log)


def test_read_log_returns_events(tmp_path, monkeypatch):
    log = _write_log(
        tmp_path,
        [
            {"tick": 1, "type": "chop", "actor": "pawn_1", "description": "chopped"},
            {"tick": 2, "type": "rest", "actor": "pawn_2", "description": "rested"},
        ],
    )
    monkeypatch.setattr(state, "LOG_FILE", log)
    rows = core._read_log()
    assert [r["type"] for r in rows] == ["chop", "rest"]


def test_read_log_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "LOG_FILE", str(tmp_path / "missing.jsonl"))
    assert core._read_log() == []


def test_read_log_skips_garbage_lines(tmp_path, monkeypatch):
    log = tmp_path / "log.jsonl"
    log.write_text("not json\n", encoding="utf-8")
    monkeypatch.setattr(state, "LOG_FILE", str(log))
    assert core._read_log() == []


def test_pawn_events_filters_by_actor(tmp_path, monkeypatch):
    log = _write_log(
        tmp_path,
        [
            {"tick": 1, "type": "chop", "actor": "pawn_1", "description": "Lumberjack chops."},
            {"tick": 2, "type": "rest", "actor": "pawn_2", "description": "Scout rests."},
        ],
    )
    monkeypatch.setattr(state, "LOG_FILE", log)
    evs = core._pawn_events("pawn_1", "Lumberjack")
    assert [e["type"] for e in evs] == ["chop"]


def test_pawn_events_caps_and_orders(tmp_path, monkeypatch):
    rows = [
        {"tick": i, "type": "rest", "actor": "pawn_1", "description": f"rest {i}"}
        for i in range(1, core.BIO_EVENT_LIMIT + 10)
    ]
    monkeypatch.setattr(state, "LOG_FILE", _write_log(tmp_path, rows))
    evs = core._pawn_events("pawn_1", "Lumberjack")
    assert len(evs) == core.BIO_EVENT_LIMIT
    assert evs[-1]["tick"] == core.BIO_EVENT_LIMIT + 9


def test_bio_context_living(tmp_path, monkeypatch):
    p = pawn("pawn_1")
    p["title"] = "the Scarred"
    p["skills"]["combat"] = 9
    p["partners"] = ["pawn_2"]
    log = _write_log(
        tmp_path,
        [
            {"tick": 1, "type": "chop", "actor": "pawn_1", "description": "Lumberjack chops wood."},
        ],
    )
    monkeypatch.setattr(state, "LOG_FILE", log)
    ctx = core._bio_context(p)
    assert "Lumberjack" in ctx
    assert "the Scarred" in ctx
    assert "woodcutting 8" in ctx
    assert "Scout" in ctx  # partner name
    assert "chops wood" in ctx


def test_bio_context_tombstone(tmp_path, monkeypatch):
    tomb = {
        "id": "pawn_9",
        "name": "Old Thane",
        "title": "the Brave",
        "cause": "old age",
        "died_tick": 300,
        "born_tick": 10,
        "epitaph": "Here lies Old Thane.",
        "beloved": True,
    }
    state.world_state["graveyard"].append(tomb)
    log = _write_log(
        tmp_path,
        [
            {"tick": 290, "type": "scout", "actor": "pawn_9", "description": "Old Thane explores the ruins."},
        ],
    )
    monkeypatch.setattr(state, "LOG_FILE", log)
    ctx = core._bio_context(tomb)
    assert "old age" in ctx
    assert "the Brave" in ctx
    assert "Here lies Old Thane" in ctx
    assert "explores the ruins" in ctx
    assert "Day 15" in ctx  # died_tick 300 // 20


def test_compose_bio_uses_llm(monkeypatch):
    calls = []

    def fake_llm(system, user, schema_model, temperature):
        calls.append((system, user, schema_model, temperature))
        return "Scout was a wanderer at heart. She charted the ruins and fed the hungry. She is missed.", "fake"

    monkeypatch.setattr(core, "_llm_call", fake_llm)
    text = asyncio.run(core.compose_bio("pawn_2"))
    assert text == "Scout was a wanderer at heart. She charted the ruins and fed the hungry. She is missed."
    assert calls[0][2] is None
    assert calls[0][3] == 0.9


def test_compose_bio_falls_back_on_llm_failure(monkeypatch):
    def boom(system, user, schema_model, temperature):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(core, "_llm_call", boom)
    text = asyncio.run(core.compose_bio("pawn_2"))
    assert "Scout" in text


def test_compose_bio_unknown_pawn():
    assert asyncio.run(core.compose_bio("pawn_99")) is None


def test_find_pawn_ref_living_by_name():
    pawn_or_tomb, err = engine.find_pawn_ref("scout")
    assert err is None
    assert pawn_or_tomb["name"] == "Scout"


def test_find_pawn_ref_tombstone_by_name():
    state.world_state["graveyard"].append(
        {
            "id": "pawn_9",
            "name": "Old Thane",
            "title": None,
            "cause": "old age",
            "died_tick": 300,
            "born_tick": 10,
            "epitaph": "Here lies Old Thane.",
            "beloved": False,
        }
    )
    pawn_or_tomb, err = engine.find_pawn_ref("old thane")
    assert err is None
    assert pawn_or_tomb["id"] == "pawn_9"
    assert pawn_or_tomb.get("cause") == "old age"


def test_find_pawn_ref_by_id_prefers_living():
    state.world_state["graveyard"].append(
        {"id": "pawn_1", "name": "Lumberjack", "cause": "starvation", "died_tick": 5}
    )
    pawn_or_tomb, err = engine.find_pawn_ref("pawn_1")
    assert err is None
    assert pawn_or_tomb == pawn("pawn_1")


def test_find_pawn_ref_unknown():
    pawn_or_tomb, err = engine.find_pawn_ref("nobody")
    assert pawn_or_tomb is None
    assert "nobody" in err
