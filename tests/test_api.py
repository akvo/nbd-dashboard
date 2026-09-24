from __future__ import annotations

import httpx
import pytest
import streamlit as st

from src.api import (
    _normalize_api_url,
    _raise_for_status,
    extract_records,
    fetch_json,
    fetch_records,
    fetch_reference_records,
    load_api_config,
)


def test_normalize_api_url_removes_duplicate_api_prefix():
    assert _normalize_api_url("https://nbd.akvo.org/api") == "https://nbd.akvo.org"


def test_load_api_config_accepts_public_api_url_without_token(monkeypatch):
    monkeypatch.setattr(st, "secrets", {"NBD_API_URL": "https://nbd.akvo.org/api"})

    config = load_api_config()

    assert config["NBD_API_URL"] == "https://nbd.akvo.org"
    assert config["NBD_API_TOKEN"] is None
    assert config["configured"] is True


def test_fetch_reference_records_requests_the_full_list_without_pagination(monkeypatch):
    calls = []

    def fake_fetch_json(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return [{"id": "a", "name": "Narok", "level": 2}]

    monkeypatch.setattr("src.api.fetch_json", fake_fetch_json)

    records = fetch_reference_records("api/v1/reference/sub-counties", api_url="https://example.org")

    assert records == [{"id": "a", "name": "Narok", "level": 2}]
    assert len(calls) == 1
    assert calls[0][1]["params"] is None


def test_fetch_reference_records_unwraps_an_envelope(monkeypatch):
    monkeypatch.setattr("src.api.fetch_json", lambda endpoint, **kwargs: {"results": [{"id": "a"}]})

    assert fetch_reference_records("api/v1/reference/sub-counties") == [{"id": "a"}]


@pytest.mark.parametrize(
    ("status_code", "expected_message"),
    [
        (401, "Authentication failed"),
        (403, "forbidden"),
        (404, "was not found"),
        (429, "rate limit"),
        (503, "server error"),
    ],
)
def test_raise_for_status_reports_a_readable_message(status_code, expected_message):
    response = httpx.Response(status_code, request=httpx.Request("GET", "https://example.org"))

    with pytest.raises(RuntimeError, match=expected_message):
        _raise_for_status(response)


def test_raise_for_status_accepts_a_successful_response():
    response = httpx.Response(200, request=httpx.Request("GET", "https://example.org"))

    assert _raise_for_status(response) is None


def test_fetch_json_requires_a_configured_api_url(monkeypatch):
    monkeypatch.setattr(st, "secrets", {})
    monkeypatch.delenv("NBD_API_URL", raising=False)

    with pytest.raises(RuntimeError, match="configuration is missing"):
        fetch_json("api/v1/submissions")


def test_extract_records_reads_the_common_envelopes():
    assert extract_records([{"id": 1}]) == [{"id": 1}]
    assert extract_records({"results": [{"id": 1}]}) == [{"id": 1}]
    assert extract_records({"data": {"items": [{"id": 1}]}}) == [{"id": 1}]
    assert extract_records("unexpected") == []
    assert extract_records({"unexpected": 1}) == []


def test_fetch_records_stops_on_a_short_page(monkeypatch):
    pages = {1: [{"id": index} for index in range(100)], 2: [{"id": 100}]}

    def fake_fetch_json(endpoint, *, params, **kwargs):
        return pages.get(params["page"], [])

    monkeypatch.setattr("src.api.fetch_json", fake_fetch_json)

    records = fetch_records("api/v1/submissions", api_url="https://example.org")

    assert len(records) == 101


def test_fetch_records_stops_on_an_empty_page(monkeypatch):
    monkeypatch.setattr("src.api.fetch_json", lambda endpoint, **kwargs: [])

    assert fetch_records("api/v1/submissions", api_url="https://example.org") == []


def test_fetch_records_requires_a_configured_api_url(monkeypatch):
    monkeypatch.setattr(st, "secrets", {})
    monkeypatch.delenv("NBD_API_URL", raising=False)

    with pytest.raises(RuntimeError, match="configuration is missing"):
        fetch_records("api/v1/submissions")
