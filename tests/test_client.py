from unittest.mock import MagicMock, patch

import requests

from cloudy_salesforce.client.auth import (
    BaseAuthentication,
    UsernamePasswordAuthentication,
)
from cloudy_salesforce.client.salesforceclient import SalesforceClient

SOAP_SUCCESS_XML = """<?xml version="1.0"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
  <soapenv:Body>
    <loginResponse>
      <result>
        <sessionId>SESSION</sessionId>
        <serverUrl>https://na1.salesforce.com/services/Soap/u/61.0</serverUrl>
      </result>
    </loginResponse>
  </soapenv:Body>
</soapenv:Envelope>
"""


class DummyAuth(BaseAuthentication):
    def __init__(self):
        super().__init__(requests.Session(), "https://example.my.salesforce.com")

    def authenticate(self):
        return self.session, self.instance_url


def test_request_empty_body_returns_empty_dict():
    auth = DummyAuth()
    client = SalesforceClient(auth)
    mock_response = MagicMock()
    mock_response.content = b""
    mock_response.raise_for_status = MagicMock()
    auth.session.request = MagicMock(return_value=mock_response)

    result = client.request("GET", "/services/data/v61.0/query")

    assert result == {}


def test_api_version_stored_on_client():
    auth = DummyAuth()
    client = SalesforceClient(auth, api_version="v59.0")
    assert client.api_version == "v59.0"


def test_request_keeps_absolute_url():
    auth = DummyAuth()
    client = SalesforceClient(auth)
    mock_response = MagicMock()
    mock_response.content = b"{}"
    mock_response.json.return_value = {}
    mock_response.raise_for_status = MagicMock()
    auth.session.request = MagicMock(return_value=mock_response)

    client.request("GET", "https://na1.salesforce.com/services/data/v61.0/query/next")

    assert (
        auth.session.request.call_args.args[1]
        == "https://na1.salesforce.com/services/data/v61.0/query/next"
    )


def test_authenticate_raises_when_soap_tags_missing():
    mock_response = MagicMock()
    mock_response.content = b"<loginResponse>no tokens here</loginResponse>"
    mock_response.raise_for_status = MagicMock()

    with patch("requests.Session.post", return_value=mock_response):
        try:
            UsernamePasswordAuthentication("user", "pass", "token")
        except ValueError as exc:
            assert "sessionId" in str(exc)
        else:
            raise AssertionError("expected ValueError for missing SOAP tags")


def test_username_password_authenticate_escapes_xml_in_credentials():
    mock_response = MagicMock()
    mock_response.content = SOAP_SUCCESS_XML.encode("utf-8")
    mock_response.raise_for_status = MagicMock()

    with patch("requests.Session.post", return_value=mock_response) as mock_post:
        UsernamePasswordAuthentication(
            username="a<b",
            password="p&w",
            security_token="t",
            login_url="https://login.salesforce.com",
            api_version="v61.0",
        )

    posted_body = mock_post.call_args.kwargs.get("data") or mock_post.call_args.args[1]
    assert "&lt;" in posted_body
    assert "<b" not in posted_body.split("<n1:password>")[0]
    assert "a&lt;b" in posted_body
