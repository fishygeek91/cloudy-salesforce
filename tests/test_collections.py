import pytest

from cloudy_salesforce.collections.crud_operations import (
    add_attributes,
    batch_records,
    build_payload,
    get_id_list,
)


class FakeClient:
    api_version = "v61.0"


def _props(records, all_or_none=True):
    return {
        "client": FakeClient(),
        "object_type": "Account",
        "records": records,
        "all_or_none": all_or_none,
        "batch_size": 200,
    }


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
