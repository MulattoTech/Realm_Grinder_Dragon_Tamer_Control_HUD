"""
Structured Realm Grinder Knowledge Base compiled from G00F's Not-a-Wiki (http://musicfamily.org/realm/).
Contains precise build templates, Dragon Unlock stage requirements, formulas, and progression advisor.
"""

from typing import Dict, Any, List, Optional

DRAGON_UNLOCK_STAGES = {
    0: {
        "name": "Spiky Rough Egg",
        "type": "Quest Artifact",
        "id": 211,
        "req_r": 46,
        "req_excavations": 1500,
        "chance_formula": "2%",
        "description": "R46+, 1500+ Excavations. Required to begin Dragon progression."
    },
    1: {
        "name": "Hatch!",
        "type": "Stage 1 Upgrade",
        "upgrade_id": 1244,
        "time_gate_seconds": 12 * 3600,
        "time_gate_description": "12 hours since obtaining Spiky Rough Egg",
        "cost_coins": 1e64,
        "cost_coins_fmt": "10 Vg (1e64)",
        "cost_faction_coins": 1e7,
        "cost_fc_fmt": "10 M (1e7) of each FC",
        "description": "Hatches the spiky egg and reveals what is inside."
    },
    2: {
        "name": "Drakeling",
        "type": "Stage 2 Upgrade",
        "upgrade_id": 1245,
        "time_gate_seconds": 12 * 3600,
        "time_gate_description": "12 hours of active Hellfire Blast since Hatch!",
        "cost_coins": 1e67,
        "cost_coins_fmt": "10 Uvg (1e67)",
        "cost_faction_coins": 1e8,
        "cost_fc_fmt": "100 M (1e8) of each FC",
        "note": "Do not use Research A25 as it can distort the Hellfire Blast activity counter.",
        "description": "Grows baby dragon into a drakeling through fire breath mastery."
    },
    3: {
        "name": "Dragon",
        "type": "Stage 3 Upgrade",
        "upgrade_id": 1246,
        "time_gate_seconds": 12 * 3600,
        "time_gate_description": "12 hours since purchasing Drakeling",
        "req_assistants": 3750,
        "assistants_description": "3,750 Fairy Assistants (Fairy Chanting assists count)",
        "cost_coins": 1e70,
        "cost_coins_fmt": "10 Dvg (1e70)",
        "cost_faction_coins": 1e9,
        "cost_fc_fmt": "1 B (1e9) of each FC",
        "description": "Grows drakeling into a mature Dragon with fairy assistant support."
    },
    4: {
        "name": "Elder Dragon",
        "type": "Stage 4 Upgrade / Dragon Tamer Trophy",
        "upgrade_id": 1247,
        "trophy_id": 466,
        "time_gate_seconds": 12 * 3600,
        "time_gate_description": "12 hours since purchasing Dragon",
        "req_max_mana": 50000,
        "max_mana_description": "50,000 Maximum Mana",
        "cost_coins": 1e73,
        "cost_coins_fmt": "10 Tvg (1e73)",
        "cost_faction_coins": 1e10,
        "cost_fc_fmt": "10 B (1e10) of each FC",
        "description": "Unlocks Elder Dragon and awards the real in-game Dragon Tamer Trophy & Steam Achievement!"
    }
}


