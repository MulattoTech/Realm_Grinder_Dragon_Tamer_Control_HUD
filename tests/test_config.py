"""Fail-closed loading of gameplay permission settings."""
import json

from src import config


def test_consequential_actions_default_disabled():
    assert config.DEFAULT_CONFIG['auto_abdicate'] is False
    assert config.DEFAULT_CONFIG['auto_reincarnate'] is False
    assert config.DEFAULT_CONFIG['auto_excavate'] is False


def test_partial_config_keeps_safe_defaults_and_rejects_string_booleans(tmp_path, monkeypatch):
    path = tmp_path / 'bot_config.json'
    path.write_text(json.dumps({
        'paused': 'false',
        'auto_abdicate': 'false',
        'auto_reincarnate': True,
        'auto_excavate': 'true',
        'auto_buy_upgrades': 'false',
        'require_minimized': 'false',
        'selected_path': 'Fairy',
    }))
    monkeypatch.setattr(config, 'CONFIG_FILE', str(path))

    loaded = config.load_config()

    assert loaded['paused'] is True
    assert loaded['auto_abdicate'] is False
    assert loaded['auto_reincarnate'] is True
    assert loaded['auto_excavate'] is False
    assert loaded['auto_buy_upgrades'] is True
    assert loaded['auto_buy_buildings'] is True
    assert loaded['require_minimized'] is True
    assert loaded['selected_path'] == 'Fairy'


def test_malformed_config_falls_back_to_paused_safe_defaults(tmp_path, monkeypatch):
    path = tmp_path / 'bot_config.json'
    path.write_text('{"paused": false,')
    monkeypatch.setattr(config, 'CONFIG_FILE', str(path))

    loaded = config.load_config()

    assert loaded['paused'] is True
    assert loaded['auto_abdicate'] is False
    assert loaded['auto_reincarnate'] is False
    assert loaded['auto_excavate'] is False
