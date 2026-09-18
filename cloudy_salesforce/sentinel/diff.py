"""Pure diff between two Schema Sentinel snapshots. No Salesforce I/O."""

from __future__ import annotations

from typing import get_args

from .types import Change, ChangeKind, FieldSnapshot, Snapshot, SObjectSnapshot

#: Every v1 change kind. Used by ``--kinds`` validation.
CHANGE_KINDS: frozenset[ChangeKind] = frozenset(get_args(ChangeKind))


def _append_optional_bool(
    changes: list[Change],
    *,
    sobject: str,
    field: str,
    prefix: str,
    before: FieldSnapshot,
    after: FieldSnapshot,
    key: str,
    kind: ChangeKind,
) -> None:
    """Emit a bool-attribute change only when both snapshots recorded the key.

    Older v1 files omit ``createable`` / ``externalId`` / ``calculated`` /
    ``htmlFormatted``. Treating a missing key as a flip would false-positive
    every live diff against a pre-0.5.1 baseline.
    """
    if key not in before or key not in after:
        return
    old_value = before.get(key)
    new_value = after.get(key)
    if old_value == new_value:
        return
    changes.append(
        Change(
            kind=kind,
            sobject=sobject,
            field=field,
            before=old_value,
            after=new_value,
            summary=f"{prefix}: {key} {old_value} → {new_value}",
        )
    )


def _append_optional_str(
    changes: list[Change],
    *,
    sobject: str,
    field: str,
    prefix: str,
    before: FieldSnapshot,
    after: FieldSnapshot,
    key: str,
    kind: ChangeKind,
    label: str,
) -> None:
    """Emit a string-attribute change only when both snapshots recorded the key."""
    if key not in before or key not in after:
        return
    old_value = before.get(key)
    new_value = after.get(key)
    if old_value == new_value:
        return
    changes.append(
        Change(
            kind=kind,
            sobject=sobject,
            field=field,
            before=old_value,
            after=new_value,
            summary=f"{prefix}: {label} {old_value} → {new_value}",
        )
    )


