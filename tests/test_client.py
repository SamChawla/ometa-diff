"""Tests for OMVersionClient — version parsing and HTTP error mapping."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from ometa_diff.client import OMVersionClient, _version_sort_key
from ometa_diff.exceptions import OMAPIError, OMAuthError, OMConnectionError, OMNotFoundError

# ---------------------------------------------------------------------------
# _version_sort_key unit tests
# ---------------------------------------------------------------------------


class TestVersionSortKey:
    def test_simple_float_style(self) -> None:
        assert _version_sort_key("0.1") == (0, 1)
        assert _version_sort_key("1.2") == (1, 2)
        assert _version_sort_key("10.3") == (10, 3)

    def test_three_part_semver(self) -> None:
        assert _version_sort_key("1.2.3") == (1, 2, 3)

    def test_large_minor_version(self) -> None:
        assert _version_sort_key("1.10") > _version_sort_key("1.9")

    def test_non_numeric_falls_back(self) -> None:
        assert _version_sort_key("unknown") == (0,)
        assert _version_sort_key("2026-04-22") == (0,)
        assert _version_sort_key("") == (0,)


# ---------------------------------------------------------------------------
# list_versions parsing tests (via mocked _get)
# ---------------------------------------------------------------------------


def _make_client() -> OMVersionClient:
    return OMVersionClient(host="http://localhost:8585/api", token="test")


def _ver(versions: list[Any]) -> dict[str, Any]:
    return {"versions": versions}


class TestListVersionsParsing:
    def test_versions_as_dicts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _make_client()
        monkeypatch.setattr(
            client, "_get", lambda *a, **kw: _ver([{"version": 0.1}, {"version": 0.2}])
        )
        assert client.list_versions("table", "id-1") == ["0.1", "0.2"]

    def test_versions_as_json_strings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _make_client()
        snaps = [json.dumps({"version": 0.1}), json.dumps({"version": 0.3})]
        monkeypatch.setattr(client, "_get", lambda *a, **kw: _ver(snaps))
        assert client.list_versions("table", "id-1") == ["0.1", "0.3"]

    def test_versions_as_raw_numbers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _make_client()
        monkeypatch.setattr(client, "_get", lambda *a, **kw: _ver([0.1, 1.0, 0.5]))
        result = client.list_versions("table", "id-1")
        assert result == sorted(result, key=_version_sort_key)

    def test_large_minor_sorts_correctly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """'1.10' must sort after '1.9', not before — the float-cast bug."""
        client = _make_client()
        monkeypatch.setattr(
            client,
            "_get",
            lambda *a, **kw: _ver([{"version": "1.9"}, {"version": "1.10"}, {"version": "1.2"}]),
        )
        assert client.list_versions("table", "id-1") == ["1.2", "1.9", "1.10"]

    def test_non_numeric_preserved_not_dropped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _make_client()
        monkeypatch.setattr(
            client,
            "_get",
            lambda *a, **kw: _ver([{"version": "0.1"}, {"version": "unknown"}, {"version": "0.2"}]),
        )
        result = client.list_versions("table", "id-1")
        assert "0.1" in result
        assert "0.2" in result
        assert "unknown" in result

    def test_empty_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _make_client()
        monkeypatch.setattr(client, "_get", lambda *a, **kw: {"versions": []})
        assert client.list_versions("table", "id-1") == []

    def test_invalid_json_string_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _make_client()
        monkeypatch.setattr(
            client,
            "_get",
            lambda *a, **kw: _ver(["not-json{{{", json.dumps({"version": 0.2})]),
        )
        assert client.list_versions("table", "id-1") == ["0.2"]


# ---------------------------------------------------------------------------
# HTTP error mapping tests
# ---------------------------------------------------------------------------


class TestHttpErrorMapping:
    def test_401_raises_auth_error(self) -> None:
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.is_success = False
        with patch.object(client._http, "get", return_value=mock_resp):
            with pytest.raises(OMAuthError):
                client._get("/v1/tables")

    def test_404_raises_not_found(self) -> None:
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.is_success = False
        with patch.object(client._http, "get", return_value=mock_resp):
            with pytest.raises(OMNotFoundError):
                client._get("/v1/tables/missing")

    def test_500_raises_api_error(self) -> None:
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.is_success = False
        with patch.object(client._http, "get", return_value=mock_resp):
            with pytest.raises(OMAPIError):
                client._get("/v1/tables")

    def test_transport_error_raises_connection_error(self) -> None:
        client = _make_client()
        with patch.object(client._http, "get", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(OMConnectionError):
                client._get("/v1/tables")

    def test_timeout_raises_connection_error(self) -> None:
        client = _make_client()
        with patch.object(client._http, "get", side_effect=httpx.ReadTimeout("timed out")):
            with pytest.raises(OMConnectionError):
                client._get("/v1/tables")
