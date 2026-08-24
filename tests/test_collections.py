from __future__ import annotations

import copy
import importlib
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone

import pytest

from cloudy_salesforce.collections import DmlResult, delete, insert, update
from cloudy_salesforce.collections.crud_operations import (
    add_attributes,
    batch_records,
    build_payload,
    get_id_list,
)
from cloudy_salesforce.collections.serialize import serialize_record
from cloudy_salesforce.sobjects import sobject
from cloudy_salesforce.types import UNSET, UnsetType


class FakeClient:
    api_version = "v61.0"

    def __init__(self, responses: list | None = None):
        self._responses = list(responses or [])
        self.calls: list[dict] = []

    def request(self, method, url=None, body=None, params=None):
        self.calls.append(
            {"method": method, "url": url, "body": body, "params": params}
        )
        if not self._responses:
            raise AssertionError("Unexpected extra request")
        return self._responses.pop(0)


def _props(records, all_or_none=True):
    return {
        "client": FakeClient(),
        "object_type": "Account",
        "records": records,
        "all_or_none": all_or_none,
        "batch_size": 200,
    }


@sobject()
@dataclass
class Account:
    Id: str | None | UnsetType = UNSET
    Name: str | None | UnsetType = UNSET
    Industry: str | None | UnsetType = UNSET
    Description: str | None | UnsetType = UNSET


@sobject()
@dataclass
class Opportunity:
    Id: str | None | UnsetType = UNSET
    Name: str | None | UnsetType = UNSET
    AccountId: str | None | UnsetType = UNSET
    Account: Account | None | UnsetType = UNSET


@sobject()
@dataclass
class Event:
    Id: str | None | UnsetType = UNSET
    Subject: str | None | UnsetType = UNSET
    ActivityDate: date | None | UnsetType = UNSET
    StartDateTime: datetime | None | UnsetType = UNSET


def _success_response(record_id: str, *, created: bool | None = None) -> list[dict]:
    item: dict = {"id": record_id, "success": True, "errors": []}
    if created is not None:
        item["created"] = created
    return [item]


def test_batch_records_splits_into_expected_batches():
    records = [{"Id": str(i)} for i in range(5)]
    batches = batch_records(records, 2)
    assert len(batches) == 3
    assert len(batches[0]) == 2
    assert len(batches[1]) == 2
    assert len(batches[2]) == 1


def test_add_attributes_does_not_mutate_original():
    original = [{"Name": "Acme"}]
    result = add_attributes(original, "Account")

    assert "attributes" not in original[0]
    assert result[0]["attributes"] == {"type": "Account"}
    assert result[0]["Name"] == "Acme"


def test_build_payload_insert():
    records = [{"Name": "Acme"}, {"Name": "Globex"}]
    url, body, params = build_payload("insert", _props(records))

    assert url == "/services/data/v61.0/composite/sobjects/"
    assert params is None
    assert body["allOrNone"] is True
    assert len(body["records"]) == 2
    assert all(r["attributes"]["type"] == "Account" for r in body["records"])


def test_build_payload_delete():
    records = [{"Id": "001"}, {"Id": "002"}]
    url, body, params = build_payload("delete", _props(records, all_or_none=False))

    assert url == "/services/data/v61.0/composite/sobjects"
    assert "?" not in url
    assert body is None
    assert params["ids"] == "001,002"
    assert params["allOrNone"] == "false"


def test_get_id_list_accepts_id_or_lowercase_id():
    assert get_id_list([{"Id": "001"}, {"id": "002"}]) == ["001", "002"]


def test_get_id_list_raises_when_missing():
    with pytest.raises(ValueError, match="does not contain an Id/id field"):
        get_id_list([{"Name": "no id here"}])


def test_insert_dataclass_serializes_to_composite_body():
    fake = FakeClient([_success_response("001NEW", created=True)])
    record = Account(Name="Acme", Industry="Technology", Description=None)

    results = insert(record, client=fake)

    call = fake.calls[0]
    assert call["method"] == "POST"
    body_record = call["body"]["records"][0]
    assert body_record["attributes"]["type"] == "Account"
    assert body_record["Name"] == "Acme"
    assert body_record["Industry"] == "Technology"
    assert "Description" in body_record
    assert body_record["Description"] is None
    assert len(results) == 1
    assert isinstance(results[0], DmlResult)
    assert results[0].id == "001NEW"
    assert results[0].success is True
    assert results[0].created is True
    assert results[0].record == {
        "Name": "Acme",
        "Industry": "Technology",
        "Description": None,
    }


def test_insert_omits_unset_fields():
    fake = FakeClient([_success_response("001NEW", created=True)])
    record = Account(Name="Acme", Industry="Technology")

    insert(record, client=fake)

    body_record = fake.calls[0]["body"]["records"][0]
    assert "Description" not in body_record
    assert "Id" not in body_record


def test_insert_list_of_dataclasses():
    fake = FakeClient(
        [
            [
                {"id": "001A", "success": True, "errors": [], "created": True},
                {"id": "001B", "success": True, "errors": [], "created": True},
            ]
        ]
    )
    records = [Account(Name="Acme"), Account(Name="Globex")]

    results = insert(records, client=fake)

    body_records = fake.calls[0]["body"]["records"]
    assert len(body_records) == 2
    assert body_records[0]["Name"] == "Acme"
    assert body_records[1]["Name"] == "Globex"
    assert len(results) == 2
    assert results[0].id == "001A"
    assert results[1].id == "001B"


