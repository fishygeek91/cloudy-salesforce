"""Build Schema Sentinel snapshots from Salesforce describe metadata."""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

from cloudy_salesforce.client import SalesforceClient
from cloudy_salesforce.exceptions import SalesforceError
from cloudy_salesforce.sobjects import SObjects

from .types import (
    SNAPSHOT_SCHEMA_VERSION,
    FieldSnapshot,
    Snapshot,
    SObjectSnapshot,
)

logger = logging.getLogger(__name__)

#: Standard objects included by ``--all-custom`` alongside every ``__c`` object.
STANDARD_ALLOWLIST: tuple[str, ...] = (
    "Account",
    "Case",
    "Contact",
    "Event",
    "Lead",
    "Opportunity",
    "Task",
    "User",
)

_OPTIONAL_INT_KEYS = ("length", "precision", "scale")
_OPTIONAL_BOOL_KEYS = (
    "nillable",
    "unique",
    "updateable",
    "custom",
    "restrictedPicklist",
)


def project_field(field: dict) -> FieldSnapshot:
    """Project one raw describe field into the snapshot schema."""
    projected: FieldSnapshot = {
        "type": str(field.get("type", "")),
        "label": str(field.get("label", "")),
    }
    for key in _OPTIONAL_BOOL_KEYS:
        value = field.get(key)
        if isinstance(value, bool):
            projected[key] = value  # type: ignore[literal-required]
    for key in _OPTIONAL_INT_KEYS:
        value = field.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            projected[key] = value  # type: ignore[literal-required]
    if field.get("type") == "picklist" or field.get("type") == "multipicklist":
        raw_values = field.get("picklistValues") or []
        projected["picklistValues"] = sorted(
            str(item["value"])
            for item in raw_values
            if isinstance(item, dict) and item.get("active")
        )
    reference_to = field.get("referenceTo")
    if isinstance(reference_to, list) and reference_to:
        projected["referenceTo"] = sorted(str(ref) for ref in reference_to)
    return projected


def project_describe(describe: dict) -> SObjectSnapshot:
    """Project one raw sObject describe into the snapshot schema."""
    fields: dict[str, FieldSnapshot] = {}
    for field in describe.get("fields", []):
        name = field.get("name")
        if isinstance(name, str) and name:
            fields[name] = project_field(field)

    children: dict[str, str] = {}
    for child in describe.get("childRelationships", []):
        relationship_name = child.get("relationshipName")
        child_sobject = child.get("childSObject")
        if isinstance(relationship_name, str) and relationship_name:
            children[relationship_name] = str(child_sobject or "")

    return SObjectSnapshot(
        label=str(describe.get("label", "")),
        custom=bool(describe.get("custom", False)),
        fields=fields,
        childRelationships=children,
    )


def resolve_sobject_names(
    sobjects_client: SObjects,
    *,
    sobject_names: list[str] | None,
    all_custom: bool,
    config_path: str = ".cloudy_config",
) -> list[str]:
    """Decide which sObjects to snapshot.

    Priority: explicit ``sobject_names`` > ``--all-custom`` (every ``__c``
    plus a small standard allowlist) > the ``sobjects`` list in
    ``.cloudy_config``. Never defaults to every standard object.
    """
    if sobject_names:
        return sorted(set(sobject_names))

    if all_custom:
        described = sobjects_client.describe_global()
        names = {
            str(entry["name"])
            for entry in described
            if isinstance(entry, dict) and str(entry.get("name", "")).endswith("__c")
        }
        available = {
            str(entry["name"])
            for entry in described
            if isinstance(entry, dict) and "name" in entry
        }
        names.update(name for name in STANDARD_ALLOWLIST if name in available)
        if not names:
            raise ValueError("--all-custom found no custom objects in this org")
        return sorted(names)

    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"No sObjects given and {config_path} not found; "
            "use --sobjects or --all-custom"
        )
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)
    configured = config.get("sobjects")
    if not isinstance(configured, list) or not configured:
        raise ValueError(
            f"No 'sobjects' list in {config_path}; use --sobjects or --all-custom"
        )
    return sorted({str(name) for name in configured})


def _get_org_id(client: SalesforceClient) -> str:
    """Return the org id, or empty string when the query is not permitted."""
    try:
        response = client.request(
            "GET",
            f"/services/data/{client.api_version}/query",
            params={"q": "SELECT Id FROM Organization"},
        )
    except Exception:  # pragma: no cover - describe-only tokens
        return ""
    if isinstance(response, dict):
        records = response.get("records")
        if isinstance(records, list) and records:
            first = records[0]
            if isinstance(first, dict):
                return str(first.get("Id", ""))
    return ""


def _is_not_found(error: SalesforceError) -> bool:
    return error.status_code == 404 or error.error_code in (
        "NOT_FOUND",
        "INVALID_TYPE",
    )


def build_snapshot(
    client: SalesforceClient,
    sobject_names: list[str],
    *,
    alias: str,
    missing_ok: bool = False,
) -> Snapshot:
    """Describe each sObject and assemble the snapshot document.

    With ``missing_ok`` (the live-diff and config-list paths), an sObject the
    org no longer has — or the running user cannot see — is omitted from the
    snapshot so ``diff_snapshots`` reports it as ``sobject_removed`` instead of
    aborting the run. Without it (explicit ``--sobjects``), an unknown name
    fails fast so typos surface immediately.
    """
    sobjects_client = SObjects(sf_client=client)
    projected: dict[str, SObjectSnapshot] = {}
    for name in sorted(set(sobject_names)):
        try:
            describe = sobjects_client.describe_sobject(name)
        except SalesforceError as error:
            if missing_ok and _is_not_found(error):
                logger.warning(
                    "sObject %s not describable (%s); treating as absent",
                    name,
                    error.error_code or error.status_code,
                )
                continue
            raise
        projected[name] = project_describe(describe)

    captured_at = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    )
    return Snapshot(
        schema_sentinel=SNAPSHOT_SCHEMA_VERSION,
        captured_at=captured_at,
        alias=alias,
        org_id=_get_org_id(client),
        api_version=client.api_version,
        sobjects=projected,
    )


def write_snapshot(snapshot: Snapshot, out_path: str) -> Path:
    """Write a snapshot as stable JSON (UTF-8, sorted keys, indent 2)."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(snapshot, file, sort_keys=True, indent=2)
        file.write("\n")
    return path


def load_snapshot(path: str) -> Snapshot:
    """Load a snapshot JSON file, validating the schema version."""
    with Path(path).open("r", encoding="utf-8") as file:
        raw = json.load(file)
    if not isinstance(raw, dict) or raw.get("schema_sentinel") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(
            f"{path} is not a schema_sentinel v{SNAPSHOT_SCHEMA_VERSION} snapshot"
        )
    sobjects = raw.get("sobjects")
    if not isinstance(sobjects, dict):
        raise ValueError(f"{path} is missing the 'sobjects' mapping")
    return Snapshot(
        schema_sentinel=SNAPSHOT_SCHEMA_VERSION,
        captured_at=str(raw.get("captured_at", "")),
        alias=str(raw.get("alias", "")),
        org_id=str(raw.get("org_id", "")),
        api_version=str(raw.get("api_version", "")),
        sobjects=sobjects,
    )


def default_out_path(alias: str) -> str:
    """Default snapshot location for an alias."""
    return str(Path(".schema-sentinel") / f"{alias}.json")
