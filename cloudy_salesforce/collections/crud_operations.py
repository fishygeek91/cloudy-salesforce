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
)

from ..client import SalesforceClient
from .return_functions import dml_results_only, records_and_response

T = TypeVar("T")


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
        dml_results_only,
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


@collections("insert", return_function=records_and_response)
def insert(
    object_type: str,
    records: List[dict],
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> CRUDProps:
    if client is None:
        client = SalesforceClient.get_default_instance()
    return {
        "client": client,
        "object_type": object_type,
        "records": records,
        "all_or_none": all_or_none,
        "batch_size": batch_size,
    }


@collections("update", return_function=records_and_response)
def update(
    object_type: str,
    records: List[dict],
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> UpdateProps:
    if client is None:
        client = SalesforceClient.get_default_instance()
    return {
        "client": client,
        "object_type": object_type,
        "records": records,
        "all_or_none": all_or_none,
        "batch_size": batch_size,
    }


@collections("upsert", return_function=records_and_response)
def upsert(
    object_type: str,
    records: List[dict],
    external_id_field: str | None = None,
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> UpsertProps:
    if client is None:
        client = SalesforceClient.get_default_instance()
    return {
        "client": client,
        "object_type": object_type,
        "records": records,
        "external_id_field": external_id_field,
        "all_or_none": all_or_none,
        "batch_size": batch_size,
    }


@collections("delete", return_function=records_and_response)
def delete(
    object_type: str,
    records: List[dict],
    all_or_none: bool = True,
    batch_size: int = 200,
    client: SalesforceClient | None = None,
) -> DeleteProps:
    if client is None:
        client = SalesforceClient.get_default_instance()
    return {
        "client": client,
        "object_type": object_type,
        "records": records,
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
