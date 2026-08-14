from functools import partial, wraps
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    TypedDict,
    TypeVar,
    cast,
    overload,
)

from ..client import SalesforceClient
from .return_functions import build_dml_results
from .serialize import normalize_records
from .types import DmlResult

T = TypeVar("T")
SObjectT = TypeVar("SObjectT")


class CRUDProps(TypedDict):
    client: SalesforceClient
    object_type: str
    records: List[dict]
    all_or_none: bool
    batch_size: int


class InsertProps(CRUDProps):
    pass


class UpdateProps(CRUDProps):
    pass


class UpsertProps(CRUDProps):
    external_id_field: Optional[str]  # defaults to "Id"


class DeleteProps(CRUDProps):
    pass


CRUDLiteral = Literal["insert", "upsert", "update", "delete"]

COLLECTION_METHODS = {
    "insert": "POST",
    "update": "PATCH",
    "upsert": "PATCH",
    "delete": "DELETE",
}


def collections(
    operation: CRUDLiteral,
    return_function: Callable[
        [List[Dict[str, Any]], List[Dict[str, Any]]], T
    ] = cast(
        Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], T],
        build_dml_results,
    ),
) -> Callable[[Callable[..., CRUDProps]], Callable[..., T]]:
    def decorator(func: Callable[..., CRUDProps]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            props: CRUDProps = func(*args, **kwargs)
            client = props["client"]
            records_to_process = props["records"]

            crud_function = partial(client.request, COLLECTION_METHODS[operation])

            results: List[Dict[str, Any]] = []

            for records in batch_records(records_to_process, props["batch_size"]):
                url, body, params = build_payload(
                    operation, {**props, "records": records}
                )

                dml_response = crud_function(url=url, body=body, params=params)

                if not isinstance(dml_response, list):
                    raise ValueError(
                        f"Expected a list of responses, but received: {dml_response}"
                    )
                results.extend(dml_response)

            return return_function(records_to_process, results)

        return wrapper

    return decorator


@overload
def insert(
    object_type: str,
    records: List[dict],
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@overload
def insert(
    record: SObjectT,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@overload
def insert(
    records: list[SObjectT],
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@collections("insert")
def insert(
    first_arg: str | Any,
    records: List[dict] | None = None,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> CRUDProps:
    object_type, normalized_records = normalize_records(first_arg, records)
    if client is None:
        client = SalesforceClient.get_default_instance()
    return {
        "client": client,
        "object_type": object_type,
        "records": normalized_records,
        "all_or_none": all_or_none,
        "batch_size": batch_size,
    }


@overload
def update(
    object_type: str,
    records: List[dict],
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@overload
def update(
    record: SObjectT,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@overload
def update(
    records: list[SObjectT],
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@collections("update")
def update(
    first_arg: str | Any,
    records: List[dict] | None = None,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> UpdateProps:
    object_type, normalized_records = normalize_records(first_arg, records)
    if client is None:
        client = SalesforceClient.get_default_instance()
    return {
        "client": client,
        "object_type": object_type,
        "records": normalized_records,
        "all_or_none": all_or_none,
        "batch_size": batch_size,
    }


@overload
def upsert(
    object_type: str,
    records: List[dict],
    external_id_field: str | None = None,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@overload
def upsert(
    record: SObjectT,
    external_id_field: str | None = None,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@overload
def upsert(
    records: list[SObjectT],
    external_id_field: str | None = None,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@collections("upsert")
def upsert(
    first_arg: str | Any,
    records: List[dict] | None = None,
    external_id_field: str | None = None,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> UpsertProps:
    object_type, normalized_records = normalize_records(first_arg, records)
    if client is None:
        client = SalesforceClient.get_default_instance()
    return {
        "client": client,
        "object_type": object_type,
        "records": normalized_records,
        "external_id_field": external_id_field,
        "all_or_none": all_or_none,
        "batch_size": batch_size,
    }


@overload
def delete(
    object_type: str,
    records: List[dict],
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@overload
def delete(
    record: SObjectT,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@overload
def delete(
    records: list[SObjectT],
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> list[DmlResult]: ...


@collections("delete")
def delete(
    first_arg: str | Any,
    records: List[dict] | None = None,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> DeleteProps:
    object_type, normalized_records = normalize_records(first_arg, records)
    if client is None:
        client = SalesforceClient.get_default_instance()
    return {
        "client": client,
        "object_type": object_type,
        "records": normalized_records,
        "all_or_none": all_or_none,
        "batch_size": batch_size,
    }


def batch_records(records: List[dict], batch_size: int) -> List[List[dict]]:
    return [records[i : i + batch_size] for i in range(0, len(records), batch_size)]


def add_attributes(records: List[dict], object_type: str) -> List[dict]:
    return [
        {**record, "attributes": {"type": object_type}} for record in records
    ]


def get_id_list(records: List[dict]) -> List[str]:
    ids = []
    for record in records:
        if "Id" in record:
            ids.append(record["Id"])
        elif "id" in record:
            ids.append(record["id"])
        else:
            raise ValueError(f"Record does not contain an Id/id field: {record}")
    return ids


def build_payload(
    operation: CRUDLiteral,
    props: CRUDProps,
) -> Tuple[str, dict | None, dict | None]:
    records = props["records"]
    all_or_none = props["all_or_none"]
    client = props["client"]
    api_version = getattr(client, "api_version", SalesforceClient.DEFAULT_API_VERSION)

    if operation == "delete":
        params = {
            "ids": ",".join(get_id_list(records)),
            "allOrNone": str(all_or_none).lower(),
        }
        return (
            f"/services/data/{api_version}/composite/sobjects",
            None,
            params,
        )

    object_type = props["object_type"]
    body = {"allOrNone": all_or_none, "records": add_attributes(records, object_type)}

    if operation == "upsert":
        upsert_props = cast(UpsertProps, props)
        if upsert_props.get("external_id_field") is not None:
            external_id = upsert_props["external_id_field"]
        else:
            external_id = "Id"
        return (
            f"/services/data/{api_version}/composite/sobjects/{object_type}/{external_id}",
            body,
            None,
        )

    return f"/services/data/{api_version}/composite/sobjects/", body, None
