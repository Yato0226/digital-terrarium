"""Stage 24 tests: physical folklore & herbal medicine (Phase 5, Step 21)."""

import pytest

import core
import engine
import events
import prompts
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


# ---- Physical folklore: carved totems ----


def test_no_totems_by_default():
    assert state.world_state["totems"] == []
    assert state.world_state["last_milestone"] is None


def test_colony_flag_records_milestone():
    engine._earn_colony_flag("fire")
    assert state.world_state["last_milestone"]["title"] == "the Great Fire"
    engine._earn_colony_flag(engine.KINDRED_TAG)
    assert state.world_state["last_milestone"]["title"] == "the Kindred way"
    assert state.world_state["colony"]["earned"]["fire"]


def test_milestone_only_recorded_once_per_flag():
    engine._earn_colony_flag("fire")
    engine._earn_colony_flag("fire")
    assert state.world_state["last_milestone"]["title"] == "the Great Fire"


def test_shrine_blessing_records_milestone():
    shrine = engine._shrine()
    shrine["built"] = True
    shrine["offered"] = engine.SHRINE_BLESSING_OFFERINGS - 1
    p = pawn("pawn_1")
    p["inventory"]["food"] = 5
    engine._do_shrine_offering(p, "pawn_1")
    assert state.world_state["last_milestone"]["title"] == "the Creator's blessing"


def test_carve_totem_requires_milestone():
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 5
    assert engine._carve_totem(p, "pawn_1") is None


def test_carve_totem_requires_camp():
    engine._record_milestone("the Great Fire")
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 5
    p["pos"] = [0, 0]
    assert engine._carve_totem(p, "pawn_1") is None


def test_carve_totem_requires_wood():
    engine._record_milestone("the Great Fire")
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 0
    ev = engine._carve_totem(p, "pawn_1")
    assert ev["type"] == "failed"
    assert ev["data"]["reason"] == "need_wood"


def test_carve_totem_moodlets_colony():
    engine._record_milestone("the Great Fire")
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 5
    ev = engine._carve_totem(p, "pawn_1")
    assert ev["type"] == "totem"
    assert ev["data"]["title"] == "the Great Fire"
    assert p["inventory"]["wood"] == 5 - engine.TOTEM_WOOD
    assert len(state.world_state["totems"]) == 1
    assert any(m["name"] == "Proud of the Great Fire" for m in p["moodlets"])
    assert any(
        "Proud of the Great Fire" in m["name"]
        for p2 in state.world_state["pawns"].values()
        for m in p2["moodlets"]
    )


def test_carve_totem_capped():
    engine._record_milestone("the Great Fire")
    for i in range(engine.TOTEM_MAX):
        p = pawn("pawn_1")
        p["inventory"]["wood"] = 10
        engine._carve_totem(p, "pawn_1")
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 10
    ev = engine._carve_totem(p, "pawn_1")
    assert ev["type"] == "failed"
    assert ev["data"]["reason"] == "totem_cap"
    assert len(state.world_state["totems"]) == engine.TOTEM_MAX


def test_interact_carve_totem_word():
    engine._record_milestone("the Great Fire")
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 5
    ev = engine._do_interact(p, "pawn_1", "carve a totem")
    assert ev["type"] == "totem"


def test_interact_carve_totem_no_milestone_falls_back():
    p = pawn("pawn_1")
    ev = engine._do_interact(p, "pawn_1", "carve a totem")
    assert ev["type"] != "totem"
    assert "no milestone" in ev["data"]["effects"][0]


def test_totems_txt():
    text = core.totems_txt()
    assert "No totems yet" in text
    engine._record_milestone("the Great Fire")
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 5
    engine._carve_totem(p, "pawn_1")
    assert "the Great Fire" in core.totems_txt()


def test_prompt_shows_totems():
    engine._record_milestone("the Great Fire")
    p = pawn("pawn_1")
    p["inventory"]["wood"] = 5
    engine._carve_totem(p, "pawn_1")
    assert "Totems: carved wooden totems remember" in prompts.build_prompt()


# ---- Herbal medicine: salves ----


def test_salves_counter_defaults():
    assert pawn("pawn_1")["counters"]["salves"] == 0


def test_gather_salve_on_meadow():
    p = pawn("pawn_1")
    p["pos"] = [1, 1]
    before_xp = p["skills"]["scouting"]
    ev = engine._gather_salve(p, "pawn_1")
    assert ev["type"] == "gather_herbs"
    assert p["counters"]["salves"] == 1
    assert p["skills"]["scouting"] > before_xp


def test_gather_salve_off_meadow():
    p = pawn("pawn_1")
    assert engine._gather_salve(p, "pawn_1") is None


def test_use_salve_heals_most_injured_tilemate():
    p = pawn("pawn_1")
    other = pawn("pawn_2")
    other["pos"] = [2, 2]
    other["vitals"]["hp"] = 50
    p["counters"]["salves"] = 1
    ev = engine._use_salve(p, "pawn_1")
    assert ev["type"] == "salve"
    assert ev["target"] == "pawn_2"
    assert other["vitals"]["hp"] == 50 + engine.SALVE_HEAL
    assert p["counters"]["salves"] == 0


def test_use_salve_requires_salve():
    p = pawn("pawn_1")
    ev = engine._use_salve(p, "pawn_1")
    assert ev["type"] == "failed"
    assert ev["data"]["reason"] == "no_salve"


def test_use_salve_off_camp():
    p = pawn("pawn_1")
    p["pos"] = [1, 1]
    p["counters"]["salves"] = 1
    assert engine._use_salve(p, "pawn_1") is None


def test_use_salve_clears_frostbite():
    p = pawn("pawn_1")
    other = pawn("pawn_2")
    other["pos"] = [2, 2]
    other["vitals"]["hp"] = 50
    engine._add_moodlet(other, "Frostbitten", -5, 10)
    p["counters"]["salves"] = 1
    engine._use_salve(p, "pawn_1")
    assert not any(m["name"] == "Frostbitten" for m in other["moodlets"])


def test_interact_gather_herbs_word():
    p = pawn("pawn_1")
    p["pos"] = [1, 1]
    ev = engine._do_interact(p, "pawn_1", "gather herbs")
    assert ev["type"] == "gather_herbs"


def test_interact_brew_salve_word():
    p = pawn("pawn_1")
    other = pawn("pawn_2")
    other["pos"] = [2, 2]
    other["vitals"]["hp"] = 40
    p["counters"]["salves"] = 1
    ev = engine._do_interact(p, "pawn_1", "brew a salve and heal")
    assert ev["type"] == "salve"
    assert other["vitals"]["hp"] == 40 + engine.SALVE_HEAL


def test_interact_herb_elsewhere_falls_back():
    p = pawn("pawn_1")
    p["pos"] = [0, 0]
    ev = engine._do_interact(p, "pawn_1", "gather herbs")
    assert ev["type"] == "interact"
    assert "no herbs" in ev["data"]["effects"][0]


def test_prompt_shows_salves():
    p = pawn("pawn_1")
    p["counters"]["salves"] = 2
    assert "Salves: 2" in prompts.build_prompt()
