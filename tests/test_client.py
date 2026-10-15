"""Tests for TrialsClient: URLs, retries, caching, and error mapping."""

from __future__ import annotations

import httpx
import pytest
import respx
from tests.conftest import BASE_URL, load_fixture

from clinical_trials_mcp.client import TrialsClient
from clinical_trials_mcp.config import Settings
from clinical_trials_mcp.errors import (
    StudyNotFoundError,
    UpstreamDataError,
    UpstreamError,
    UpstreamUnavailableError,
)


async def test_get_study_returns_payload(
    api: respx.MockRouter, trials_client: TrialsClient
) -> None:
    study = load_fixture("study_recruiting.json")
    route = api.get("/studies/NCT06001122").mock(return_value=httpx.Response(200, json=study))
    result = await trials_client.get_study("NCT06001122")
    assert result == study
    assert route.called


async def test_get_study_404_becomes_not_found(
    api: respx.MockRouter, trials_client: TrialsClient
) -> None:
    api.get("/studies/NCT99999999").mock(return_value=httpx.Response(404, json={}))
    with pytest.raises(StudyNotFoundError) as info:
        await trials_client.get_study("NCT99999999")
    assert "NCT99999999" in str(info.value)


async def test_search_sends_format_and_count_total(
    api: respx.MockRouter, trials_client: TrialsClient
) -> None:
    page = load_fixture("search_page.json")
    route = api.get("/studies").mock(return_value=httpx.Response(200, json=page))
    result = await trials_client.search_studies({"query.cond": "diabetes", "pageSize": "10"})
    assert result["totalCount"] == 137
    request = route.calls[0].request
    assert request.url.params["format"] == "json"
    assert request.url.params["countTotal"] == "true"
    assert request.url.params["query.cond"] == "diabetes"


async def test_server_error_is_retried_then_succeeds(
    api: respx.MockRouter, trials_client: TrialsClient
) -> None:
    study = load_fixture("study_child.json")
    route = api.get("/studies/NCT06005566").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=study)]
    )
    result = await trials_client.get_study("NCT06005566")
    assert result == study
    assert route.call_count == 2


async def test_persistent_server_error_raises_unavailable(
    api: respx.MockRouter, trials_client: TrialsClient
) -> None:
    route = api.get("/studies/NCT06001122").mock(return_value=httpx.Response(500))
    with pytest.raises(UpstreamUnavailableError) as info:
        await trials_client.get_study("NCT06001122")
    assert route.call_count == 3  # 1 initial + 2 retries
    assert "not responding" in str(info.value)


async def test_timeout_raises_unavailable_after_retries(
    api: respx.MockRouter, trials_client: TrialsClient
) -> None:
    route = api.get("/studies/NCT06001122").mock(side_effect=httpx.ReadTimeout("timed out"))
    with pytest.raises(UpstreamUnavailableError):
        await trials_client.get_study("NCT06001122")
    assert route.call_count == 3


async def test_client_error_is_not_retried(
    api: respx.MockRouter, trials_client: TrialsClient
) -> None:
    route = api.get("/studies").mock(return_value=httpx.Response(400, json={}))
    with pytest.raises(UpstreamError) as info:
        await trials_client.search_studies({"query.cond": "x"})
    assert info.value.status_code == 400
    assert route.call_count == 1


async def test_invalid_json_raises_data_error(
    api: respx.MockRouter, trials_client: TrialsClient
) -> None:
    api.get("/studies/NCT06001122").mock(
        return_value=httpx.Response(200, content=b"<html>not json</html>")
    )
    with pytest.raises(UpstreamDataError):
        await trials_client.get_study("NCT06001122")


async def test_cache_avoids_second_request(api: respx.MockRouter) -> None:
    cached_settings = Settings(
        base_url=BASE_URL, timeout_seconds=5.0, cache_ttl_seconds=60.0, max_retries=0
    )
    client = TrialsClient(cached_settings)
    study = load_fixture("study_child.json")
    route = api.get("/studies/NCT06005566").mock(return_value=httpx.Response(200, json=study))
    first = await client.get_study("NCT06005566")
    second = await client.get_study("NCT06005566")
    assert first == second == study
    assert route.call_count == 1


async def test_failures_are_not_cached(api: respx.MockRouter) -> None:
    cached_settings = Settings(
        base_url=BASE_URL, timeout_seconds=5.0, cache_ttl_seconds=60.0, max_retries=0
    )
    client = TrialsClient(cached_settings)
    study = load_fixture("study_child.json")
    route = api.get("/studies/NCT06005566").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json=study)]
    )
    with pytest.raises(UpstreamUnavailableError):
        await client.get_study("NCT06005566")
    result = await client.get_study("NCT06005566")
    assert result == study
    assert route.call_count == 2
