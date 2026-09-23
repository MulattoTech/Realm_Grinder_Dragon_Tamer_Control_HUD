"""
Bot configuration manager for Realm Grinder Dragon Tamer.
Provides shared settings that can be toggled on/off in real-time
via the GUI monitor or external scripts.
"""

import os
import json
from typing import Dict, Any

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "state", "bot_config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "paused": True,  # Missing or malformed settings must never enable gameplay.
    "auto_buy_upgrades": True,
    "auto_buy_buildings": True,
    "auto_click_realm": True,
    "auto_cast_spells": True,
    "auto_abdicate": True,
    "auto_reincarnate": True,
    "auto_excavate": True,
    "cycle_delay_sec": 5.0,
    "abdicate_multiplier_threshold": 50.0,
    "ultron_burst": True
}


def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(data)
                return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    from src.atomic_store import write_json
    write_json(CONFIG_FILE,config)


def update_setting(key: str, value: Any):
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
