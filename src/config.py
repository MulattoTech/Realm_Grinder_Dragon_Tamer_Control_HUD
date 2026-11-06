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
    "auto_abdicate": False,
    "auto_reincarnate": False,
    "auto_excavate": False,
    "cycle_delay_sec": 5.0,
    "abdicate_multiplier_threshold": 50.0,
    "ultron_burst": True
}

_OPTIONAL_BOOLEAN_DEFAULTS = {
    "require_minimized": True,
    "auto_spells": True,
    "auto_apply_build": True,
}


def load_config() -> Dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
        except Exception:
            return cfg
    # JSON booleans are the only accepted representation for permission flags.
    # In particular, non-empty strings such as "false" are truthy in Python.
    for key, default in DEFAULT_CONFIG.items():
        if type(default) is bool and type(cfg.get(key)) is not bool:
            cfg[key] = default
    for key, default in _OPTIONAL_BOOLEAN_DEFAULTS.items():
        if key in cfg and type(cfg[key]) is not bool:
            cfg[key] = default
    return cfg


def save_config(config: Dict[str, Any]):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    from src.atomic_store import write_json
    write_json(CONFIG_FILE,config)


def update_setting(key: str, value: Any):
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
