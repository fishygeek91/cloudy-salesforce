import importlib
import sys
from dataclasses import is_dataclass

from jinja2 import Environment, PackageLoader

from cloudy_salesforce.generator.generator import (
    SObjectGenerator,
    parse_type,
    salesforce_to_python_type_map,
    unique_picklist_alias,
)
from cloudy_salesforce.sobjects.sobject import parse_record
from cloudy_salesforce.types import UNSET


def _generator_instance() -> SObjectGenerator:
    return SObjectGenerator.__new__(SObjectGenerator)


def test_get_objects_splits_comma_separated_names(monkeypatch):
    gen = _generator_instance()
    captured = {}

    def fake_describe(name):
        captured.setdefault("names", []).append(name)
        return {
            "fields": [{"name": "Id", "type": "id"}],
            "childRelationships": [],
        }

    gen.sf_client = object()
    monkeypatch.setattr(
        "cloudy_salesforce.generator.generator.SObjects",
        lambda sf_client=None: type(
            "FakeSObjects",
            (),
            {
                "describe_sobject": staticmethod(fake_describe),
                "get_object_fields": staticmethod(lambda resp: resp["fields"]),
                "get_object_lookups": staticmethod(lambda resp: []),
                "get_object_child_relations": staticmethod(
                    lambda resp: resp["childRelationships"]
                ),
            },
        )(),
    )

    objects = gen.get_objects("Account, Contact")
    assert [obj["class_name"] for obj in objects] == ["Account", "Contact"]
    assert captured["names"] == ["Account", "Contact"]


def test_parse_type_picklist_sanitization():
    assert parse_type("2FA__c", "picklist") == "F2FA__C_PICKLIST"
    assert parse_type("Industry", "picklist") == "INDUSTRY_PICKLIST"
    assert parse_type("Sub_Type__c", "picklist") == "SUB_TYPE__C_PICKLIST"
    assert parse_type("Name", "mystery") == "str"
    assert "mystery" not in salesforce_to_python_type_map


def test_parse_type_date_and_datetime():
    assert parse_type("CloseDate", "date") == "datetime.date"
    assert parse_type("CreatedDate", "datetime") == "datetime.datetime"
    assert salesforce_to_python_type_map["date"] == "datetime.date"
    assert salesforce_to_python_type_map["datetime"] == "datetime.datetime"


def test_parse_sf_fields_relationships():
    gen = _generator_instance()
    generated_set = {"Account", "Opportunity"}

    account_fields = [
        {"name": "Id", "type": "id"},
        {"name": "Name", "type": "string"},
        {
            "name": "Industry",
            "type": "picklist",
            "picklistValues": [
                {"value": "Tech", "active": True},
                {"value": "Legacy", "active": False},
            ],
        },
        {
            "name": "OwnerId",
            "type": "reference",
            "referenceTo": ["User"],
            "relationshipName": "Owner",
        },
    ]
    account_lookups = [f for f in account_fields if f["type"] == "reference"]
    account_children = [
        {"relationshipName": "Opportunities", "childSObject": "Opportunity"},
    ]

    account_field_dicts, account_imports = gen.parse_sf_fields(
        account_fields,
        account_lookups,
        account_children,
        generated_set,
        class_name="Account",
    )
    account_by_name = {f["name"]: f for f in account_field_dicts}

    assert account_by_name["Opportunities"]["type"] == "list[Opportunity]"
    assert "Opportunity" in account_imports
    assert "Owner" not in account_by_name

    industry_field = account_by_name["Industry"]
    assert industry_field["picklist"] == ["Tech"]

    opportunity_fields = [
        {"name": "Id", "type": "id"},
        {
            "name": "AccountId",
            "type": "reference",
            "referenceTo": ["Account"],
            "relationshipName": "Account",
        },
    ]
    opportunity_lookups = [f for f in opportunity_fields if f["type"] == "reference"]

    opp_field_dicts, opp_imports = gen.parse_sf_fields(
        opportunity_fields,
        opportunity_lookups,
        [],
        generated_set,
        class_name="Opportunity",
    )
    opp_by_name = {f["name"]: f for f in opp_field_dicts}

    assert opp_by_name["AccountId"]["type"] == "str"
    assert opp_by_name["Account"]["type"] == "Account"
    assert "Account" in opp_imports


def test_parse_sf_fields_self_lookup_no_self_import():
    gen = _generator_instance()
    generated_set = {"Account"}

    fields = [
        {"name": "Id", "type": "id"},
        {
            "name": "ParentId",
            "type": "reference",
            "referenceTo": ["Account"],
            "relationshipName": "Parent",
        },
    ]
    lookups = [f for f in fields if f["type"] == "reference"]

    field_dicts, related_imports = gen.parse_sf_fields(
        fields, lookups, [], generated_set, class_name="Account"
    )
    by_name = {f["name"]: f for f in field_dicts}

    assert by_name["Parent"]["type"] == "Account"
    assert "Account" not in related_imports


def test_parse_sf_fields_polymorphic_reference_skipped():
    gen = _generator_instance()
    generated_set = {"Task", "Contact", "Lead"}

    fields = [
        {"name": "Id", "type": "id"},
        {
            "name": "WhoId",
            "type": "reference",
            "referenceTo": ["Contact", "Lead"],
            "relationshipName": "Who",
        },
    ]
    lookups = [f for f in fields if f["type"] == "reference"]

    field_dicts, related_imports = gen.parse_sf_fields(
        fields, lookups, [], generated_set, class_name="Task"
    )
    by_name = {f["name"]: f for f in field_dicts}

    assert "WhoId" in by_name
    assert "Who" not in by_name
    assert related_imports == []