def _field_changes(
    sobject: str, name: str, before: FieldSnapshot, after: FieldSnapshot
) -> list[Change]:
    changes: list[Change] = []
    prefix = f"{sobject}.{name}"

    old_type = before.get("type")
    new_type = after.get("type")
    if old_type != new_type:
        changes.append(
            Change(
                kind="type_changed",
                sobject=sobject,
                field=name,
                before=old_type,
                after=new_type,
                summary=f"{prefix}: type {old_type} → {new_type}",
            )
        )

    old_nillable = before.get("nillable")
    new_nillable = after.get("nillable")
    if old_nillable != new_nillable:
        word = "now required" if new_nillable is False else "now nillable"
        changes.append(
            Change(
                kind="nillable_changed",
                sobject=sobject,
                field=name,
                before=old_nillable,
                after=new_nillable,
                summary=f"{prefix}: {word} (nillable {old_nillable} → {new_nillable})",
            )
        )

    old_length = before.get("length")
    new_length = after.get("length")
    if old_length != new_length:
        changes.append(
            Change(
                kind="length_changed",
                sobject=sobject,
                field=name,
                before=old_length,
                after=new_length,
                summary=f"{prefix}: length {old_length} → {new_length}",
            )
        )

    old_precision = (before.get("precision"), before.get("scale"))
    new_precision = (after.get("precision"), after.get("scale"))
    if old_precision != new_precision:
        changes.append(
            Change(
                kind="precision_changed",
                sobject=sobject,
                field=name,
                before={"precision": old_precision[0], "scale": old_precision[1]},
                after={"precision": new_precision[0], "scale": new_precision[1]},
                summary=(
                    f"{prefix}: precision/scale {old_precision[0]},{old_precision[1]}"
                    f" → {new_precision[0]},{new_precision[1]}"
                ),
            )
        )

    old_updateable = before.get("updateable")
    new_updateable = after.get("updateable")
    if old_updateable != new_updateable:
        changes.append(
            Change(
                kind="updateable_changed",
                sobject=sobject,
                field=name,
                before=old_updateable,
                after=new_updateable,
                summary=(
                    f"{prefix}: updateable {old_updateable} → {new_updateable}"
                ),
            )
        )

    _append_optional_bool(
        changes,
        sobject=sobject,
        field=name,
        prefix=prefix,
        before=before,
        after=after,
        key="createable",
        kind="createable_changed",
    )
    _append_optional_bool(
        changes,
        sobject=sobject,
        field=name,
        prefix=prefix,
        before=before,
        after=after,
        key="externalId",
        kind="external_id_changed",
    )
    _append_optional_bool(
        changes,
        sobject=sobject,
        field=name,
        prefix=prefix,
        before=before,
        after=after,
        key="calculated",
        kind="calculated_changed",
    )
    _append_optional_bool(
        changes,
        sobject=sobject,
        field=name,
        prefix=prefix,
        before=before,
        after=after,
        key="htmlFormatted",
        kind="html_formatted_changed",
    )

    old_unique = before.get("unique")
    new_unique = after.get("unique")
    if old_unique != new_unique:
        changes.append(
            Change(
                kind="unique_changed",
                sobject=sobject,
                field=name,
                before=old_unique,
                after=new_unique,
                summary=f"{prefix}: unique {old_unique} → {new_unique}",
            )
        )

    old_refs = before.get("referenceTo")
    new_refs = after.get("referenceTo")
    if old_refs != new_refs:
        changes.append(
            Change(
                kind="reference_to_changed",
                sobject=sobject,
                field=name,
                before=old_refs,
                after=new_refs,
                summary=(
                    f"{prefix}: lookup target {old_refs or []} → {new_refs or []}"
                ),
            )
        )

    old_restricted = before.get("restrictedPicklist")
    new_restricted = after.get("restrictedPicklist")
    if old_restricted != new_restricted:
        word = (
            "picklist now restricted"
            if new_restricted
            else "picklist no longer restricted"
        )
        changes.append(
            Change(
                kind="restricted_picklist_changed",
                sobject=sobject,
                field=name,
                before=old_restricted,
                after=new_restricted,
                summary=f"{prefix}: {word}",
            )
        )

    _append_optional_str(
        changes,
        sobject=sobject,
        field=name,
        prefix=prefix,
        before=before,
        after=after,
        key="extraTypeInfo",
        kind="extra_type_info_changed",
        label="extraTypeInfo",
    )
    _append_optional_str(
        changes,
        sobject=sobject,
        field=name,
        prefix=prefix,
        before=before,
        after=after,
        key="relationshipName",
        kind="relationship_name_changed",
        label="relationshipName",
    )

    old_values = before.get("picklistValues")
    new_values = after.get("picklistValues")
    if old_values is not None or new_values is not None:
        old_set = set(old_values or [])
        new_set = set(new_values or [])
        for value in sorted(new_set - old_set):
            changes.append(
                Change(
                    kind="picklist_values_added",
                    sobject=sobject,
                    field=name,
                    before=None,
                    after=value,
                    summary=f'{prefix}: picklist value "{value}" added',
                )
            )
        for value in sorted(old_set - new_set):
            changes.append(
                Change(
                    kind="picklist_values_removed",
                    sobject=sobject,
                    field=name,
                    before=value,
                    after=None,
                    summary=f'{prefix}: picklist value "{value}" removed',
                )
            )

    return changes


