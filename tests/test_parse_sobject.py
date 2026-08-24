from __future__ import annotations

import datetime
from dataclasses import dataclass

import pytest

from cloudy_salesforce.sobjects import (
    SObjects,
    get_sobject_registry,
    parse_sobject_response,
    sobject,
)
from cloudy_salesforce.sobjects.sobject import parse_record
from cloudy_salesforce.types import UNSET, UnsetType


@sobject()
@dataclass
class User:
    Id: str | None = None


@sobject()
@dataclass
class Opportunity:
    Id: str | None = None
    Name: str | None = None
    CloseDate: datetime.date | None = None
    CreatedDate: datetime.datetime | None = None


@sobject()
@dataclass
class Account:
    Id: str | None = None
    Name: str | None = None
    Industry: str | None = None
    Owner: User | None = None
    Opportunities: list[Opportunity] | None = None


@sobject()
@dataclass
class DatedThing:
    Id: str | None | UnsetType = UNSET
    CloseDate: datetime.date | None | UnsetType = UNSET


def test_close_date_string_coerced_to_date():
    record = {
        "Id": "006ABC",
        "CloseDate": "2024-01-15",
        "attributes": {"type": "Opportunity"},
    }
    result = parse_record(Opportunity, record)
    assert result.CloseDate == datetime.date(2024, 1, 15)
    assert isinstance(result.CloseDate, datetime.date)


def test_created_date_string_coerced_to_datetime():
    record = {
        "Id": "006ABC",
        "CreatedDate": "2024-01-15T12:30:00.000+0000",
        "attributes": {"type": "Opportunity"},
    }
    result = parse_record(Opportunity, record)
    assert result.CreatedDate == datetime.datetime(
        2024, 1, 15, 12, 30, 0, tzinfo=datetime.timezone.utc
    )
    assert isinstance(result.CreatedDate, datetime.datetime)


def test_created_date_z_suffix_coerced_to_datetime():
    record = {
        "Id": "006ABC",
        "CreatedDate": "2024-01-15T12:30:00.000Z",
        "attributes": {"type": "Opportunity"},
    }
    result = parse_record(Opportunity, record)
    assert result.CreatedDate == datetime.datetime(
        2024, 1, 15, 12, 30, 0, tzinfo=datetime.timezone.utc
    )


def test_invalid_date_string_raises():
    record = {
        "Id": "006ABC",
        "CloseDate": "not-a-date",
        "attributes": {"type": "Opportunity"},
    }
    with pytest.raises(ValueError, match="Cannot parse date"):
        parse_record(Opportunity, record)


def test_scalars_assigned():
    record = {
        "Id": "001ABC",
        "Name": "Acme Corp",
        "Industry": "Technology",
        "attributes": {"type": "Account"},
    }
    result = parse_record(Account, record)
    assert result.Id == "001ABC"
    assert result.Name == "Acme Corp"
    assert result.Industry == "Technology"


def test_null_lookup_stays_none():
    record = {
        "Id": "001ABC",
        "Owner": None,
        "attributes": {"type": "Account"},
    }
    result = parse_record(Account, record)
    assert result.Owner is None


def test_subquery_wrapper_parses_opportunities():
    record = {
        "Id": "001ABC",
        "Opportunities": {
            "totalSize": 1,
            "done": True,
            "records": [
                {
                    "Id": "006",
                    "Name": "Deal",
                    "attributes": {"type": "Opportunity"},
                }
            ],
        },
        "attributes": {"type": "Account"},
    }
    result = parse_record(Account, record)
    assert len(result.Opportunities) == 1
    assert isinstance(result.Opportunities[0], Opportunity)
    assert result.Opportunities[0].Id == "006"
    assert result.Opportunities[0].Name == "Deal"


def test_unknown_field_skipped():
    record = {
        "Id": "001ABC",
        "NotAField": "should be ignored",
        "attributes": {"type": "Account"},
    }
    result = parse_record(Account, record)
    assert result.Id == "001ABC"
    assert not hasattr(result, "NotAField")


def test_missing_records_key_raises():
    with pytest.raises(ValueError, match="missing 'records' key"):
        parse_sobject_response(Account, {"totalSize": 0, "done": True})


def test_empty_records_returns_empty_list():
    assert parse_sobject_response(Account, {"records": []}) == []


def test_unset_type_union_still_coerces_close_date():
    record = {
        "CloseDate": "2024-01-15",
        "attributes": {"type": "DatedThing"},
    }
    result = parse_record(DatedThing, record)
    assert result.CloseDate == datetime.date(2024, 1, 15)
    assert isinstance(result.CloseDate, datetime.date)
    assert result.Id is UNSET


def test_forward_ref_registry_resolves_nested_types():
    registry = get_sobject_registry()
    assert "Account" in registry
    assert "Opportunity" in registry

    response = {
        "records": [
            {
                "Id": "001ABC",
                "Name": "Acme",
                "Opportunities": {
                    "totalSize": 1,
                    "done": True,
                    "records": [
                        {
                            "Id": "006",
                            "Name": "Big Deal",
                            "attributes": {"type": "Opportunity"},
                        }
                    ],
                },
                "attributes": {"type": "Account"},
            }
        ]
    }
    results = parse_sobject_response(Account, response)
    assert len(results) == 1
    assert isinstance(results[0], Account)
    assert len(results[0].Opportunities) == 1
    assert isinstance(results[0].Opportunities[0], Opportunity)
    assert results[0].Opportunities[0].Name == "Big Deal"


class FakeClient:
    """Minimal Salesforce client stub for describe_global tests."""

    api_version = "v61.0"

    def __init__(self, response: object) -> None:
        self._response = response
        self.last_request: tuple[str, str] | None = None

    def request(
        self,
        method: str,
        url: str,
        body: object | None = None,
        params: object | None = None,
    ) -> object:
        self.last_request = (method, url)
        return self._response


def test_describe_global_returns_sobjects_list():
    sobjects = [{"name": "Account", "label": "Account"}]
    client = FakeClient({"sobjects": sobjects})
    result = SObjects(sf_client=client).describe_global()
    assert result == sobjects
    assert client.last_request == ("GET", "/services/data/v61.0/sobjects/")


def test_describe_global_missing_key_raises():
    client = FakeClient({"encoding": "UTF-8"})
    with pytest.raises(ValueError, match="describe_global expected a dict with 'sobjects'"):
        SObjects(sf_client=client).describe_global()


def test_describe_global_non_dict_raises():
    client = FakeClient(["not", "a", "dict"])
    with pytest.raises(ValueError, match="describe_global expected a dict with 'sobjects'"):
        SObjects(sf_client=client).describe_global()


def test_describe_global_sobjects_not_list_raises():
    client = FakeClient({"sobjects": "not-a-list"})
    with pytest.raises(
        ValueError,
        match="describe_global expected 'sobjects' to be a list",
    ):
        SObjects(sf_client=client).describe_global()