def test_parse_sf_fields_empty_picklist_uses_str():
    gen = _generator_instance()

    empty_values_fields = [
        {"name": "Id", "type": "id"},
        {"name": "Status", "type": "picklist", "picklistValues": []},
    ]
    inactive_values_fields = [
        {"name": "Id", "type": "id"},
        {
            "name": "Status",
            "type": "picklist",
            "picklistValues": [
                {"value": "Open", "active": False},
                {"value": "Closed", "active": False},
            ],
        },
    ]
    missing_values_fields = [
        {"name": "Id", "type": "id"},
        {"name": "Status", "type": "picklist"},
    ]

    for fields in (
        empty_values_fields,
        inactive_values_fields,
        missing_values_fields,
    ):
        field_dicts, _ = gen.parse_sf_fields(
            fields, [], [], {"Account"}, class_name="Account"
        )
        status_field = next(f for f in field_dicts if f["name"] == "Status")
        assert status_field["type"] == "str"
        assert status_field["picklist"] is None


def test_picklist_alias_no_collision():
    gen = _generator_instance()
    fields = [
        {"name": "Id", "type": "id"},
        {
            "name": "Sub_Type__c",
            "type": "picklist",
            "picklistValues": [{"value": "A", "active": True}],
        },
        {
            "name": "SubType__c",
            "type": "picklist",
            "picklistValues": [{"value": "B", "active": True}],
        },
    ]

    field_dicts, _ = gen.parse_sf_fields(
        fields, [], [], {"Account"}, class_name="Account"
    )
    by_name = {f["name"]: f for f in field_dicts}

    assert by_name["Sub_Type__c"]["type"] == "SUB_TYPE__C_PICKLIST"
    assert by_name["SubType__c"]["type"] == "SUBTYPE__C_PICKLIST"


def test_unique_picklist_alias_collision_suffix():
    used_aliases: set[str] = set()
    first = unique_picklist_alias("Industry", used_aliases)
    second = unique_picklist_alias("industry", used_aliases)

    assert first == "INDUSTRY_PICKLIST"
    assert second == "INDUSTRY_PICKLIST_2"


def test_generate_init_file_emits_all(tmp_path):
    gen = SObjectGenerator.__new__(SObjectGenerator)
    gen.output_dir = str(tmp_path / "sobjects")
    gen.generate_init_file(["Account", "Opportunity"])

    init_path = tmp_path / "sobjects" / "__init__.py"
    content = init_path.read_text(encoding="utf-8")

    assert "__all__" in content
    assert "__all__ = ['Account', 'Opportunity']" in content
    assert "from .Account import Account" in content
    assert "from .Opportunity import Opportunity" in content


def test_template_render_circular_imports(tmp_path):
    env = Environment(
        loader=PackageLoader("cloudy_salesforce.generator", "templates")
    )
    template = env.get_template("sobject.jinja2")

    account_fields = [
        ("Id", "str"),
        ("Name", "str"),
        ("Opportunities", "list[Opportunity]"),
    ]
    opportunity_fields = [
        ("Id", "str"),
        ("Name", "str"),
        ("AccountId", "str"),
        ("Account", "Account"),
    ]

    account_source = template.render(
        sobject="Account",
        fields=account_fields,
        picklist_fields=[],
        related_imports=["Opportunity"],
        needs_datetime=False,
    )
    opportunity_source = template.render(
        sobject="Opportunity",
        fields=opportunity_fields,
        picklist_fields=[],
        related_imports=["Account"],
        needs_datetime=False,
    )
    assert "# noqa: E402" in opportunity_source

    pkg_dir = tmp_path / "generated_sobjects"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "Account.py").write_text(account_source)
    (pkg_dir / "Opportunity.py").write_text(opportunity_source)

    sys.path.insert(0, str(tmp_path))
    try:
        # Import Opportunity only — Account must load via the runtime import
        # at the bottom of Opportunity.py, not via package __init__.
        opportunity_mod = importlib.import_module("generated_sobjects.Opportunity")
        opportunity_cls = opportunity_mod.Opportunity
        assert is_dataclass(opportunity_cls)

        record = {
            "Id": "006000000000001",
            "Name": "Big Deal",
            "Account": {"Id": "001000000000001", "Name": "Acme"},
        }
        opportunity = parse_record(opportunity_cls, record)

        assert opportunity.Name == "Big Deal"
        assert opportunity.Account is not None
        assert opportunity.Account.Name == "Acme"

        account_mod = importlib.import_module("generated_sobjects.Account")
        account = account_mod.Account()
        assert is_dataclass(account_mod.Account)
        assert account.Id is UNSET
        assert account.Name is UNSET
        assert account.Opportunities is UNSET
    finally:
        sys.path.remove(str(tmp_path))
        for name in list(sys.modules):
            if name == "generated_sobjects" or name.startswith("generated_sobjects."):
                del sys.modules[name]


def test_parse_sf_fields_empty_child_relationships_allowed():
    gen = _generator_instance()
    fields = [{"name": "Id", "type": "id"}]

    field_dicts, related_imports = gen.parse_sf_fields(
        fields, [], [], {"Account"}, class_name="Account"
    )

    assert len(field_dicts) == 1
    assert related_imports == []
