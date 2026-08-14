import importlib

import pytest
import requests

from cloudy_salesforce.client.auth import BaseAuthentication
from cloudy_salesforce.client.salesforceclient import SalesforceClient

sobject_mod = importlib.import_module("cloudy_salesforce.sobjects.sobject")


class DummyAuth(BaseAuthentication):
    def __init__(self):
        super().__init__(requests.Session(), "https://example.my.salesforce.com")

    def authenticate(self):
        return self.session, self.instance_url


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
