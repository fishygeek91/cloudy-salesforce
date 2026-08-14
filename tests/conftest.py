import importlib

import pytest

from cloudy_salesforce.client.salesforceclient import SalesforceClient

sobject_mod = importlib.import_module("cloudy_salesforce.sobjects.sobject")


@pytest.fixture(autouse=True)
def isolate_sobject_registry():
    """Restore the global sObject registry after each test."""
    saved = sobject_mod._SObjectRegistry.copy()
    yield
    sobject_mod._SObjectRegistry.clear()
    sobject_mod._SObjectRegistry.update(saved)


@pytest.fixture(autouse=True)
def reset_default_client():
    """Reset SalesforceClient default instance after each test."""
    saved = SalesforceClient._default_instance
    yield
    SalesforceClient._default_instance = saved
