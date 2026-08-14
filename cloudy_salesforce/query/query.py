from functools import partial, wraps
from typing import Any, Callable, Literal, TypedDict, TypeVar

from cloudy_salesforce.client.salesforceclient import SalesforceClient

from .return_functions import response_json_only

T = TypeVar("T")


class QueryProps(TypedDict):
    client: SalesforceClient
    soql_query: str


QueryEndpoints = Literal["query", "queryAll"]


def soql_query(
    endpoint: QueryEndpoints = "query",
    return_function: Callable[[dict[str, Any]], T] = response_json_only,
) -> Callable[[Callable[..., QueryProps]], Callable[..., T]]:
    def decorator(func: Callable[..., QueryProps]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            props: QueryProps = func(*args, **kwargs)
            client = props["client"]
            version = getattr(client, "api_version", "v61.0")
            url = f"/services/data/{version}/{endpoint}"
            params = {"q": props["soql_query"]}

            crud_function = partial(client.request, "GET")

            results: dict[str, Any] = {
                "totalSize": 0,
                "done": False,
                "records": [],
                "nextRecordsUrl": None,
            }

            def query_all(url, params, results):
                while not results["done"] and url:
                    query_response = crud_function(url=url, body=None, params=params)
                    if not isinstance(query_response, dict):
                        raise ValueError(
                            f"Expected a dict of responses, but received: {query_response}"
                        )
                    results["records"].extend(query_response["records"])
                    results["done"] = query_response["done"]
                    results["totalSize"] = query_response["totalSize"]
                    results["nextRecordsUrl"] = query_response.get("nextRecordsUrl")

                    url = results["nextRecordsUrl"]
                    params = None

            query_all(url, params, results)

            def handle_nested_queries(records: list[dict[str, Any]]) -> None:
                for record in records:
                    for key, value in record.items():
                        if isinstance(value, dict) and "nextRecordsUrl" in value:
                            query_all(value["nextRecordsUrl"], None, value)
                            handle_nested_queries(value["records"])

            handle_nested_queries(results["records"])

            return return_function(results)

        return wrapper

    return decorator


def query(
    soql: str,
    client: SalesforceClient | None = None,
    parse_as: type[T] | None = None,
    include_deleted: bool = False,
) -> list[T] | dict[str, Any]:
    """Run a SOQL query, paginating automatically.

    When ``parse_as`` is a generated ``@sobject`` dataclass, returns ``list[T]``.
    Otherwise returns the raw Salesforce result dict.
    """
    if client is None:
        client = SalesforceClient.get_default_instance()
    endpoint: QueryEndpoints = "queryAll" if include_deleted else "query"

    if parse_as is not None:
        from cloudy_salesforce.sobjects.sobject import parse_sobject_response

        return_function: Callable[[dict[str, Any]], Any] = partial(
            parse_sobject_response, parse_as
        )
    else:
        return_function = response_json_only

    @soql_query(endpoint=endpoint, return_function=return_function)
    def _run_query() -> QueryProps:
        return {
            "client": client,
            "soql_query": soql,
        }

    return _run_query()
