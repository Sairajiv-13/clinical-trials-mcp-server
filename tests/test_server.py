"""End-to-end tool tests through FastMCP's in-memory client.

The HTTP layer is mocked with respx, so these exercise the full path:
tool call, query building, client, parsing, and structured output.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from clinical_trials_mcp import server
from clinical_trials_mcp.client import TrialsClient
from clinical_trials_mcp.server import build_search_params, normalize_phase, normalize_status
from tests.conftest import load_fixture


@pytest.fixture(autouse=True)
def wire_client(api: respx.MockRouter, trials_client: TrialsClient):
    """Point the server tools at a client backed by the mocked API."""
    server.set_client(trials_client)
    yield
    server.set_client(None)


def structured(result) -> dict:
    assert result.structured_content is not None
    return result.structured_content


async def test_list_tools_exposes_the_four_tools() -> None:
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools}
    assert names == {"search_trials", "get_trial", "eligibility_check", "recruiting_sites"}


async def test_search_trials_normalizes_results(api: respx.MockRouter) -> None:
    page = load_fixture("search_page.json")
    route = api.get("/studies").mock(return_value=httpx.Response(200, json=page))
    async with Client(server.mcp) as client:
        result = await client.call_tool("search_trials", {"condition": "diabetes"})
    data = structured(result)
    assert data["total_count"] == 137
    assert data["returned_count"] == 2
    assert data["next_page_token"] == page["nextPageToken"]
    first = data["trials"][0]
    assert first["nct_id"] == "NCT06001122"
    assert first["status"] == "RECRUITING"
    assert first["phases"] == ["PHASE2"]
    assert first["interventions"] == ["Metformin XR 1500 mg", "Placebo"]
    sent = route.calls[0].request.url.params
    assert sent["query.cond"] == "diabetes"
    assert sent["pageSize"] == "10"


async def test_search_trials_caps_page_size(api: respx.MockRouter) -> None:
    page = load_fixture("search_page.json")
    route = api.get("/studies").mock(return_value=httpx.Response(200, json=page))
    async with Client(server.mcp) as client:
        result = await client.call_tool("search_trials", {"page_size": 500})
    data = structured(result)
    assert data["page_size"] == server.MAX_PAGE_SIZE
    assert route.calls[0].request.url.params["pageSize"] == str(server.MAX_PAGE_SIZE)


async def test_search_trials_forwards_filters_and_token(api: respx.MockRouter) -> None:
    page = load_fixture("search_page.json")
    route = api.get("/studies").mock(return_value=httpx.Response(200, json=page))
    async with Client(server.mcp) as client:
        await client.call_tool(
            "search_trials",
            {
                "condition": "diabetes",
                "intervention": "metformin",
                "location": "Minnesota",
                "phases": ["Phase 2"],
                "statuses": ["Recruiting"],
                "page_token": "abc123",
            },
        )
    sent = route.calls[0].request.url.params
    assert sent["query.intr"] == "metformin"
    assert sent["query.locn"] == "Minnesota"
    assert sent["filter.overallStatus"] == "RECRUITING"
    assert sent["filter.advanced"] == "AREA[Phase]PHASE2"
    assert sent["pageToken"] == "abc123"


async def test_get_trial_returns_detail(api: respx.MockRouter) -> None:
    study = load_fixture("study_recruiting.json")
    api.get("/studies/NCT06001122").mock(return_value=httpx.Response(200, json=study))
    async with Client(server.mcp) as client:
        result = await client.call_tool("get_trial", {"nct_id": "nct06001122"})
    data = structured(result)
    assert data["nct_id"] == "NCT06001122"
    assert data["status"] == "RECRUITING"
    assert data["locations_count"] == 4
    assert data["recruiting_locations_count"] == 3
    assert data["eligibility"]["minimum_age"] == "18 Years"
    assert data["enrollment_count"] == 240


async def test_get_trial_unknown_nct_is_a_clean_tool_error(api: respx.MockRouter) -> None:
    api.get("/studies/NCT99999999").mock(return_value=httpx.Response(404, json={}))
    async with Client(server.mcp) as client:
        with pytest.raises(ToolError) as info:
            await client.call_tool("get_trial", {"nct_id": "NCT99999999"})
    message = str(info.value)
    assert "No study found for NCT number NCT99999999" in message
    assert "Traceback" not in message


async def test_upstream_500_surfaces_as_tool_error(api: respx.MockRouter) -> None:
    api.get("/studies/NCT06001122").mock(return_value=httpx.Response(500))
    async with Client(server.mcp) as client:
        with pytest.raises(ToolError) as info:
            await client.call_tool("get_trial", {"nct_id": "NCT06001122"})
    assert "not responding" in str(info.value)


async def test_eligibility_check_meets(api: respx.MockRouter) -> None:
    study = load_fixture("study_recruiting.json")
    api.get("/studies/NCT06001122").mock(return_value=httpx.Response(200, json=study))
    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "eligibility_check", {"nct_id": "NCT06001122", "age": 45, "sex": "female"}
        )
    data = structured(result)
    assert data["verdict"] == "meets"
    assert {c["criterion"] for c in data["checks"]} == {"age", "sex"}
    assert "Inclusion Criteria" in data["criteria_text"]


async def test_eligibility_check_does_not_meet(api: respx.MockRouter) -> None:
    study = load_fixture("study_female_only.json")
    api.get("/studies/NCT06003344").mock(return_value=httpx.Response(200, json=study))
    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "eligibility_check", {"nct_id": "NCT06003344", "age": 30, "sex": "male"}
        )
    data = structured(result)
    assert data["verdict"] == "does_not_meet"


async def test_recruiting_sites_filters_by_status_and_place(api: respx.MockRouter) -> None:
    study = load_fixture("study_recruiting.json")
    api.get("/studies/NCT06001122").mock(return_value=httpx.Response(200, json=study))
    async with Client(server.mcp) as client:
        all_sites = await client.call_tool("recruiting_sites", {"nct_id": "NCT06001122"})
        mn_sites = await client.call_tool(
            "recruiting_sites", {"nct_id": "NCT06001122", "state": "Minnesota"}
        )
    all_data = structured(all_sites)
    assert all_data["total_sites_listed"] == 4
    assert all_data["sites_returned"] == 3
    cities = {site["city"] for site in all_data["sites"]}
    assert cities == {"Rochester", "Chicago", "Minneapolis"}  # Phoenix is NOT_YET_RECRUITING
    rochester = next(s for s in all_data["sites"] if s["city"] == "Rochester")
    assert rochester["contact_name"] == "Jane Doe, MD"
    assert rochester["contact_email"] == "jdoe@example.org"
    mn_data = structured(mn_sites)
    assert mn_data["sites_returned"] == 2
    assert {s["city"] for s in mn_data["sites"]} == {"Rochester", "Minneapolis"}
    minneapolis = next(s for s in mn_data["sites"] if s["city"] == "Minneapolis")
    assert minneapolis["status"] == "RECRUITING"  # inherited from the study


async def test_recruiting_sites_for_non_recruiting_study(api: respx.MockRouter) -> None:
    study = load_fixture("study_female_only.json")
    api.get("/studies/NCT06003344").mock(return_value=httpx.Response(200, json=study))
    async with Client(server.mcp) as client:
        result = await client.call_tool("recruiting_sites", {"nct_id": "NCT06003344"})
    data = structured(result)
    assert data["study_status"] == "ACTIVE_NOT_RECRUITING"
    assert data["sites_returned"] == 0


# -- query building ---------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Phase 2", "PHASE2"),
        ("phase3", "PHASE3"),
        ("2", "PHASE2"),
        ("Phase 1", "PHASE1"),
        ("Early Phase 1", "EARLY_PHASE1"),
        ("N/A", "NA"),
        ("bogus", None),
    ],
)
def test_normalize_phase(raw: str, expected: str | None) -> None:
    assert normalize_phase(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Recruiting", "RECRUITING"),
        ("not yet recruiting", "NOT_YET_RECRUITING"),
        ("ACTIVE_NOT_RECRUITING", "ACTIVE_NOT_RECRUITING"),
    ],
)
def test_normalize_status(raw: str, expected: str) -> None:
    assert normalize_status(raw) == expected


def test_build_search_params_multiple_phases() -> None:
    params = build_search_params(
        condition=None,
        intervention=None,
        location=None,
        phases=["Phase 2", "Phase 3"],
        statuses=None,
        page_size=10,
        page_token=None,
    )
    assert params["filter.advanced"] == "AREA[Phase](PHASE2 OR PHASE3)"


def test_build_search_params_empty() -> None:
    params = build_search_params(
        condition=None,
        intervention=None,
        location=None,
        phases=None,
        statuses=None,
        page_size=25,
        page_token=None,
    )
    assert params == {"pageSize": "25"}
