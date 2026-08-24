"""Typed Salesforce client with query, CRUD, and codegen."""

from cloudy_salesforce.client import (
    JwtBearerAuthentication,
    SalesforceClient,
    SessionAuthentication,
    UsernamePasswordAuthentication,
)
from cloudy_salesforce.collections import DmlResult, delete, insert, update, upsert
from cloudy_salesforce.exceptions import SalesforceError
from cloudy_salesforce.query import SoqlQuery, query, select, soql_query
from cloudy_salesforce.sobjects import SObjects, parse_sobject_response, sobject
from cloudy_salesforce.types import UNSET, UnsetType

__version__ = "0.4.0"

__all__ = [
    "SalesforceClient",
    "UsernamePasswordAuthentication",
    "JwtBearerAuthentication",
    "SessionAuthentication",
    "query",
    "select",
    "SoqlQuery",
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
    "UNSET",
    "UnsetType",
    "__version__",
]
