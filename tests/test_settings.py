"""Basic settings round-trip tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from zen_type.config.settings import DEFAULT_CONFIG, SCHEMA_VERSION, Settings


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    return Settings(path=tmp_path / "config.json")


def test_defaults_on_first_load(tmp_settings: Settings) -> None:
    cfg = tmp_settings.load()
    assert cfg["schema_version"] == SCHEMA_VERSION
    assert cfg["sttProvider"] == "groq"
    assert cfg["llmProvider"] == "groq"
    assert "hotkeys" in cfg
    assert set(cfg["hotkeys"].keys()) == {"dictate", "transform", "ask"}


def test_config_file_is_created(tmp_settings: Settings) -> None:
    tmp_settings.load()
    assert tmp_settings.path.exists()


def test_save_then_load(tmp_settings: Settings) -> None:
    cfg = tmp_settings.load()
    cfg["language"] = "zh-TW"
    tmp_settings.save(cfg)
    tmp_settings.invalidate()
    reloaded = tmp_settings.load()
    assert reloaded["language"] == "zh-TW"


def test_merge_missing_keys(tmp_settings: Settings) -> None:
    # Simulate an old config that lacks new keys
    tmp_settings.path.parent.mkdir(parents=True, exist_ok=True)
    tmp_settings.path.write_text('{"sttProvider":"groq"}', encoding="utf-8")
    cfg = tmp_settings.load()
    # Missing keys should be backfilled from DEFAULT_CONFIG
    assert cfg["llmProvider"] == DEFAULT_CONFIG["llmProvider"]
    assert "hotkeys" in cfg
    assert cfg["schema_version"] == SCHEMA_VERSION


def test_set_api_key(tmp_settings: Settings) -> None:
    tmp_settings.set_api_key("groq", "gsk_test_123")
    tmp_settings.invalidate()
    cfg = tmp_settings.load()
    assert cfg["apiKeys"]["groq"] == "gsk_test_123"


def test_validate_clean_config(tmp_settings: Settings) -> None:
    errors = tmp_settings.validate()
    assert errors == []


def test_validate_bad_provider(tmp_settings: Settings) -> None:
    cfg = tmp_settings.load()
    cfg["sttProvider"] = "bogus"
    tmp_settings.save(cfg)
    errors = tmp_settings.validate()
    assert any("sttProvider" in e for e in errors)
