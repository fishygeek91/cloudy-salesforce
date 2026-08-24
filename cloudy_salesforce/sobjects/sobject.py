from __future__ import annotations

import datetime
import logging
import re
import sys
import types
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

if TYPE_CHECKING:
    from cloudy_salesforce.query.builder import SoqlQuery

from cloudy_salesforce.client import SalesforceClient
from cloudy_salesforce.types import UnsetType

logger = logging.getLogger(__name__)

T = TypeVar("T")

_SObjectRegistry: dict[str, type] = {}
_type_hints_cache: dict[type, dict[str, object]] = {}


def get_sobject_registry() -> dict[str, type]:
    """Return a copy of the registered sObject types."""
    return _SObjectRegistry.copy()


def get_sobject_type_hints(sobject_type: type) -> dict[str, object]:
    """Return cached typing.get_type_hints for an sObject class."""
    cached = _type_hints_cache.get(sobject_type)
    if cached is not None:
        return cached
    module = sys.modules.get(sobject_type.__module__)
    module_ns = getattr(module, "__dict__", {})
    hints = get_type_hints(
        sobject_type,
        globalns=module_ns,
        localns={**module_ns, **_SObjectRegistry},
    )
    _type_hints_cache[sobject_type] = hints
    return hints


def sobject(api_name: str | None = None):
    """Decorator that marks a class as a Salesforce sObject and registers it.

    Adds ``cls.select(*fields)`` so generated dataclasses can start a typed
    SOQL builder without a Jinja change.
    """

    def decorator(cls: type) -> type:
        api_name_to_set = api_name or cls.__name__
        setattr(cls, "__sf_meta__", {"api_name": api_name_to_set})
        _SObjectRegistry[cls.__name__] = cls
        _SObjectRegistry[api_name_to_set] = cls

        def _select(sobject_cls: type[T], *fields: str) -> SoqlQuery[T]:
            """Start a typed SOQL query for this sObject."""
            from cloudy_salesforce.query.builder import SoqlQuery

            return SoqlQuery(sobject_cls, fields)

        setattr(cls, "select", classmethod(_select))
        return cls

    return decorator


def parse_sobject_response(sobject: type[T], response: dict) -> list[T]:
    """Parse a Salesforce query response into a list of sObject instances."""
    if "records" not in response:
        raise ValueError("Response missing 'records' key")
    records = response["records"]
    if not records:
        return []
    return [parse_record(sobject, record) for record in records]


def parse_record(sobject: type[T], record: dict) -> T:
    """Parse a single Salesforce record dict into an sObject instance."""
    hints = get_sobject_type_hints(sobject)
    instance = sobject()
    for key, value in record.items():
        if key == "attributes":
            continue
        if key not in hints:
            logger.warning(
                "Unknown field %s on %s, skipping",
                key,
                sobject.__name__,
            )
            continue
        setattr(instance, key, coerce_value(hints[key], value))
    return instance


