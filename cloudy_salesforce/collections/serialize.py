from __future__ import annotations

import dataclasses
import datetime
import types
from typing import Any, Union, get_args, get_origin

from cloudy_salesforce.types import UNSET, UnsetType


def _is_sobject_type(cls: type) -> bool:
    meta = getattr(cls, "__sf_meta__", None)
    return isinstance(meta, dict) and "api_name" in meta


def is_sobject_instance(obj: Any) -> bool:
    return _is_sobject_type(type(obj))


def get_api_name(obj: Any) -> str:
    meta = getattr(type(obj), "__sf_meta__", None)
    if not isinstance(meta, dict) or "api_name" not in meta:
        raise TypeError(f"{type(obj).__name__} is not an sObject dataclass")
    return str(meta["api_name"])


def _should_skip_value(value: Any) -> bool:
    if is_sobject_instance(value):
        return True
    if isinstance(value, list) and value and all(is_sobject_instance(item) for item in value):
        return True
    return False


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value


def _annotation_includes_unset(annotation: object) -> bool:
    """True when a field annotation includes ``UnsetType`` (UNSET-aware classes)."""
    if annotation is UnsetType:
        return True
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        return any(_annotation_includes_unset(arg) for arg in get_args(annotation))
    return False


def serialize_record(record: Any) -> dict[str, Any]:
    """Serialize an sObject instance to a composite API record dict.

    Fields set to ``UNSET`` are omitted. Explicit ``None`` is sent as JSON null
    only when the field annotation includes ``UnsetType`` (generated classes
    after UNSET landed). Pre-UNSET dataclasses still omit ``None``. Nested
    relationship fields are never sent as null — the composite API rejects them.
    """
    if not is_sobject_instance(record):
        raise TypeError(f"Expected sObject instance, got {type(record).__name__}")
    from cloudy_salesforce.query.builder import _is_relationship_annotation
    from cloudy_salesforce.sobjects.sobject import get_sobject_type_hints

    hints = get_sobject_type_hints(type(record))
    result: dict[str, Any] = {}
    for field in dataclasses.fields(record):
        value = getattr(record, field.name)
        if value is UNSET:
            continue
        annotation = hints.get(field.name)
        if value is None:
            if annotation is not None and _is_relationship_annotation(annotation):
                continue
            if _annotation_includes_unset(annotation):
                result[field.name] = None
            continue
        if _should_skip_value(value):
            continue
        result[field.name] = _serialize_value(value)
    return result


def normalize_records(
    first_arg: Any,
    records_arg: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    if isinstance(first_arg, str):
        if records_arg is None:
            raise TypeError("records argument is required when object_type is a string")
        if not isinstance(records_arg, list):
            raise TypeError("records must be a list")
        if records_arg and not all(isinstance(record, dict) for record in records_arg):
            raise TypeError("records must be a list of dicts when object_type is provided")
        return first_arg, records_arg

    if is_sobject_instance(first_arg):
        return get_api_name(first_arg), [serialize_record(first_arg)]

    if isinstance(first_arg, list):
        if not first_arg:
            raise TypeError("records list cannot be empty")
        if all(isinstance(record, dict) for record in first_arg):
            raise TypeError(
                "List of dicts requires an object_type string as the first argument"
            )
        if not all(is_sobject_instance(record) for record in first_arg):
            raise TypeError("All records must be sObject instances")
        api_names = {get_api_name(record) for record in first_arg}
        if len(api_names) > 1:
            raise TypeError("All records must be the same sObject type")
        return api_names.pop(), [serialize_record(record) for record in first_arg]

    raise TypeError(
        "Expected object_type str, sObject instance, or list of sObjects, "
        f"got {type(first_arg).__name__}"
    )
