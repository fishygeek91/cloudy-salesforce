import logging
from typing import Any, Dict, List, Tuple, TypeVar

from .types import DmlResult

logger = logging.getLogger(__name__)

T = TypeVar("T")


def dml_results_only(records: List[Dict[str, Any]], results: T) -> T:
    return results


def build_dml_results(
    records: List[Dict[str, Any]], results: List[Dict[str, Any]]
) -> List[DmlResult]:
    dml_results: List[DmlResult] = []
    for record, response in zip(records, results):
        dml_results.append(
            DmlResult(
                id=response.get("id"),
                success=response["success"],
                errors=response.get("errors", []),
                created=response.get("created"),
                record=record,
            )
        )
    return dml_results


def records_and_response(
    records: List[Dict[str, Any]], results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    parsed_results: List[Dict[str, Any]] = []
    for record, response in zip(records, results):
        record_result = {"record": record, "response": response}
        parsed_results.append(record_result)

    return parsed_results


def success_failure(
    records: List[Dict[str, Any]], results: List[Dict[str, Any]]
) -> Tuple[Dict, Dict]:
    successes: Dict[str, Any] = {"count": 0, "results": []}
    failures: Dict[str, Any] = {"count": 0, "results": []}
    for record, response in zip(records, results):
        record_result = {"record": record, "response": response}
        if not response["success"]:
            failures["count"] += 1
            failures["results"].append(record_result)
        else:
            successes["count"] += 1
            successes["results"].append(record_result)

    logger.info("---Results for dml:---")
    logger.info(f"Successes: {successes['count']}")
    logger.info(f"Failures: {failures['count']}")
    return successes, failures
