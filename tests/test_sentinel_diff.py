"""Pure-diff tests: no network, fixture-driven."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from cloudy_salesforce.sentinel import (
    Snapshot,
    diff_snapshots,
    format_slack,
    format_text,
    load_snapshot,
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