def _sobject_changes(
    name: str, before: SObjectSnapshot, after: SObjectSnapshot
) -> list[Change]:
    changes: list[Change] = []

    old_fields = before.get("fields", {})
    new_fields = after.get("fields", {})
    for field_name in sorted(set(old_fields) | set(new_fields)):
        if field_name not in new_fields:
            changes.append(
                Change(
                    kind="field_removed",
                    sobject=name,
                    field=field_name,
                    before=old_fields[field_name],
                    after=None,
                    summary=f"{name}.{field_name}: field removed",
                )
            )
        elif field_name not in old_fields:
            changes.append(
                Change(
                    kind="field_added",
                    sobject=name,
                    field=field_name,
                    before=None,
                    after=new_fields[field_name],
                    summary=f"{name}.{field_name}: field added",
                )
            )
        else:
            changes.extend(
                _field_changes(
                    name, field_name, old_fields[field_name], new_fields[field_name]
                )
            )

    old_children = before.get("childRelationships", {})
    new_children = after.get("childRelationships", {})
    if old_children != new_children:
        changes.append(
            Change(
                kind="child_relationship_changed",
                sobject=name,
                field=None,
                before=old_children,
                after=new_children,
                summary=f"{name}: child relationships changed",
            )
        )

    return changes


def diff_snapshots(old: Snapshot, new: Snapshot) -> list[Change]:
    """Compare two snapshots. Pure function; deterministic order.

    Order: sObject name, then field name, then change kind (by emit order).
    """
    changes: list[Change] = []
    old_sobjects = old["sobjects"]
    new_sobjects = new["sobjects"]

    for name in sorted(set(old_sobjects) | set(new_sobjects)):
        if name not in new_sobjects:
            changes.append(
                Change(
                    kind="sobject_removed",
                    sobject=name,
                    field=None,
                    before=old_sobjects[name].get("label"),
                    after=None,
                    summary=f"{name}: sObject removed from snapshot set",
                )
            )
        elif name not in old_sobjects:
            changes.append(
                Change(
                    kind="sobject_added",
                    sobject=name,
                    field=None,
                    before=None,
                    after=new_sobjects[name].get("label"),
                    summary=f"{name}: sObject added to snapshot set",
                )
            )
        else:
            changes.extend(
                _sobject_changes(name, old_sobjects[name], new_sobjects[name])
            )

    return changes


def format_text(changes: list[Change]) -> str:
    """Human output: one summary line per change."""
    if not changes:
        return "No schema changes."
    return "\n".join(change.summary for change in changes)


def format_slack(changes: list[Change]) -> str:
    """Plain-text block suitable for pasting into Slack."""
    if not changes:
        return "No schema changes."
    lines = [f"*{len(changes)} Salesforce schema change(s) detected:*"]
    lines.extend(f"• {change.summary}" for change in changes)
    return "\n".join(lines)


def format_markdown(changes: list[Change]) -> str:
    """Markdown change set for a PR comment or README gist."""
    if not changes:
        return "No schema changes."
    lines = [
        f"## {len(changes)} Salesforce schema change(s)",
        "",
        "| Kind | Object | Field | Summary |",
        "| --- | --- | --- | --- |",
    ]
    for change in changes:
        field = change.field if change.field is not None else ""
        summary = change.summary.replace("|", "\\|")
        lines.append(
            f"| `{change.kind}` | `{change.sobject}` | `{field}` | {summary} |"
        )
    return "\n".join(lines)


def parse_kinds(raw: str) -> frozenset[ChangeKind]:
    """Parse a comma-separated ``--kinds`` list.

    Raises:
        ValueError: if any token is not a known ``ChangeKind``.
    """
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    if not tokens:
        raise ValueError("--kinds was empty")
    selected: set[ChangeKind] = set()
    unknown: list[str] = []
    for token in tokens:
        matched: ChangeKind | None = None
        for kind in CHANGE_KINDS:
            if kind == token:
                matched = kind
                break
        if matched is None:
            unknown.append(token)
        else:
            selected.add(matched)
    if unknown:
        known = ", ".join(sorted(CHANGE_KINDS))
        raise ValueError(
            f"unknown change kind(s): {', '.join(unknown)}. Choose from: {known}"
        )
    return frozenset(selected)


def filter_changes(
    changes: list[Change], kinds: frozenset[ChangeKind] | None
) -> list[Change]:
    """Keep only the requested kinds. ``None`` returns the full list."""
    if kinds is None:
        return changes
    return [change for change in changes if change.kind in kinds]
