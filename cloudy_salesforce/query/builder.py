"""Typed SOQL query builder for generated ``@sobject`` dataclasses."""

from __future__ import annotations

import datetime
import types
from collections.abc import Iterable
from decimal import Decimal
from typing import Generic, TypeVar, Union, get_args, get_origin

from cloudy_salesforce.client import SalesforceClient
from cloudy_salesforce.types import UnsetType

T = TypeVar("T")

# Split where() kwargs on the last "__" only when the suffix is a known operator
# so custom fields like External_Id__c still bind as equality filters.
_WHERE_OPERATORS: dict[str, str] = {
    "eq": "=",
    "ne": "!=",
    "like": "LIKE",
    "in": "IN",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "null": "",
}

_DESC_PREFIX = "-"


def _sobject_api_name(sobject_type: type) -> str:
    """Return the Salesforce API name stored by ``@sobject``."""
    meta = getattr(sobject_type, "__sf_meta__", None)
    if not isinstance(meta, dict) or "api_name" not in meta:
        raise TypeError(
            f"{sobject_type.__name__} is not a decorated @sobject dataclass"
        )
    api_name = meta["api_name"]
    if not isinstance(api_name, str) or not api_name:
        raise TypeError(
            f"{sobject_type.__name__} has an invalid __sf_meta__ api_name"
        )
    return api_name


def _field_annotations(sobject_type: type) -> dict[str, object]:
    """Resolve dataclass field annotations, including forward refs when possible."""
    from cloudy_salesforce.sobjects.sobject import get_sobject_type_hints

    return dict(get_sobject_type_hints(sobject_type))


