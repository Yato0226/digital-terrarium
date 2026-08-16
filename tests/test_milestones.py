"""Stage 10 Step 6 tests: the Milestone Announcement System.

Discord no longer receives an embed every tick — the full state embed posts
only on high-impact ticks, and dedicated milestone embeds (era chronicle,
fallen-hero eulogy, breaking crisis) fire alongside. Posting itself is
exercised by monkeypatching core._post_embed; no real webhook is touched.
"""

import asyncio

import pytest

import core
import engine
import events
import state


@pytest.fixture(autouse=True)
def fresh_world():
    state.reset_world()
    events.LOGGING = False
    core.POSTING_ENABLED = True
    yield
    events.LOGGING = True
    core.POSTING_ENABLED = True


# --- Milestone gating ---------------------------------------------------------


def test_quiet_tick_is_not_a_milestone():
    assert not core._is_milestone_tick(
        [
            {"type": "move", "description": "walks east"},
            {"type": "chop", "description": "chops a tree"},
            {"type": "forage", "description": "picks berries"},
        ]
    )
    assert not core._is_milestone_tick([])


def test_milestone_event_types_count():
    assert core._is_milestone_tick([{"type": "death"}])
    assert core._is_milestone_tick([{"type": "birth"}])
    assert core._is_milestone_tick([{"type": "season"}])
    assert core._is_milestone_tick([{"type": "feast"}])
    assert core._is_milestone_tick([{"type": "tradition"}])
    assert core._is_milestone_tick([{"type": "quest_complete"}])
    assert core._is_milestone_tick([{"type": "move"}, {"type": "raid"}])


def test_crises_are_also_milestones():
    assert set(core.CRISIS_EVENT_TYPES) <= set(core.MILESTONE_EVENT_TYPES)


# --- Dedicated milestone embeds ----------------------------------------------


def test_post_chronicle_embed(monkeypatch):
    sent = []
    monkeypatch.setattr(core, "_post_embed", sent.append)
    core.post_chronicle(
        {
            "season": "Winter",
            "title": "The Winter of the White",
            "text": "The snows came and the colony huddled by the fire.",
            "tick": 300,
        }
    )
    assert len(sent) == 1
    embed = sent[0]
    assert "Winter of the White" in embed["title"]
    assert "snows came" in embed["description"]
    assert embed["color"] == 0xD4AF37
    assert embed["fields"][0]["value"] == "Winter"


def test_post_eulogy_embed(monkeypatch):
    sent = []
    monkeypatch.setattr(core, "_post_embed", sent.append)
    core.post_eulogy(
        {
            "name": "Bob",
            "cause": "old age",
            "died_tick": 320,
            "epitaph": "He swung an honest axe.",
        }
    )
    assert len(sent) == 1
    embed = sent[0]
    assert "Bob" in embed["title"]
    assert embed["description"] == "He swung an honest axe."
    assert embed["fields"][0]["value"] == "old age"
    assert embed["fields"][1]["value"] == f"{320 // engine.TICKS_PER_DAY} (tick 320)"


def test_post_eulogy_falls_back_without_epitaph(monkeypatch):
    sent = []
    monkeypatch.setattr(core, "_post_embed", sent.append)
    core.post_eulogy({"name": "Ann", "cause": "starvation", "died_tick": 100})
    assert sent[0]["description"] != ""


def test_post_crisis_only_fires_on_crisis_events(monkeypatch):
    sent = []
    monkeypatch.setattr(core, "_post_embed", sent.append)
    core.post_crisis(
        [
            {"type": "move", "description": "walking", "tick": 1},
            {"type": "raid", "description": "scavengers at the gate", "tick": 2},
            {"type": "chop", "description": "chopping", "tick": 3},
            {"type": "fire_start", "description": "the forest is ablaze", "tick": 4},
            {"type": "flood", "description": "the meadows are drowned", "tick": 5},
            {"type": "miasma", "description": "poison spores drift in", "tick": 6},
        ]
    )
    assert len(sent) == 4
    assert sent[0]["title"] == "🥷 Scavenger Raid!"
    assert "scavengers" in sent[0]["description"]
    assert sent[1]["title"] == "🔥 Wildfire!"
    assert sent[2]["title"] == "🌊 Flash Flood!"
    assert sent[3]["title"] == "☠️ Toxic Miasma!"
    assert sent[0]["color"] == 0xFF4444
    assert sent[0]["footer"]["text"] == "Tick 2"


def test_post_embed_noop_when_disabled(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("must not post")

    monkeypatch.setattr(core.requests, "post", boom)
    core.POSTING_ENABLED = False
    core._post_embed({"title": "x"})


# --- Integrated through _chronicle_season -------------------------------------


def test_chronicle_season_posts_era_embed(monkeypatch):
    sent = []
    monkeypatch.setattr(core, "_post_embed", sent.append)

    def fake_llm(system, user, schema_model, temperature):
        return (
            "The Summer of the Long Nights\n\nThe colony survived the flood.\n",
            "fake-model",
        )

    monkeypatch.setattr(core, "_llm_call", fake_llm)
    state.world_state["tick"] = 101
    asyncio.run(core._chronicle_season("Summer"))
    assert len(sent) == 1
    assert "Long Nights" in sent[0]["title"]
    assert "survived the flood" in sent[0]["description"]
