"""Tests for environment-based configuration."""

from __future__ import annotations

import pytest

from clinical_trials_mcp.config import (
    DEFAULT_BASE_URL,
    Settings,
)

ENV_VARS = (
    "CT_MCP_BASE_URL",
    "CT_MCP_TIMEOUT_SECONDS",
    "CT_MCP_CACHE_TTL_SECONDS",
    "CT_MCP_MAX_RETRIES",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults() -> None:
    settings = Settings.from_env()
    assert settings.base_url == DEFAULT_BASE_URL
    assert settings.timeout_seconds == 15.0
    assert settings.cache_ttl_seconds == 300.0
    assert settings.max_retries == 2


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CT_MCP_BASE_URL", "https://example.test/api/")
    monkeypatch.setenv("CT_MCP_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("CT_MCP_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("CT_MCP_MAX_RETRIES", "5")
    settings = Settings.from_env()
    assert settings.base_url == "https://example.test/api"  # trailing slash stripped
    assert settings.timeout_seconds == 30.0
    assert settings.cache_ttl_seconds == 0.0
    assert settings.max_retries == 5


def test_invalid_env_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CT_MCP_TIMEOUT_SECONDS", "soon")
    monkeypatch.setenv("CT_MCP_MAX_RETRIES", "many")
    settings = Settings.from_env()
    assert settings.timeout_seconds == 15.0
    assert settings.max_retries == 2


def test_negative_retries_clamped_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CT_MCP_MAX_RETRIES", "-3")
    assert Settings.from_env().max_retries == 0