def _unwrap_optional(annotation: object) -> object:
    """Return the non-None member of an Optional/union, otherwise the annotation."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = [
            arg
            for arg in get_args(annotation)
            if arg is not type(None) and arg is not UnsetType
        ]
        if len(args) == 1:
            return args[0]
    return annotation


def _is_relationship_annotation(annotation: object) -> bool:
    """True for nested sObjects and child-relationship lists."""
    if isinstance(annotation, str):
        stripped = annotation.replace(" ", "")
        if stripped.startswith("list[") or stripped.startswith("List["):
            return True
        base = stripped.split("|", 1)[0]
        from cloudy_salesforce.sobjects.sobject import get_sobject_registry

        return base in get_sobject_registry()

    unwrapped = _unwrap_optional(annotation)
    origin = get_origin(unwrapped)
    if origin is list:
        inner_args = get_args(unwrapped)
        inner = inner_args[0] if inner_args else None
        return inner is not None and hasattr(inner, "__sf_meta__")
    return hasattr(unwrapped, "__sf_meta__")


def scalar_field_names(sobject_type: type) -> list[str]:
    """Return declared fields that are not nested sObjects or child lists."""
    names: list[str] = []
    for name, annotation in _field_annotations(sobject_type).items():
        if name.startswith("_"):
            continue
        if _is_relationship_annotation(annotation):
            continue
        names.append(name)
    if not names:
        raise ValueError(f"{sobject_type.__name__} has no scalar fields to select")
    return names


def _escape_soql_string(value: str) -> str:
    """Escape backslashes and single quotes for a SOQL string literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _soql_datetime(value: datetime.datetime) -> str:
    """Render a datetime as an unquoted SOQL dateTime literal in UTC."""
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    utc = value.astimezone(datetime.timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _soql_number(value: float | Decimal) -> str:
    """Format a numeric SOQL literal without scientific notation."""
    if isinstance(value, Decimal):
        text = format(value, "f")
    else:
        text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text if text else "0"


def soql_literal(value: object) -> str:
    """Render a Python value as a SOQL literal."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return _soql_number(value)
    if isinstance(value, float):
        return _soql_number(value)
    if isinstance(value, datetime.datetime):
        return _soql_datetime(value)
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, str):
        return "'" + _escape_soql_string(value) + "'"
    raise TypeError(f"Cannot render {type(value).__name__} as a SOQL literal")


def _parse_where_key(key: str) -> tuple[str, str]:
    """Split a where() kwarg into ``(field_name, operator_name)``."""
    if "__" not in key:
        return key, "eq"
    field, suffix = key.rsplit("__", 1)
    if suffix in _WHERE_OPERATORS:
        if not field:
            raise ValueError(f"Invalid where() key: {key!r}")
        return field, suffix
    return key, "eq"


def _render_condition(field: str, operator: str, value: object) -> str:
    """Render one WHERE clause predicate."""
    if operator == "null":
        if not isinstance(value, bool):
            raise TypeError(
                f"{field}__null expects a bool, got {type(value).__name__}"
            )
        return f"{field} {'=' if value else '!='} null"
    if operator == "in":
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise TypeError(
                f"{field}__in expects a sequence, got {type(value).__name__}"
            )
        items = list(value)
        if len(items) == 0:
            raise ValueError(f"{field}__in cannot be an empty sequence")
        rendered = ", ".join(soql_literal(item) for item in items)
        return f"{field} IN ({rendered})"
    sql_op = _WHERE_OPERATORS[operator]
    return f"{field} {sql_op} {soql_literal(value)}"


class SoqlQuery(Generic[T]):
    """Fluent SOQL builder bound to one ``@sobject`` dataclass."""

    def __init__(
        self,
        sobject_type: type[T],
        fields: tuple[str, ...] | None = None,
    ) -> None:
        if not hasattr(sobject_type, "__sf_meta__"):
            raise TypeError(
                f"{sobject_type.__name__} is not a decorated @sobject dataclass"
            )
        self._sobject_type = sobject_type
        self._api_name = _sobject_api_name(sobject_type)
        self._known_fields = set(_field_annotations(sobject_type))
        self._fields = self._resolve_select_fields(fields)
        self._conditions: list[str] = []
        self._order_by: list[str] = []
        self._limit: int | None = None
        self._offset: int | None = None
        self._include_deleted = False

    def _resolve_select_fields(
        self, fields: tuple[str, ...] | None
    ) -> tuple[str, ...]:
        """Validate requested fields, or default to all scalar fields."""
        if fields is None or len(fields) == 0:
            return tuple(scalar_field_names(self._sobject_type))
        resolved: list[str] = []
        annotations = _field_annotations(self._sobject_type)
        for field in fields:
            if not isinstance(field, str) or not field:
                raise ValueError("select() field names must be non-empty strings")
            self._assert_known_field(field)
            annotation = annotations.get(field)
            if annotation is not None and _is_relationship_annotation(annotation):
                raise ValueError(
                    f"{field} is a relationship on {self._sobject_type.__name__}; "
                    "select scalar fields only"
                )
            resolved.append(field)
        return tuple(resolved)

    def _assert_known_field(self, field: str) -> None:
        """Raise if ``field`` is not declared on the sObject dataclass."""
        if field not in self._known_fields:
            raise ValueError(
                f"Unknown field {field!r} on {self._sobject_type.__name__}"
            )

    def where(self, **filters: object) -> SoqlQuery[T]:
        """AND additional equality (or suffixed-operator) predicates."""
        if not filters:
            raise ValueError("where() requires at least one filter")
        annotations = _field_annotations(self._sobject_type)
        for key, value in filters.items():
            field, operator = _parse_where_key(key)
            self._assert_known_field(field)
            annotation = annotations.get(field)
            if annotation is not None and _is_relationship_annotation(annotation):
                raise ValueError(
                    f"{field} is a relationship on {self._sobject_type.__name__}; "
                    "filter on Id fields instead"
                )
            self._conditions.append(_render_condition(field, operator, value))
        return self

    def order_by(self, *fields: str) -> SoqlQuery[T]:
        """Append ORDER BY fields. Prefix with ``-`` for DESC."""
        if not fields:
            raise ValueError("order_by() requires at least one field")
        for raw in fields:
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("order_by() field names must be non-empty strings")
            direction = "ASC"
            name = raw.strip()
            if name.startswith(_DESC_PREFIX):
                name = name[1:]
                direction = "DESC"
            elif name.upper().endswith(" DESC"):
                name = name[:-5].strip()
                direction = "DESC"
            elif name.upper().endswith(" ASC"):
                name = name[:-4].strip()
                direction = "ASC"
            if not name:
                raise ValueError(f"Invalid order_by() field: {raw!r}")
            self._assert_known_field(name)
            self._order_by.append(f"{name} {direction}")
        return self

    def limit(self, n: int) -> SoqlQuery[T]:
        """Set LIMIT. ``n`` must be a non-negative integer."""
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise ValueError("limit() expects a non-negative int")
        self._limit = n
        return self

    def offset(self, n: int) -> SoqlQuery[T]:
        """Set OFFSET. ``n`` must be a non-negative integer."""
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise ValueError("offset() expects a non-negative int")
        self._offset = n
        return self

    def include_deleted(self, value: bool = True) -> SoqlQuery[T]:
        """Use queryAll so the query includes deleted and archived rows."""
        if not isinstance(value, bool):
            raise TypeError("include_deleted() expects a bool")
        self._include_deleted = value
        return self

    def to_soql(self) -> str:
        """Render the current builder state as a SOQL string."""
        parts = [
            "SELECT " + ", ".join(self._fields),
            "FROM " + self._api_name,
        ]
        if self._conditions:
            parts.append("WHERE " + " AND ".join(self._conditions))
        if self._order_by:
            parts.append("ORDER BY " + ", ".join(self._order_by))
        if self._limit is not None:
            parts.append(f"LIMIT {self._limit}")
        if self._offset is not None:
            parts.append(f"OFFSET {self._offset}")
        return " ".join(parts)

    def execute(self, client: SalesforceClient | None = None) -> list[T]:
        """Run the query and parse rows into instances of the bound sObject."""
        from cloudy_salesforce.query.query import query as run_query

        result = run_query(
            self.to_soql(),
            client=client,
            parse_as=self._sobject_type,
            include_deleted=self._include_deleted,
        )
        if not isinstance(result, list):
            raise TypeError(
                "query(parse_as=...) must return a list of sObject instances"
            )
        return result


def select(sobject_type: type[T], *fields: str) -> SoqlQuery[T]:
    """Start a typed SOQL query for ``sobject_type``."""
    return SoqlQuery(sobject_type, fields)