def test_insert_dict_api_still_works():
    fake = FakeClient([_success_response("001DICT", created=True)])

    results = insert("Account", [{"Name": "Acme"}], client=fake)

    body_record = fake.calls[0]["body"]["records"][0]
    assert body_record["attributes"]["type"] == "Account"
    assert body_record["Name"] == "Acme"
    assert results[0].success is True
    assert results[0].record == {"Name": "Acme"}


def test_update_from_dataclass():
    fake = FakeClient([_success_response("001UPD")])
    record = Account(Id="001UPD", Name="Acme Inc")

    results = update(record, client=fake)

    call = fake.calls[0]
    assert call["method"] == "PATCH"
    body_record = call["body"]["records"][0]
    assert body_record["Id"] == "001UPD"
    assert body_record["Name"] == "Acme Inc"
    assert results[0].id == "001UPD"
    assert results[0].success is True


def test_update_sends_none_as_json_null():
    fake = FakeClient([_success_response("001UPD")])
    record = Account(Id="001UPD", Industry=None)

    update(record, client=fake)

    body_record = fake.calls[0]["body"]["records"][0]
    assert "Industry" in body_record
    assert body_record["Industry"] is None


def test_delete_from_dataclass():
    fake = FakeClient([_success_response("001DEL")])
    record = Account(Id="001DEL")

    results = delete(record, client=fake)

    call = fake.calls[0]
    assert call["method"] == "DELETE"
    assert call["params"]["ids"] == "001DEL"
    assert results[0].id == "001DEL"
    assert results[0].success is True


def test_serialize_skips_nested_account_on_opportunity():
    opp = Opportunity(
        Name="Big Deal",
        AccountId="001PARENT",
        Account=Account(Id="001PARENT", Name="Parent Co"),
    )

    serialized = serialize_record(opp)

    assert serialized == {"Name": "Big Deal", "AccountId": "001PARENT"}
    assert "Account" not in serialized


def test_serialize_omits_unset_includes_none():
    account_unset = Account(Name="Acme")
    account_none = Account(Name="Acme", Description=None)

    assert serialize_record(account_unset) == {"Name": "Acme"}
    assert serialize_record(account_none) == {"Name": "Acme", "Description": None}


@sobject("OldAccount")
@dataclass
class OldAccount:
    Id: str | None = None
    Name: str | None = None
    Industry: str | None = None


def test_serialize_pre_unset_dataclass_omits_none():
    serialized = serialize_record(OldAccount(Id="001", Name="x"))
    assert serialized == {"Id": "001", "Name": "x"}
    assert "Industry" not in serialized


def test_serialize_legacy_unresolved_sibling_does_not_raise(tmp_path):
    """Pre-UNSET codegen imported TYPE_CHECKING siblings only.

    Importing one module standalone leaves an unresolvable forward ref.
    serialize_record must still omit None instead of raising NameError.
    """
    pkg_dir = tmp_path / "legacy_sobjects"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "Legacy.py").write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from typing import TYPE_CHECKING\n"
        "from cloudy_salesforce.sobjects import sobject\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from .Missing import Missing\n"
        "\n"
        "@sobject()\n"
        "@dataclass\n"
        "class Legacy:\n"
        "    Id: str | None = None\n"
        "    Name: str | None = None\n"
        "    Related: Missing | None = None\n"
    )
    sys.path.insert(0, str(tmp_path))
    try:
        mod = importlib.import_module("legacy_sobjects.Legacy")
        serialized = serialize_record(mod.Legacy(Id="1", Name="n"))
        assert serialized == {"Id": "1", "Name": "n"}
        assert "Related" not in serialized
    finally:
        sys.path.remove(str(tmp_path))
        for name in list(sys.modules):
            if name == "legacy_sobjects" or name.startswith("legacy_sobjects."):
                del sys.modules[name]


def test_serialize_skips_none_relationship():
    from cloudy_salesforce.sobjects.sobject import parse_record

    opp = parse_record(
        Opportunity,
        {"Id": "006", "Name": "n", "Account": None},
    )
    serialized = serialize_record(opp)
    assert serialized == {"Id": "006", "Name": "n"}
    assert "Account" not in serialized


def test_serialize_deepcopy_keeps_unset_identity():
    serialized = serialize_record(copy.deepcopy(Account(Id="001")))
    assert serialized == {"Id": "001"}


def test_serialize_date_and_datetime_fields():
    event = Event(
        Subject="Kickoff",
        ActivityDate=date(2024, 1, 15),
        StartDateTime=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    serialized = serialize_record(event)

    assert serialized["ActivityDate"] == "2024-01-15"
    assert serialized["StartDateTime"] == "2024-01-15T12:00:00.000+0000"


def test_insert_returns_dml_result_list_from_fake_response():
    fake = FakeClient(
        [
            [
                {
                    "id": "001XYZ",
                    "success": True,
                    "errors": [],
                    "created": True,
                }
            ]
        ]
    )

    results = insert(Account(Name="Acme"), client=fake)

    assert len(results) == 1
    result = results[0]
    assert isinstance(result, DmlResult)
    assert result.id == "001XYZ"
    assert result.success is True
    assert result.errors == []
    assert result.created is True
    assert result.record == {"Name": "Acme"}


def test_insert_mixed_sobject_types_raises_type_error():
    with pytest.raises(TypeError, match="same sObject type"):
        insert([Account(Name="Acme"), Opportunity(Name="Deal")])


def test_insert_list_of_dicts_without_object_type_raises_type_error():
    with pytest.raises(TypeError, match="object_type string"):
        insert([{"Name": "Acme"}])
