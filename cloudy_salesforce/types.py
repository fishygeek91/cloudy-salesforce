"""Sentinel for omitted sObject fields (distinct from JSON null)."""

from __future__ import annotations


class UnsetType:
    """Singleton type for fields that should be omitted from DML payloads."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET = UnsetType()
