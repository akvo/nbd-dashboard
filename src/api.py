from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st


DEFAULT_TIMEOUT = 30.0


def _normalize_api_url(api_url: str | None) -> str | None:
    if not api_url:
        return api_url

    normalized = api_url.rstrip('/')
    if normalized.endswith('/api'):
        return normalized[:-4] or normalized

    return normalized


def load_api_config() -> dict[str, Any]:
    """Load API configuration from Streamlit secrets or environment variables."""
    secrets = getattr(st, "secrets", {})

    api_url = secrets.get("NBD_API_URL") or os.getenv("NBD_API_URL")
    api_token = secrets.get("NBD_API_TOKEN") or os.getenv("NBD_API_TOKEN")

    normalized_api_url = _normalize_api_url(api_url)

    return {
        "NBD_API_URL": normalized_api_url,
        "NBD_API_TOKEN": api_token,
        "configured": bool(normalized_api_url),
        "token_configured": bool(api_token),
    }


def _build_headers(api_token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    return headers


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise RuntimeError("Authentication failed while connecting to the NBD API.")

    if response.status_code == 403:
        raise RuntimeError("Access to the NBD API was forbidden.")

    if response.status_code == 404:
        raise RuntimeError("The requested NBD API endpoint was not found.")

    if response.status_code == 429:
        raise RuntimeError("The NBD API rate limit was exceeded. Please retry later.")

    if response.status_code >= 500:
        raise RuntimeError("The NBD API returned a server error.")

    response.raise_for_status()


def fetch_json(
    endpoint: str,
    *,
    params: dict[str, Any] | None = None,
    api_url: str | None = None,
    api_token: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """Fetch and decode JSON from the NBD API."""
    config = load_api_config()

    if api_url is None:
        api_url = config["NBD_API_URL"]

    if api_token is None:
        api_token = config["NBD_API_TOKEN"]

    if not api_url:
        raise RuntimeError("NBD API configuration is missing. Add NBD_API_URL.")

    normalized_api_url = _normalize_api_url(api_url)
    url = f"{normalized_api_url.rstrip('/')}/{endpoint.lstrip('/')}"

    with httpx.Client() as client:
        response = client.get(
            url,
            params=params,
            headers=_build_headers(api_token),
            timeout=timeout,
        )

    _raise_for_status(response)

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("The NBD API returned malformed JSON.") from exc


def extract_records(payload: Any) -> list[dict[str, Any]]:
    """Extract a list of record dictionaries from a typical API envelope."""
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    for key in ("results", "items", "data", "records", "rows"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    if isinstance(payload.get("data"), dict):
        for key in ("results", "items", "records", "rows"):
            value = payload["data"].get(key)
            if isinstance(value, list):
                return value

    return []


def fetch_records(
    endpoint: str,
    *,
    params: dict[str, Any] | None = None,
    api_url: str | None = None,
    api_token: str | None = None,
    page_size: int = 100,
    max_pages: int = 10,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Fetch paginated or unpaginated records from the NBD API.

    The function is intentionally tolerant of common API response envelopes to
    support the Phase 1 contract discovery work.
    """
    config = load_api_config()

    if api_url is None:
        api_url = config["NBD_API_URL"]

    if api_token is None:
        api_token = config["NBD_API_TOKEN"]

    if not api_url:
        raise RuntimeError("NBD API configuration is missing. Add NBD_API_URL.")

    all_records: list[dict[str, Any]] = []
    current_params = dict(params or {})

    for page in range(1, max_pages + 1):
        request_params = dict(current_params)
        if "page" not in request_params:
            request_params["page"] = page
        if "page_size" not in request_params and "limit" not in request_params:
            request_params["page_size"] = page_size

        payload = fetch_json(
            endpoint,
            params=request_params,
            api_url=api_url,
            api_token=api_token,
            timeout=timeout,
        )

        records = extract_records(payload)

        if not records:
            break

        all_records.extend(records)

        if len(records) < request_params.get("page_size", page_size):
            break

    return all_records


def fetch_reference_records(
    endpoint: str,
    *,
    params: dict[str, Any] | None = None,
    api_url: str | None = None,
    api_token: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Fetch a reference list in a single request.

    The reference endpoints return the complete collection and ignore the
    pagination parameters that :func:`fetch_records` adds, which would
    otherwise make the same page be fetched repeatedly.
    """
    payload = fetch_json(
        endpoint,
        params=params,
        api_url=api_url,
        api_token=api_token,
        timeout=timeout,
    )

    return extract_records(payload)