def _union_non_none_args(annotation: Any) -> list[Any] | None:
    """Return non-None union members, or None if the annotation is not a union."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        return [
            arg
            for arg in get_args(annotation)
            if arg is not type(None) and arg is not UnsetType
        ]
    return None


def _normalize_sf_datetime_string(value: str) -> str:
    """Normalize a Salesforce ISO datetime string for ``datetime.fromisoformat``."""
    if value.endswith("Z"):
        return value[:-1] + "+00:00"
    match = re.search(r"([+-]\d{2})(\d{2})$", value)
    if match is not None and ":" not in value[match.start():]:
        return value[:match.start()] + match.group(1) + ":" + match.group(2)
    return value


def _parse_sf_date(value: str) -> datetime.date:
    """Parse a Salesforce date string (YYYY-MM-DD) into a ``datetime.date``."""
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Cannot parse date from string: {value}")


def _parse_sf_datetime(value: str) -> datetime.datetime:
    """Parse a Salesforce ISO datetime string into a ``datetime.datetime``."""
    try:
        return datetime.datetime.fromisoformat(_normalize_sf_datetime_string(value))
    except ValueError:
        raise ValueError(f"Cannot parse datetime from string: {value}")


def coerce_value(annotation: Any, value: Any) -> Any:
    """Coerce a Salesforce JSON value to match the annotated field type."""
    if value is None:
        return None

    non_none_args = _union_non_none_args(annotation)
    if non_none_args is not None:
        if len(non_none_args) == 1:
            return coerce_value(non_none_args[0], value)
        return value

    if annotation is datetime.datetime:
        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, str):
            return _parse_sf_datetime(value)
        return value

    if annotation is datetime.date:
        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, datetime.date):
            return value
        if isinstance(value, str):
            return _parse_sf_date(value)
        return value

    if get_origin(annotation) is list:
        inner_type = get_args(annotation)[0] if get_args(annotation) else None
        if isinstance(value, dict) and "records" in value:
            records = value["records"]
        elif isinstance(value, list):
            records = value
        else:
            return value
        if inner_type is not None and hasattr(inner_type, "__sf_meta__"):
            return [parse_record(inner_type, record) for record in records]
        return records

    if hasattr(annotation, "__sf_meta__") and isinstance(value, dict):
        return parse_record(annotation, value)

    return value


class SObjects:
    def __init__(self, sf_client: SalesforceClient | None = None):
        if sf_client is None:
            sf_client = SalesforceClient.get_default_instance()
        self.sf_client = sf_client

    def describe_global(self) -> list[dict]:
        """Return the org sObject list from GET /sobjects/."""
        version = getattr(self.sf_client, "api_version", "v61.0")
        url = f"/services/data/{version}/sobjects/"
        response = self.sf_client.request("GET", url)
        if not isinstance(response, dict) or "sobjects" not in response:
            raise ValueError(
                f"describe_global expected a dict with 'sobjects', got: {response}"
            )
        sobjects = response["sobjects"]
        if not isinstance(sobjects, list):
            raise ValueError(
                f"describe_global expected 'sobjects' to be a list, got: {sobjects}"
            )
        return sobjects

    def describe_sobject(self, sobject: str) -> dict:
        """Query the Salesforce API to describe the specified sObject."""
        version = getattr(self.sf_client, "api_version", "v61.0")
        url = f"/services/data/{version}/sobjects/{sobject}/describe/"
        response = self.sf_client.request("GET", url)
        if not isinstance(response, dict):
            raise ValueError(f"describe_sobject expected a dict, got: {response}")
        return response

    def get_object_fields(self, object_resp: dict) -> list[dict]:
        """Return the fields list from a describe response."""
        if "fields" not in object_resp:
            raise ValueError("Describe response missing 'fields' key")
        return object_resp["fields"]

    def get_object_lookups(self, object_resp: dict) -> list[dict]:
        """Return reference-type fields from a describe response."""
        lookup_fields: list[dict] = []
        for field in self.get_object_fields(object_resp):
            if field["type"] == "reference":
                lookup_fields.append(field)
        return lookup_fields

    def get_object_child_relations(self, object_resp: dict) -> list[dict]:
        """Return child relationships from a describe response."""
        if "childRelationships" not in object_resp:
            raise ValueError("Describe response missing 'childRelationships' key")
        return object_resp["childRelationships"]

    def query_sobject(
        self,
        object_type: type[T],
        query_string: str,
        client: SalesforceClient | None = None,
        include_deleted: bool = False,
    ) -> list[T]:
        """Execute a SOQL query and parse results into typed sObject instances."""
        if client is None:
            client = self.sf_client
        from cloudy_salesforce.query import query as run_query

        return cast(
            list[T],
            run_query(
                query_string,
                client=client,
                parse_as=object_type,
                include_deleted=include_deleted,
            ),
        )
