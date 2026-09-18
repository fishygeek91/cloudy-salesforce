"""Pure-diff tests: no network, fixture-driven."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from cloudy_salesforce.sentinel import (
    Change,
    Snapshot,
    diff_snapshots,
    filter_changes,
    format_markdown,
    format_slack,
    format_text,
    load_snapshot,
    parse_kinds,
    render_html_report,
)

FIXTURES = Path(__file__).parent.parent / "examples" / "snapshots"


def _load(name: str) -> Snapshot:
    return load_snapshot(str(FIXTURES / name))


def test_diff_identical_snapshots_is_empty():
    base = _load("base.json")
    assert diff_snapshots(base, base) == []
    assert format_text([]) == "No schema changes."


def test_diff_fixture_changes_exact():
    old = _load("base.json")
    new = _load("drifted.json")
    changes = diff_snapshots(old, new)

    assert [(c.kind, c.sobject, c.field) for c in changes] == [
        ("picklist_values_removed", "Account", "Industry"),
        ("type_changed", "Opportunity", "Amount"),
        ("length_changed", "Opportunity", "NextStep"),
        ("field_removed", "Opportunity", "Tracking_Code__c"),
    ]

    summaries = [c.summary for c in changes]
    assert 'Account.Industry: picklist value "Banking" removed' in summaries
    assert "Opportunity.NextStep: length 255 → 80" in summaries
    assert "Opportunity.Amount: type currency → double" in summaries
    assert "Opportunity.Tracking_Code__c: field removed" in summaries


def test_diff_sobject_added_and_removed():
    old = _load("base.json")
    new = copy.deepcopy(old)
    del new["sobjects"]["Opportunity"]
    new["sobjects"]["Lead"] = {
        "label": "Lead",
        "custom": False,
        "fields": {},
        "childRelationships": {},
    }
    changes = diff_snapshots(old, new)
    assert [(c.kind, c.sobject) for c in changes] == [
        ("sobject_added", "Lead"),
        ("sobject_removed", "Opportunity"),
    ]


def test_diff_nillable_and_updateable_and_children():
    old = _load("base.json")
    new = copy.deepcopy(old)
    new["sobjects"]["Account"]["fields"]["Industry"]["nillable"] = False
    new["sobjects"]["Account"]["fields"]["Name"]["updateable"] = False
    new["sobjects"]["Account"]["childRelationships"] = {}
    changes = diff_snapshots(old, new)
    kinds = {(c.kind, c.field) for c in changes}
    assert ("nillable_changed", "Industry") in kinds
    assert ("updateable_changed", "Name") in kinds
    assert ("child_relationship_changed", None) in kinds


def test_diff_precision_changed():
    old = _load("base.json")
    new = copy.deepcopy(old)
    new["sobjects"]["Opportunity"]["fields"]["Amount"]["scale"] = 0
    changes = diff_snapshots(old, new)
    assert [(c.kind, c.field) for c in changes] == [("precision_changed", "Amount")]


def test_picklist_add_and_remove_not_rename():
    old = _load("base.json")
    new = copy.deepcopy(old)
    new["sobjects"]["Account"]["fields"]["Industry"]["picklistValues"] = [
        "Agriculture",
        "Banking & Finance",
        "Technology",
    ]
    changes = diff_snapshots(old, new)
    assert [(c.kind, c.after or c.before) for c in changes] == [
        ("picklist_values_added", "Banking & Finance"),
        ("picklist_values_removed", "Banking"),
    ]


def test_change_to_dict_round_trips_through_json():
    changes = diff_snapshots(_load("base.json"), _load("drifted.json"))
    payload = json.dumps([c.to_dict() for c in changes])
    decoded = json.loads(payload)
    assert decoded[0]["kind"] == "picklist_values_removed"
    assert decoded[0]["sobject"] == "Account"


def test_format_slack_lists_changes():
    changes = diff_snapshots(_load("base.json"), _load("drifted.json"))
    block = format_slack(changes)
    assert block.startswith("*4 Salesforce schema change(s) detected:*")
    assert "• Opportunity.NextStep: length 255 → 80" in block


def test_format_markdown_table():
    changes = diff_snapshots(_load("base.json"), _load("drifted.json"))
    table = format_markdown(changes)
    assert table.startswith("## 4 Salesforce schema change(s)")
    assert "| `length_changed` | `Opportunity` | `NextStep` |" in table
    assert format_markdown([]) == "No schema changes."


def test_parse_kinds_and_filter():
    kinds = parse_kinds("length_changed, field_removed")
    assert kinds == frozenset({"length_changed", "field_removed"})
    changes = diff_snapshots(_load("base.json"), _load("drifted.json"))
    filtered = filter_changes(changes, kinds)
    assert [(c.kind, c.field) for c in filtered] == [
        ("length_changed", "NextStep"),
        ("field_removed", "Tracking_Code__c"),
    ]
    assert filter_changes(changes, None) == changes


def test_parse_kinds_rejects_unknown():
    try:
        parse_kinds("not_a_kind")
    except ValueError as error:
        assert "not_a_kind" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_optional_bools_ignored_when_absent_on_one_side():
    old = _load("base.json")
    new = copy.deepcopy(old)
    new["sobjects"]["Account"]["fields"]["Name"]["createable"] = False
    assert diff_snapshots(old, new) == []


def test_optional_bools_emit_when_both_sides_present():
    old = _load("base.json")
    new = copy.deepcopy(old)
    name = new["sobjects"]["Account"]["fields"]["Name"]
    name["createable"] = False
    name["externalId"] = True
    name["calculated"] = True
    name["htmlFormatted"] = True
    old["sobjects"]["Account"]["fields"]["Name"]["createable"] = True
    old["sobjects"]["Account"]["fields"]["Name"]["externalId"] = False
    old["sobjects"]["Account"]["fields"]["Name"]["calculated"] = False
    old["sobjects"]["Account"]["fields"]["Name"]["htmlFormatted"] = False
    kinds = {c.kind for c in diff_snapshots(old, new)}
    assert kinds == {
        "createable_changed",
        "external_id_changed",
        "calculated_changed",
        "html_formatted_changed",
    }


def test_optional_strings_emit_when_both_sides_present():
    old = _load("base.json")
    new = copy.deepcopy(old)
    new["sobjects"]["Account"]["fields"]["Name"]["extraTypeInfo"] = "personname"
    new["sobjects"]["Account"]["fields"]["Name"]["relationshipName"] = "Renamed"
    old["sobjects"]["Account"]["fields"]["Name"]["extraTypeInfo"] = "plain"
    old["sobjects"]["Account"]["fields"]["Name"]["relationshipName"] = "Name"
    kinds = {c.kind: c for c in diff_snapshots(old, new)}
    assert kinds["extra_type_info_changed"].after == "personname"
    assert kinds["relationship_name_changed"].after == "Renamed"


def test_html_report_escapes_and_lists_changes():
    changes = diff_snapshots(_load("base.json"), _load("drifted.json"))
    page = render_html_report(
        changes, old_label="base.json", new_label="drifted.json"
    )
    assert "<!DOCTYPE html>" in page
    assert "Opportunity.NextStep: length 255 → 80" in page
    assert "base.json" in page
    empty = render_html_report([], old_label="a", new_label="b")
    assert "No schema changes" in empty


def test_html_report_escapes_markup():
    change = Change(
        kind="field_added",
        sobject="Account",
        field="<script>",
        before=None,
        after="<img>",
        summary='Account.<script>: field added',
    )
    page = render_html_report(
        [change], old_label="<old>", new_label="<new>"
    )
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "&lt;old&gt;" in page


def test_diff_unique_reference_and_restricted_changes():
    old = _load("base.json")
    new = copy.deepcopy(old)
    account_fields = new["sobjects"]["Account"]["fields"]
    account_fields["Name"]["unique"] = True
    account_fields["Industry"]["restrictedPicklist"] = True
    account_fields["OwnerRef"] = {"type": "reference", "referenceTo": ["User"]}
    old["sobjects"]["Account"]["fields"]["OwnerRef"] = {
        "type": "reference",
        "referenceTo": ["Group", "User"],
    }
    changes = diff_snapshots(old, new)
    by_kind = {c.kind: c for c in changes}
    assert by_kind["unique_changed"].field == "Name"
    assert by_kind["restricted_picklist_changed"].field == "Industry"
    assert "picklist now restricted" in by_kind["restricted_picklist_changed"].summary
    ref = by_kind["reference_to_changed"]
    assert ref.field == "OwnerRef"
    assert ref.before == ["Group", "User"]
    assert ref.after == ["User"]
