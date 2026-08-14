import json
import logging
import os
from typing import List, TypedDict

from jinja2 import Environment, PackageLoader

from cloudy_salesforce.client import SalesforceClient
from cloudy_salesforce.client.auth import BaseAuthentication
from cloudy_salesforce.sobjects import SObjects

logger = logging.getLogger(__name__)


class FieldDict(TypedDict):
    name: str
    type: str
    picklist: List[str] | None


class ObjectDict(TypedDict):
    class_name: str
    fields: List[FieldDict]
    related_imports: List[str]


class SObjectGenerator:
    def __init__(
        self,
        authentication: BaseAuthentication,
        template_dir: str = "templates",
        template_name: str = "sobject.jinja2",
        output_dir: str = "sobjects",
    ):
        self.sf_client = SalesforceClient(auth_strategy=authentication)

        env = Environment(
            loader=PackageLoader("cloudy_salesforce.generator", template_dir)
        )
        self.template = env.get_template(template_name)
        self.output_dir = output_dir

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def get_objects(
        self,
        object_names: List[str] | str | None = None,
        path: str = ".cloudy_config",
    ) -> List[ObjectDict]:
        if not object_names:
            try:
                with open(path, "r") as file:
                    object_names = json.load(file)["sobjects"]
                    if not object_names:
                        raise ValueError("No sobjects configured in config file.")
            except FileNotFoundError:
                raise FileNotFoundError(
                    "No object names provided and no config file found."
                )

        if isinstance(object_names, str):
            object_names = [
                name.strip() for name in object_names.split(",") if name.strip()
            ]

        generated_set = set(object_names)
        sobject_client = SObjects(sf_client=self.sf_client)
        gen_objects = []

        for ob in object_names:
            describe = sobject_client.describe_sobject(ob)
            fields = sobject_client.get_object_fields(describe)
            lookups = sobject_client.get_object_lookups(describe)
            children = sobject_client.get_object_child_relations(describe)
            field_dicts, related_imports = self.parse_sf_fields(
                fields, lookups, children, generated_set, class_name=ob
            )
            gen_objects.append(
                ObjectDict(
                    class_name=ob,
                    fields=field_dicts,
                    related_imports=related_imports,
                )
            )
        return gen_objects

    def generate_all(
        self,
        object_names: List[str] | str | None = None,
        path: str = "./.cloudy_config",
    ):
        objects = self.get_objects(object_names, path)
        class_names = [obj["class_name"] for obj in objects]
        for obj in objects:
            self.generate(obj["class_name"], obj["fields"], obj["related_imports"])
        self.generate_init_file(class_names)

    def generate(
        self,
        sobject: str,
        fields: List[FieldDict],
        related_imports: List[str],
    ):
        prepared_fields = [(f["name"], f["type"]) for f in fields]
        picklist_fields = [
            (f["type"], [json.dumps(v) for v in f["picklist"]])
            for f in fields
            if f["picklist"]
        ]

        needs_datetime = any("datetime." in f["type"] for f in fields)

        generated_file = self.template.render(
            sobject=sobject,
            fields=prepared_fields,
            picklist_fields=picklist_fields,
            related_imports=related_imports,
            needs_datetime=needs_datetime,
        )

        absolute_path = os.path.join(self.output_dir, f"{sobject}.py")

        with open(absolute_path, "w") as file:
            file.write(generated_file)
        logger.info("%s generated.", absolute_path)

    def generate_init_file(self, class_names: List[str]):
        init_file_path = os.path.join(self.output_dir, "__init__.py")
        with open(init_file_path, "w") as file:
            for class_name in class_names:
                file.write(f"from .{class_name} import {class_name}\n")
        logger.info("%s generated.", init_file_path)

    def parse_sf_fields(
        self,
        fields: List[dict],
        lookups: List[dict],
        children: List[dict],
        generated_set: set[str],
        class_name: str,
    ) -> tuple[List[FieldDict], List[str]]:
        lookup_names = {f["name"] for f in lookups}
        field_dict_list: List[FieldDict] = []
        field_names: set[str] = set()
        related_imports: set[str] = set()

        def add_field(
            name: str, ftype: str, picklist: List[str] | None = None
        ) -> None:
            if name in field_names:
                return
            field_names.add(name)
            field_dict_list.append(
                FieldDict(name=name, type=ftype, picklist=picklist)
            )

        for field in fields:
            field_name = field["name"]
            sf_type = field["type"]
            field_type = parse_type(field_name, sf_type)
            picklist = None
            if sf_type == "picklist":
                picklist_values = field.get("picklistValues")
                if picklist_values:
                    picklist = [
                        item["value"]
                        for item in picklist_values
                        if item.get("active")
                    ]
            add_field(field_name, field_type, picklist)

            if sf_type == "reference" or field_name in lookup_names:
                relationship_name = field.get("relationshipName")
                reference_to = field.get("referenceTo")
                if (
                    relationship_name
                    and isinstance(reference_to, list)
                    and len(reference_to) == 1
                    and reference_to[0] in generated_set
                ):
                    ref_class = reference_to[0]
                    add_field(relationship_name, ref_class)
                    if ref_class != class_name:
                        related_imports.add(ref_class)

        for child in children:
            relationship_name = child.get("relationshipName")
            child_sobject = child.get("childSObject")
            if not relationship_name:
                continue
            if child_sobject not in generated_set:
                continue
            add_field(relationship_name, f"list[{child_sobject}]")
            if child_sobject != class_name:
                related_imports.add(child_sobject)

        return field_dict_list, sorted(related_imports)


# -----------------------HELPERS-------------------------#


def parse_type(field_name: str, field_type: str) -> str:
    if field_type == "picklist":
        sanitized = "".join(c for c in field_name if c.isalnum())
        if not sanitized or sanitized[0].isdigit():
            sanitized = f"F{sanitized}"
        return f"{sanitized.upper()}PICKLIST"
    return salesforce_to_python_type_map.get(field_type, "str")


salesforce_to_python_type_map = {
    "reference": "str",
    "string": "str",
    "phone": "str",
    "id": "str",
    "email": "str",
    "percent": "float",
    "boolean": "bool",
    "double": "float",
    "url": "str",
    "textarea": "str",
    "date": "datetime.date",
    "int": "int",
    "long": "int",
    "datetime": "datetime.datetime",
    "address": "str",
    "encryptedstring": "str",
    "currency": "float",
    "multipicklist": "str",
    "combobox": "str",
    "base64": "str",
    "time": "str",
    "location": "str",
    "json": "str",
    "anyType": "str",
}
