from __future__ import annotations

from dataclasses import dataclass

from cloudy_salesforce.query import query
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


def test_query_pagination_concatenates_pages():
    fake = FakeClient(
        [
            {
                "totalSize": 2,
                "done": False,
                "records": [{"Id": "001", "attributes": {"type": "Account"}}],
                "nextRecordsUrl": "/services/data/v61.0/query/next",
            },
            {
                "totalSize": 2,
                "done": True,
                "records": [{"Id": "002", "attributes": {"type": "Account"}}],
            },
        ]
    )

    result = query("SELECT Id FROM Account", client=fake)

    assert len(result["records"]) == 2
    assert result["records"][0]["Id"] == "001"
    assert result["records"][1]["Id"] == "002"
    assert fake.calls[0]["url"] == "/services/data/v61.0/query"
    assert "v61.0" in fake.calls[0]["url"]
    assert "v52.0" not in fake.calls[0]["url"]
    assert fake.calls[1]["url"] == "/services/data/v61.0/query/next"


def test_query_nested_subquery_pagination_merges_child_records():
    fake = FakeClient(
        [
            {
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "Id": "001",
                        "Opportunities": {
                            "totalSize": 2,
                            "done": False,
                            "records": [
                                {
                                    "Id": "006A",
                                    "attributes": {"type": "Opportunity"},
                                }
                            ],
                            "nextRecordsUrl": "/services/data/v61.0/query/child-next",
                        },
                        "attributes": {"type": "Account"},
                    }
                ],
            },
            {
                "totalSize": 2,
                "done": True,
                "records": [
                    {"Id": "006B", "attributes": {"type": "Opportunity"}},
                ],
            },
        ]
    )

    result = query(
        "SELECT Id, (SELECT Id FROM Opportunities) FROM Account",
        client=fake,
    )

    child_records = result["records"][0]["Opportunities"]["records"]
    assert len(child_records) == 2
    assert child_records[0]["Id"] == "006A"
    assert child_records[1]["Id"] == "006B"


def test_query_include_deleted_uses_query_all():
    fake = FakeClient(
        [
            {
                "totalSize": 0,
                "done": True,
                "records": [],
            }
        ]
    )

    query("SELECT Id FROM Account", client=fake, include_deleted=True)

    assert fake.calls[0]["url"] == "/services/data/v61.0/queryAll"


@sobject()
@dataclass
class Account:
    Id: str | None = None
    Name: str | None = None


def test_query_parse_as_returns_typed_instances():
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

    results = query(
        "SELECT Id, Name FROM Account",
        client=fake,
        parse_as=Account,
    )

    assert len(results) == 1
    assert isinstance(results[0], Account)
    assert results[0].Id == "001XYZ"
    assert results[0].Name == "Typed Account"
