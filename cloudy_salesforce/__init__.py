"""Typed Salesforce client with query, CRUD, and codegen."""

from cloudy_salesforce.client import SalesforceClient, UsernamePasswordAuthentication
from cloudy_salesforce.collections import DmlResult, delete, insert, update, upsert
from cloudy_salesforce.exceptions import SalesforceError
from cloudy_salesforce.query import query, soql_query
from cloudy_salesforce.sobjects import SObjects, parse_sobject_response, sobject

__version__ = "0.2.0"

__all__ = [
    "SalesforceClient",
    "UsernamePasswordAuthentication",
    "query",
    "soql_query",
    "insert",
    "update",
    "upsert",
    "delete",
    "DmlResult",
    "SalesforceError",
    "sobject",
    "SObjects",
    "parse_sobject_response",
    "__version__",
]
