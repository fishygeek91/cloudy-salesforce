import json
from pathlib import Path

from jinja2 import Environment, PackageLoader

from cloudy_salesforce.generator.generator import SObjectGenerator
from cloudy_salesforce.sobjects.sobject import SObjects
from tests.fixtures.account_opportunity_fields import (
    GENERATED_SET,
    SOBJECT_DESCRIBES,
    SOBJECT_ORDER,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples" / "generated"


def _generator_instance() -> SObjectGenerator:
    return SObjectGenerator.__new__(SObjectGenerator)


def _render_sobject(
    gen: SObjectGenerator,
    template,
    class_name: str,
    describe: dict,
) -> str:
    sobject_client = SObjects(sf_client=object())
    fields = sobject_client.get_object_fields(describe)
    lookups = sobject_client.get_object_lookups(describe)
    children = sobject_client.get_object_child_relations(describe)
    field_dicts, related_imports = gen.parse_sf_fields(
        fields,
        lookups,
        children,
        set(GENERATED_SET),
        class_name=class_name,
    )
    prepared_fields = [(f["name"], f["type"]) for f in field_dicts]
    picklist_fields = [
        (f["type"], [json.dumps(v) for v in f["picklist"]])
        for f in field_dicts
        if f["picklist"]
    ]
    return template.render(
        sobject=class_name,
        fields=prepared_fields,
        picklist_fields=picklist_fields,
        related_imports=related_imports,
    )


def _render_examples_from_fixture() -> dict[str, str]:
    gen = _generator_instance()
    env = Environment(
        loader=PackageLoader("cloudy_salesforce.generator", "templates")
    )
    template = env.get_template("sobject.jinja2")

    rendered: dict[str, str] = {}
    for class_name in SOBJECT_ORDER:
        describe = SOBJECT_DESCRIBES[class_name]
        rendered[f"{class_name}.py"] = _render_sobject(
            gen, template, class_name, describe
        )

    init_lines = [f"from .{name} import {name}\n" for name in SOBJECT_ORDER]
    rendered["__init__.py"] = "".join(init_lines)
    return rendered


def test_examples_generated_match_fixture():
    rendered = _render_examples_from_fixture()

    for filename, expected_content in rendered.items():
        checked_in_path = EXAMPLES_DIR / filename
        checked_in = checked_in_path.read_text()
        assert checked_in == expected_content, (
            f"{filename} drifted from fixture output; regenerate examples/generated"
        )
