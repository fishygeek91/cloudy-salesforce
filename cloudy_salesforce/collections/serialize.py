from __future__ import annotations

import dataclasses
import datetime
from typing import Any


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


def serialize_record(record: Any) -> dict[str, Any]:
    if not is_sobject_instance(record):
        raise TypeError(f"Expected sObject instance, got {type(record).__name__}")
    result: dict[str, Any] = {}
    for field in dataclasses.fields(record):
        value = getattr(record, field.name)
        if value is None:
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
