"""Snapshot projection tests with mocked describes — no Salesforce in CI."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from cloudy_salesforce.sentinel import (
    STANDARD_ALLOWLIST,
    build_snapshot,
    load_snapshot,
    project_describe,
    project_field,
    resolve_sobject_names,
    write_snapshot,
)

DESCRIBE_ACCOUNT = {
    "name": "Account",
    "label": "Account",
    "custom": False,
    "fields": [
        {
            "name": "Id",
            "type": "id",
            "label": "Account ID",
            "nillable": False,
            "unique": False,
            "updateable": False,
            "custom": False,
            "length": 18,
            "precision": 0,
            "scale": 0,
        },
        {
            "name": "Industry",
            "type": "picklist",
            "label": "Industry",
            "nillable": True,
            "unique": False,
            "updateable": True,
            "custom": False,
            "length": 40,
            "restrictedPicklist": False,
            "picklistValues": [
                {"value": "Technology", "active": True},
                {"value": "Banking", "active": True},
                {"value": "Retired", "active": False},
            ],
        },
        {
            "name": "OwnerId",
            "type": "reference",
            "label": "Owner ID",
            "nillable": False,
            "unique": False,
            "updateable": True,
            "custom": False,
            "referenceTo": ["User", "Group"],
        },
    ],
    "childRelationships": [
        {"relationshipName": "Opportunities", "childSObject": "Opportunity"},
        {"relationshipName": None, "childSObject": "Hidden"},
    ],
}


def test_project_field_picklist_active_sorted():
    projected = project_field(DESCRIBE_ACCOUNT["fields"][1])
    assert projected["type"] == "picklist"
    assert projected["picklistValues"] == ["Banking", "Technology"]
    assert projected["restrictedPicklist"] is False


def test_project_field_reference_sorted_and_zero_ints_dropped():
    projected = project_field(DESCRIBE_ACCOUNT["fields"][2])
    assert projected["referenceTo"] == ["Group", "User"]
    id_field = project_field(DESCRIBE_ACCOUNT["fields"][0])
    assert "precision" not in id_field
    assert "scale" not in id_field
    assert id_field["length"] == 18


def test_project_describe_projection():
    projected = project_describe(DESCRIBE_ACCOUNT)
    assert projected["label"] == "Account"
    assert projected["custom"] is False
    assert set(projected["fields"]) == {"Id", "Industry", "OwnerId"}
    assert projected["childRelationships"] == {"Opportunities": "Opportunity"}


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.api_version = "v61.0"

    def request(method: str, url: str, body=None, params=None):
        if url.endswith("/describe/"):
            return DESCRIBE_ACCOUNT
        if url.endswith("/query"):
            return {"records": [{"Id": "00D000000000001EXAMPLE"}], "done": True}
        raise AssertionError(f"unexpected url: {url}")

    client.request.side_effect = request
    return client


def test_build_and_write_snapshot_stable_json(tmp_path):
    client = _mock_client()
    snapshot = build_snapshot(client, ["Account"], alias="prod")
    assert snapshot["schema_sentinel"] == 1
    assert snapshot["alias"] == "prod"
    assert snapshot["api_version"] == "v61.0"
    assert snapshot["org_id"] == "00D000000000001EXAMPLE"
    assert set(snapshot["sobjects"]) == {"Account"}

    out = tmp_path / "snapshots" / "prod.json"
    write_snapshot(snapshot, str(out))
    text = out.read_text(encoding="utf-8")
    assert json.loads(text) == json.loads(
        json.dumps(snapshot, sort_keys=True, indent=2)
    )
    # sorted keys => stable diffs in git
    assert text.index('"alias"') < text.index('"api_version"') < text.index('"sobjects"')

    loaded = load_snapshot(str(out))
    assert loaded["sobjects"] == snapshot["sobjects"]


def test_load_snapshot_rejects_wrong_version(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema_sentinel": 99, "sobjects": {}}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_snapshot(str(path))


def test_resolve_sobject_names_explicit_wins():
    names = resolve_sobject_names(
        MagicMock(), sobject_names=["Contact", "Account", "Account"], all_custom=True
    )
    assert names == ["Account", "Contact"]


def test_resolve_sobject_names_all_custom_allowlist():
    sobjects_client = MagicMock()
    sobjects_client.describe_global.return_value = [
        {"name": "Widget__c"},
        {"name": "Gadget__c"},
        {"name": "Account"},
        {"name": "AccountContactRole"},
    ]
    names = resolve_sobject_names(
        sobjects_client, sobject_names=None, all_custom=True
    )
    assert names == ["Account", "Gadget__c", "Widget__c"]
    assert "AccountContactRole" not in names
    assert set(STANDARD_ALLOWLIST) >= {"Account", "Contact", "Opportunity"}


def test_resolve_sobject_names_from_config(tmp_path, monkeypatch):
    config = tmp_path / ".cloudy_config"
    config.write_text(
        json.dumps({"auth": {}, "sobjects": ["Opportunity", "Account"]}),
        encoding="utf-8",
    )
    names = resolve_sobject_names(
        MagicMock(),
        sobject_names=None,
        all_custom=False,
        config_path=str(config),
    )
    assert names == ["Account", "Opportunity"]


def test_resolve_sobject_names_missing_config_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_sobject_names(
            MagicMock(),
            sobject_names=None,
            all_custom=False,
            config_path=str(tmp_path / "missing"),
        )