BUILDS_DATABASE = {
    # R16-R25 Early / Mid Bracket
    "R24_MERC_NEUTRAL": {
        "name": "Neutral Mercenary (Assisted Advancement)",
        "author": "G00F Not-a-Wiki",
        "faction": "Neutral Mercenary",
        "bloodline": "Fairy",
        "min_r": 16,
        "max_r": 29,
        "gem_min": 1e35,
        "gem_max": 1e75,
        "template": "FR2,FR7,EL5,GB1,TT1,TT7,DD1,DD6,DD7,FC4,DN4,DW7,SP:Fairy Chanting,SP:God's Hand",
        "spells": ["Fairy Chanting", "God's Hand"],
        "notes": "Optimal rush build for 1e35 to 1e75 gems. Massive assistant scaling from Fairy Bloodline + Goblin/Druid synergy."
    },
    "R24_GOBLIN_RESEARCH": {
        "name": "Druidline Goblin Research (R24)",
        "author": "Ensteffahn",
        "faction": "Goblin",
        "bloodline": "Druid",
        "min_r": 24,
        "max_r": 24,
        "gem_min": 1e72,
        "gem_max": 1e99,
        "template": "S50,S105,S150,S215,S270,C105,C120,C135,C150,C175,D55,D135,D200,D250,D290,E80,E135,E150,E200,E225,A10,A105,A120,A150,A250,W25,W120,W150,W180,W205",
        "notes": "Pushes R24 from 1e72 gems to 1e99 gems (1 Dtg) to trigger Reincarnation 25."
    },
    "R25_GOBLIN_RESEARCH": {
        "name": "Druidline Goblin Research (R25)",
        "author": "Ensteffahn",
        "faction": "Goblin",
        "bloodline": "Druid",
        "min_r": 25,
        "max_r": 25,
        "gem_min": 1e72,
        "gem_max": 1e102,
        "template": "S50,S105,S150,S215,S270,C105,C120,C135,C150,C175,D55,D200,D250,D290,D320,E80,E135,E150,E200,E225,A10,A105,A120,A150,A250,W25,W120,W150,W205,W320",
        "notes": "R25 push to 1e102 gems for Reincarnation 26."
    },
    "R26_29_GOBLIN": {
        "name": "Druidline Goblin Research (R26-R29)",
        "author": "G00F",
        "faction": "Goblin",
        "bloodline": "Druid",
        "min_r": 26,
        "max_r": 29,
        "gem_min": 1e72,
        "gem_max": 1e85,
        "template": "S50,S105,S150,S215,S330,C105,C120,C135,C150,C340,D55,D200,D250,D290,D320,E80,E150,E200,E225,E330,A10,A105,A120,A150,A250,W25,W120,W150,W205,W320",
        "notes": "R26-R29 mid-game push up to 1e85 gems."
    },
    "R26_29_DRUID": {
        "name": "Druid Research (R26-R29)",
        "author": "G00F",
        "faction": "Druid",
        "bloodline": "Druid",
        "min_r": 26,
        "max_r": 29,
        "gem_min": 1e85,
        "gem_max": 1e114,
        "template": "S105,S200,S215,S270,S330,C120,C135,C150,C300,C330,D55,D200,D275,D290,D320,E145,E150,E200,E250,E260,E330,A105,A120,A150,A250,A305,A330,W120,W150,W320,W330,W350",
        "notes": "Requires Ancient Device. Pushes to Reincarnation threshold."
    },
    "R30_39_FAIRY_DWARF": {
        "name": "Enchanted Field Fairy/Dwarf (R30-R39)",
        "author": "Cyden",
        "faction": "Fairy/Dwarf",
        "bloodline": "Fairy",
        "min_r": 30,
        "max_r": 39,
        "gem_min": 1e66,
        "gem_max": 1e90,
        "template": "S1,S135,S215,S250,S330,C80,C120,C150,C330,C400,D55,D225,D245,D290,D320,E50,E135,E150,E200,E330,A105,A120,A150,A330,A400,W150,W180,W290,W320,W330",
        "notes": "Prestige Research Fairy build for early R30s."
    },
    "R40_46_DRUIDLINE_GOBLIN": {
        "name": "U Druidline Goblin (R40-R46)",
        "author": "Ensteffahn",
        "faction": "Goblin/Drow",
        "bloodline": "Druid",
        "min_r": 40,
        "max_r": 46,
        "gem_min": 0,
        "gem_max": 1e100,
        "template": "S50,S135,S215,S330,S500,C150,C175,C340,C400,C500,D55,D200,D250,D290,D320,E1,E80,E225,E330,E590,A105,A120,A150,A250,A410,W25,W150,W180,W205,W290",
        "notes": "Standard progression build up to R46 Dragon Unlock threshold."
    }
}


def get_recommended_build(r: int, current_gems: float) -> Dict[str, Any]:
    """Returns the optimal build recommendation based on R and gem count."""
    if r < 24:
        return BUILDS_DATABASE["R24_MERC_NEUTRAL"]
    elif r == 24:
        if current_gems < 1e72:
            return BUILDS_DATABASE["R24_MERC_NEUTRAL"]
        else:
            return BUILDS_DATABASE["R24_GOBLIN_RESEARCH"]
    elif r == 25:
        if current_gems < 1e72:
            return BUILDS_DATABASE["R24_MERC_NEUTRAL"]
        else:
            return BUILDS_DATABASE["R25_GOBLIN_RESEARCH"]
    elif 26 <= r <= 29:
        if current_gems < 1e72:
            return BUILDS_DATABASE["R24_MERC_NEUTRAL"]
        elif current_gems < 1e85:
            return BUILDS_DATABASE["R26_29_GOBLIN"]
        else:
            return BUILDS_DATABASE["R26_29_DRUID"]
    elif 30 <= r <= 39:
        return BUILDS_DATABASE["R30_39_FAIRY_DWARF"]
    elif 40 <= r <= 46:
        return BUILDS_DATABASE["R40_46_DRUIDLINE_GOBLIN"]
    else:
        return BUILDS_DATABASE["R40_46_DRUIDLINE_GOBLIN"]


def get_reincarnation_gem_requirement(r: int) -> float:
    """Returns exact required gems to reincarnate at reincarnation level r."""
    if r < 40:
        return 10.0 ** (27 + r * 3)
    else:
        # A1 scaling
        return 1e99


def load_knowledge_base() -> Dict[str, Any]:
    import os, json
    kb_path = os.path.join(os.path.dirname(__file__), "..", "scraped_wiki", "knowledge_base.json")
    if os.path.exists(kb_path):
        try:
            with open(kb_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def lookup_research(code: str) -> Optional[Dict[str, Any]]:
    """Lookup full research details from the scraped wiki catalog."""
    kb = load_knowledge_base()
    catalog = kb.get("research_catalog", {})
    return catalog.get(code.upper())


def lookup_trophy(name: str) -> Optional[Dict[str, Any]]:
    """Lookup trophy unlock requirements from the scraped wiki."""
    kb = load_knowledge_base()
    catalog = kb.get("trophies_catalog", {})
    for tname, tinfo in catalog.items():
        if name.lower() in tname.lower():
            return tinfo
    return None

