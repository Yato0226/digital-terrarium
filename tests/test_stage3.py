"""Stage 3 tests: seasonal chronicle, heirlooms, adoptions, and the PNG map renderer."""

import asyncio
import struct

import pytest

import core
import engine
import events
import map_renderer
import state

pytestmark = pytest.mark.usefixtures("fresh_world")


@pytest.fixture(autouse=True)
def fresh_world():
    state.reset_world()
    events.LOGGING = False
    core.POSTING_ENABLED = False
    yield
    events.LOGGING = True
    core.POSTING_ENABLED = True


def pawn(pawn_id):
    return state.world_state["pawns"][pawn_id]


def test_season_change_signal_set():
    state.world_state["tick"] = 100  # Spring is 0..99; tick 100 begins Summer
    state.world_state["biome"]["season"] = "Spring"
    state.pending_chronicle = None
    engine.tick_environment()
    assert state.world_state["biome"]["season"] == "Summer"
    assert state.pending_chronicle == "Summer"


def test_no_season_signal_on_same_season():
    state.world_state["tick"] = 50
    state.world_state["biome"]["season"] = "Spring"
    state.pending_chronicle = None
    engine.tick_environment()
    assert state.pending_chronicle is None


def test_chronicle_entry_shape(monkeypatch):
    state.world_state["tick"] = 101

    def fake_llm(system, user, schema_model, temperature):
        return (
            "The Summer of the Long Nights\n\n"
            "The colony huddled by the campfire and survived the flood.\n",
            "fake-model",
        )

    monkeypatch.setattr(core, "_llm_call", fake_llm)
    asyncio.run(core._chronicle_season("Summer"))
    entry = state.world_state["chronicle"][-1]
    assert set(entry) == {"season", "title", "text", "tick"}
    assert entry["season"] == "Summer"
    assert entry["title"] == "The Summer of the Long Nights"
    assert "campfire" in entry["text"]
    assert entry["tick"] == 101
    assert any(e["type"] == "chronicle" for e in state.world_state["history"])


def test_chronicle_caps_entries(monkeypatch):
    def fake_llm(system, user, schema_model, temperature):
        return ("Title\nBody text\n", "fake")

    monkeypatch.setattr(core, "_llm_call", fake_llm)
    for i in range(core.MAX_CHRONICLE + 5):
        state.world_state["tick"] = i + 1
        asyncio.run(core._chronicle_season("Spring"))
    assert len(state.world_state["chronicle"]) == core.MAX_CHRONICLE


def test_titled_death_drops_heirloom():
    p = pawn("pawn_1")
    p["title"] = "the Scarred"
    p["gear"]["main_hand"] = "Flint Spear"
    engine._kill("pawn_1", p, "old age")
    hs = state.world_state["heirlooms"]
    assert len(hs) == 1
    h = hs[0]
    assert h["name"] == "Lumberjack's Flint Spear"
    assert h["stat_bonus"] == {"combat": 1}
    assert h["moodlet_delta"] > 0
    assert h["source"] == "death of Lumberjack"
    assert set(h) == {"id", "name", "stat_bonus", "moodlet_delta", "source"}


def test_untitled_death_drops_no_heirloom():
    p = pawn("pawn_1")
    p["gear"]["main_hand"] = "Flint Spear"
    engine._kill("pawn_1", p, "old age")
    assert state.world_state["heirlooms"] == []


def test_interact_claims_heirloom_by_name():
    state.world_state["heirlooms"].append(
        {
            "id": "heirloom_1",
            "name": "Scout's Stone Axe",
            "stat_bonus": {"woodcutting": 1},
            "moodlet_delta": 5,
            "source": "death of Scout",
        }
    )
    p = pawn("pawn_1")
    before = p["skills"]["woodcutting"]
    ev = engine._do_interact(p, "pawn_1", "claim Scout's Stone Axe")
    assert ev["type"] == "interact"
    assert state.world_state["heirlooms"][0]["owner"] == "pawn_1"
    assert p["skills"]["woodcutting"] == before + 1
    assert any(m["name"] == "Proud" for m in p["moodlets"])


def test_interact_claim_no_heirloom_does_not_bump_morale():
    p = pawn("pawn_1")
    before = p["vitals"]["morale"]
    ev = engine._do_interact(p, "pawn_1", "claim nothing here")
    assert ev["type"] == "interact"
    assert "no heirloom" in " ".join(ev["data"]["effects"])
    assert p["vitals"]["morale"] == before


def test_death_releases_owned_heirloom():
    state.world_state["heirlooms"].append(
        {
            "id": "heirloom_1",
            "name": "Scout's Stone Axe",
            "stat_bonus": {"woodcutting": 1},
            "moodlet_delta": 5,
            "source": "death of Scout",
            "owner": "pawn_1",
        }
    )
    p = pawn("pawn_1")
    engine._kill("pawn_1", p, "old age")
    assert state.world_state["heirlooms"][0].get("owner") is None


def test_adoptions_persist_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "STATE_FILE", str(tmp_path / "state.json"))
    state.world_state["adoptions"]["123456"] = "pawn_2"
    state.save_state()
    state.world_state["adoptions"].clear()
    state.load_state()
    assert state.world_state["adoptions"] == {"123456": "pawn_2"}


def test_notifier_called_on_matching_events(monkeypatch):
    state.world_state["adoptions"]["123456"] = "pawn_1"
    calls = []

    async def fake_notifier(user_id, message):
        calls.append((user_id, message))

    monkeypatch.setattr(core, "notifier", fake_notifier)
    events_list = [
        {"type": "birth", "actor": "pawn_1", "description": "Lumberjack gives birth."},
        {"type": "goal", "actor": "pawn_2", "description": "Scout fulfills a goal."},
        {"type": "break", "actor": "pawn_1", "description": "Lumberjack has a mental break."},
        {"type": "death", "actor": "pawn_1", "description": "Lumberjack has died."},
        {"type": "forage", "actor": "pawn_1", "description": "No DM for this."},
    ]
    asyncio.run(core._notify_adopted(events_list))
    assert len(calls) == 3
    assert all(uid == "123456" for uid, _ in calls)


def test_map_renderer_png_header():
    data = map_renderer.render_png()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert width == 5 * map_renderer.CELL
    assert height == 5 * map_renderer.CELL
