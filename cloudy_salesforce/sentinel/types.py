"""Typed schema for Schema Sentinel snapshots and change sets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

SNAPSHOT_SCHEMA_VERSION = 1


class FieldSnapshot(TypedDict, total=False):
    """Projection of one describe field: only what breaks integrations."""

    type: str
    label: str
    nillable: bool
    unique: bool
    updateable: bool
    custom: bool
    length: int
    precision: int
    scale: int
    restrictedPicklist: bool
    picklistValues: list[str]
    referenceTo: list[str]


class SObjectSnapshot(TypedDict):
    """Projection of one sObject describe."""

    label: str
    custom: bool
    fields: dict[str, FieldSnapshot]
    childRelationships: dict[str, str]


class Snapshot(TypedDict):
    """Snapshot document, v1. Written as sorted-key, indent-2 JSON."""

    schema_sentinel: int
    captured_at: str
    alias: str
    org_id: str
    api_version: str
    sobjects: dict[str, SObjectSnapshot]


ChangeKind = Literal[
    "sobject_added",
    "sobject_removed",
    "field_added",
    "field_removed",
    "type_changed",
    "nillable_changed",
    "length_changed",
    "precision_changed",
    "updateable_changed",
    "picklist_values_added",
    "picklist_values_removed",
    "child_relationship_changed",
]


@dataclass
class Change:
    """One schema change between two snapshots."""

    kind: ChangeKind
    sobject: str
    field: str | None
    before: object
    after: object
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "sobject": self.sobject,
            "field": self.field,
            "before": self.before,
            "after": self.after,
            "summary": self.summary,
        }
