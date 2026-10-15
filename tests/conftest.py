"""Shared fixtures: offline HTTP mocking for the ClinicalTrials.gov API.

All tests run against respx routes backed by the JSON fixtures in
tests/fixtures/. No test touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import respx

from clinical_trials_mcp import client as client_module
from clinical_trials_mcp.client import TrialsClient
from clinical_trials_mcp.config import Settings

BASE_URL = "https://clinicaltrials.gov/api/v2"
FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the real backoff delay so failure-path tests stay fast."""
    monkeypatch.setattr(client_module, "RETRY_BASE_DELAY_SECONDS", 0.0)


@pytest.fixture(autouse=True)
def no_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests hermetic: never route mocked traffic through a system proxy.

    Some environments export *_PROXY variables that httpx picks up by
    default; offline tests must not depend on them.
    """
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings() -> Settings:
    return Settings(base_url=BASE_URL, timeout_seconds=5.0, cache_ttl_seconds=0.0, max_retries=2)


@pytest.fixture
def api() -> respx.MockRouter:
    """A respx router scoped to the API base URL. Nothing is routed by default."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        yield router


@pytest.fixture
def trials_client(settings: Settings) -> TrialsClient:
    return TrialsClient(settings)


@pytest.fixture(
    params=[
        "study_recruiting.json",
        "study_female_only.json",
        "study_child.json",
        "study_open_age.json",
    ]
)
def any_study(request: pytest.FixtureRequest) -> dict[str, Any]:
    return load_fixture(request.param)
