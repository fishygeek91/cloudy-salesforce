from __future__ import annotations

import datetime
from dataclasses import dataclass

import pytest

from cloudy_salesforce.query.builder import SoqlQuery, select, soql_literal
from cloudy_salesforce.sobjects import sobject


class FakeClient:
    api_version = "v61.0"

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls = []

    def request(self, method, url=None, body=None, params=None):
        self.calls.append(
            {"method": method, "url": url, "body": body, "params": params}
        )
        if not self._responses:
            raise AssertionError("Unexpected extra request")
        return self._responses.pop(0)


@sobject()
@dataclass
class User:
    Id: str | None = None


@sobject()
@dataclass
class Opportunity:
    Id: str | None = None
    Name: str | None = None


@sobject()
@dataclass
class Account:
    Id: str | None = None
    Name: str | None = None
    Industry: str | None = None
    External_Id__c: str | None = None
    CreatedDate: datetime.datetime | None = None
    CloseDate: datetime.date | None = None
    IsDeleted: bool | None = None
    Owner: User | None = None
    Opportunities: list[Opportunity] | None = None


@sobject("Custom_Object__c")
@dataclass
class CustomObject:
    Id: str | None = None
    Name: str | None = None


def test_select_where_limit_renders_soql():
    soql = (
        Account.select("Id", "Name", "Industry")
        .where(Industry="Technology")
        .order_by("Name")
        .limit(10)
        .to_soql()
    )
    assert soql == (
        "SELECT Id, Name, Industry FROM Account "
        "WHERE Industry = 'Technology' ORDER BY Name ASC LIMIT 10"
    )


def test_select_without_fields_uses_scalar_fields_only():
    soql = Account.select().to_soql()
    assert soql.startswith("SELECT ")
    assert "FROM Account" in soql
    selected = soql.removeprefix("SELECT ").split(" FROM ")[0].split(", ")
    assert "Id" in selected
    assert "Name" in selected
    assert "External_Id__c" in selected
    assert "Owner" not in selected
    assert "Opportunities" not in selected


def test_where_operator_suffixes():
    soql = (
        Account.select("Id", "Name")
        .where(Name__like="Acme%", Industry__in=["Technology", "Finance"])
        .where(Id__null=False)
        .to_soql()
    )
    assert "Name LIKE 'Acme%'" in soql
    assert "Industry IN ('Technology', 'Finance')" in soql
    assert "Id != null" in soql


def test_custom_field_equality_is_not_parsed_as_operator():
    soql = Account.select("Id").where(External_Id__c="x1").to_soql()
    assert "External_Id__c = 'x1'" in soql


def test_custom_field_with_like_suffix():
    soql = Account.select("Id").where(External_Id__c__like="x%").to_soql()
    assert "External_Id__c LIKE 'x%'" in soql


def test_soql_string_escaping():
    soql = Account.select("Id").where(Name="O'Brien\\path").to_soql()
    assert "Name = 'O\\'Brien\\\\path'" in soql


def test_soql_literal_types():
    assert soql_literal(None) == "null"
    assert soql_literal(True) == "TRUE"
    assert soql_literal(False) == "FALSE"
    assert soql_literal(3) == "3"
    assert soql_literal(datetime.date(2024, 1, 15)) == "2024-01-15"
    assert (
        soql_literal(datetime.datetime(2024, 1, 15, 12, 30, 0))
        == "2024-01-15T12:30:00Z"
    )


def test_where_date_and_bool_literals():
    soql = (
        Account.select("Id")
        .where(CloseDate=datetime.date(2024, 1, 15), IsDeleted=False)
        .to_soql()
    )
    assert "CloseDate = 2024-01-15" in soql
    assert "IsDeleted = FALSE" in soql


def test_order_by_desc_prefix_and_offset():
    soql = (
        Account.select("Id", "Name")
        .order_by("-Name", "Id ASC")
        .offset(20)
        .to_soql()
    )
    assert soql.endswith("ORDER BY Name DESC, Id ASC OFFSET 20")


def test_custom_api_name_in_from_clause():
    soql = CustomObject.select("Id", "Name").to_soql()
    assert soql == "SELECT Id, Name FROM Custom_Object__c"


def test_module_level_select_matches_classmethod():
    built = select(Account, "Id", "Name").where(Name="Acme").to_soql()
    via_cls = Account.select("Id", "Name").where(Name="Acme").to_soql()
    assert built == via_cls


def test_unknown_select_field_raises():
    with pytest.raises(ValueError, match="Unknown field"):
        Account.select("NotAField")


def test_relationship_select_raises():
    with pytest.raises(ValueError, match="relationship"):
        Account.select("Opportunities")


def test_unknown_where_field_raises():
    with pytest.raises(ValueError, match="Unknown field"):
        Account.select("Id").where(Missing="x")


def test_empty_in_raises():
    with pytest.raises(ValueError, match="empty sequence"):
        Account.select("Id").where(Industry__in=[])


def test_where_requires_filters():
    with pytest.raises(ValueError, match="at least one filter"):
        Account.select("Id").where()


def test_limit_rejects_bool_and_negative():
    with pytest.raises(ValueError, match="non-negative"):
        Account.select("Id").limit(-1)
    with pytest.raises(ValueError, match="non-negative"):
        Account.select("Id").limit(True)


def test_undecorated_class_raises():
    @dataclass
    class Plain:
        Id: str | None = None

    with pytest.raises(TypeError, match="@sobject"):
        SoqlQuery(Plain, ("Id",))


def test_execute_parses_typed_results_and_sends_soql():
    fake = FakeClient(
        [
            {
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "Id": "001XYZ",
                        "Name": "Typed Account",
                        "attributes": {"type": "Account"},
                    }
                ],
            }
        ]
    )

    results = (
        Account.select("Id", "Name")
        .where(Name="Typed Account")
        .limit(1)
        .execute(client=fake)
    )

    assert len(results) == 1
    assert isinstance(results[0], Account)
    assert results[0].Id == "001XYZ"
    assert results[0].Name == "Typed Account"
    assert fake.calls[0]["url"] == "/services/data/v61.0/query"
    assert fake.calls[0]["params"]["q"] == (
        "SELECT Id, Name FROM Account WHERE Name = 'Typed Account' LIMIT 1"
    )


def test_include_deleted_uses_query_all():
    fake = FakeClient(
        [
            {
                "totalSize": 0,
                "done": True,
                "records": [],
            }
        ]
    )

    Account.select("Id").include_deleted().execute(client=fake)

    assert fake.calls[0]["url"] == "/services/data/v61.0/queryAll"
