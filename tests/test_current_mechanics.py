"""Regression coverage for the statically verified 4.3.22 mechanics subset."""
import json
from pathlib import Path

import pytest

from src.mechanics import RuleBook
from src.wiki_data import get_reincarnation_gem_requirement


ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_SWF = "7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b"


def rules():
    return json.loads((ROOT / "data" / "progression_rules.json").read_text(encoding="utf-8"))["rules"]


def supported_state(**values):
    state = {
        "ascension": 0,
        "reincarnation": 46,
        "excavations": 1500,
        "game_identity": {
            "supported": True,
            "game_version": "4.3.22",
            "save_version": 58,
            "swf_sha256": SUPPORTED_SWF,
        },
        "raw_data": {"saveVersion": 58, "upgrades": {}, "trophies": {}},
    }
    state.update(values)
    return state


@pytest.mark.parametrize(
    "r,ascension,expected",
    [(24, 0, 1e99), (40, 0, 1e147), (40, 1, 1e27), (46, 1, 1e39)],
)
def test_installed_4322_reincarnation_thresholds(r, ascension, expected):
    assert get_reincarnation_gem_requirement(r, ascension) == expected


@pytest.mark.parametrize("r,ascension", [(-1, 0), (100, 0), (39, 1), (42, 2)])
def test_unsupported_reincarnation_domain_fails_closed(r, ascension):
    assert get_reincarnation_gem_requirement(r, ascension) == float("inf")


def test_reincarnation_helper_keeps_legacy_a0_default():
    assert get_reincarnation_gem_requirement(40) == 1e147


def test_rules_require_exact_supported_game_binary_even_for_owned_dragon_trophy():
    state = supported_state()
    state["raw_data"]["trophies"] = {"210": {}}
    book = RuleBook(rules())
    assert book.plan("Dragon Tamer", state)["complete"] is True

    for identity in (
        None,
        {"supported": False, "game_version": "4.3.22", "save_version": 58, "swf_sha256": SUPPORTED_SWF},
        {"supported": True, "game_version": "4.3.11", "save_version": 58, "swf_sha256": "a" * 64},
    ):
        state = supported_state()
        state["raw_data"]["trophies"] = {"210": {}}
        if identity is None:
            state.pop("game_identity")
        else:
            state["game_identity"] = identity
        result = book.plan("Dragon Tamer", state)
        assert result["complete"] is False
        assert result["next_action"]["action"] == "reference_only"
        assert result["steps"][-1]["status"] == "UNSUPPORTED_GAME_VERSION"

    state = supported_state(raw_data={"saveVersion": 57, "upgrades": {}, "trophies": {"210": {}}})
    result = book.plan("Dragon Tamer", state)
    assert result["complete"] is False
    assert result["next_action"]["action"] == "reference_only"


def test_egg_is_supported_from_r42_with_excavation_threshold():
    book = RuleBook(rules())
    state = supported_state(reincarnation=42, excavations=1499)
    result = book.plan("Spiky Rough Egg", state)
    assert result["next_action"]["target"] == 1500
    assert result["next_action"]["action"] == "excavate"

    state["excavations"] = 1500
    result = book.plan("Spiky Rough Egg", state)
    assert result["next_action"]["action"] == "excavate_for_egg"


def test_hatch_static_counter_boundary_is_7200_seconds():
    book = RuleBook(rules())
    state = supported_state(reincarnation=42, dragon_quest_counter=7199)
    state["raw_data"]["trophies"] = {"211": {}}
    assert book.plan("Hatch!", state)["next_action"]["status"] == "LOCKED"

    state["dragon_quest_counter"] = 7200
    result = book.plan("Hatch!", state)
    assert result["next_action"]["target"] == "Hatch!"
    assert result["next_action"]["action"] == "purchase_dragon_stage"


def test_elder_dragon_at_r46_routes_to_r48():
    state = supported_state(reincarnation=46)
    state["raw_data"]["upgrades"] = {str(identifier): {"u1": True} for identifier in (604, 605, 606)}
    result = RuleBook(rules()).plan("Elder Dragon", state)
    assert result["next_action"]["target"] == "Reach R48"
    assert result["next_action"]["action"] == "reach_reincarnation"
    assert result["next_action"]["target_r"] == 48


@pytest.mark.parametrize(
    "goal,reincarnation,owned_upgrades,target_r,extra",
    [
        ("Drakeling", 43, (604,), 44, {}),
        ("Dragon", 45, (604, 605), 46, {"faction": 0, "assistants_num": 5000}),
    ],
)
def test_dragon_stage_r_boundaries_route_to_the_next_reincarnation(goal, reincarnation, owned_upgrades, target_r, extra):
    state = supported_state(reincarnation=reincarnation, dragon_quest_counter=7200, **extra)
    state["raw_data"]["trophies"] = {"211": {}}
    state["raw_data"]["upgrades"] = {str(identifier): {"u1": True} for identifier in owned_upgrades}
    result = RuleBook(rules()).plan(goal, state)
    assert result["next_action"]["target_r"] == target_r


def test_unmapped_dragon_timer_and_volatile_requirements_stay_unknown():
    state = supported_state(reincarnation=48)
    state["raw_data"]["trophies"] = {"211": {}}
    state["raw_data"]["upgrades"] = {str(identifier): {"u1": True} for identifier in (604, 605, 606)}
    result = RuleBook(rules()).plan("Elder Dragon", state)
    assert result["next_action"]["action"] == "needs_measurement"
    assert result["steps"][-1]["status"] == "UNKNOWN"
    measurements = {condition["field"]: condition["satisfied"] for condition in result["steps"][-1]["conditions"]}
    assert measurements["dragon_quest_counter"] is None
    assert measurements["mana_max"] is None


def test_dragon_and_elder_thresholds_and_unknown_costs_are_explicit_in_data():
    indexed = {rule["name"]: rule for rule in rules()}
    assert "Reach R42" in indexed and "Reach R44" in indexed and "Reach R48" in indexed
    dragon = indexed["Dragon"]
    assert dragon["ownership"] == {"kind": "upgrade", "id": 606}
    assert {condition["field"]: condition["value"] for condition in dragon["conditions"]} == {
        "reincarnation": 46,
        "faction": 0,
        "assistants_num": 5000,
        "dragon_quest_counter": 7200,
    }
    elder = indexed["Elder Dragon"]
    assert {condition["field"]: condition["value"] for condition in elder["conditions"]} == {
        "reincarnation": 48,
        "mana_max": 60000,
        "dragon_quest_counter": 7200,
    }
    for name in ("Hatch!", "Drakeling", "Dragon", "Elder Dragon"):
        assert indexed[name]["costs"] == []
        assert any("unverified" in note.lower() for note in indexed[name]["notes"])
