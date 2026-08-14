from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError

from cloudy_salesforce.client.auth import UsernamePasswordAuthentication
from cloudy_salesforce.client.salesforceclient import SalesforceClient
from cloudy_salesforce.exceptions import SalesforceError
from tests.conftest import DummyAuth

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


def _mock_http_error_response(
    *,
    status_code: int,
    content: bytes,
    json_side_effect: Exception | None = None,
    json_return: object | None = None,
) -> MagicMock:
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.content = content
    mock_response.text = content.decode("utf-8")
    if json_side_effect is not None:
        mock_response.json.side_effect = json_side_effect
    else:
        mock_response.json.return_value = json_return

    def raise_http_error() -> None:
        raise HTTPError(response=mock_response)

    mock_response.raise_for_status = MagicMock(side_effect=raise_http_error)
    return mock_response


def test_request_raises_salesforce_error_for_json_list_error_body():
    auth = DummyAuth()
    client = SalesforceClient(auth)
    error_body = [
        {"errorCode": "INVALID_FIELD", "message": "No such column"},
    ]
    mock_response = _mock_http_error_response(
        status_code=400,
        content=b'[{"errorCode": "INVALID_FIELD", "message": "No such column"}]',
        json_return=error_body,
    )
    auth.session.request = MagicMock(return_value=mock_response)

    with pytest.raises(SalesforceError) as exc_info:
        client.request("GET", "/services/data/v61.0/query")

    err = exc_info.value
    assert err.status_code == 400
    assert err.error_code == "INVALID_FIELD"
    assert err.message == "No such column"
    assert err.response_body == error_body
    assert "INVALID_FIELD" in str(err)
    assert "No such column" in str(err)


def test_request_raises_salesforce_error_for_non_json_error_body():
    auth = DummyAuth()
    client = SalesforceClient(auth)
    mock_response = _mock_http_error_response(
        status_code=400,
        content=b"not json",
        json_side_effect=ValueError("No JSON object could be decoded"),
    )
    auth.session.request = MagicMock(return_value=mock_response)

    with pytest.raises(SalesforceError) as exc_info:
        client.request("GET", "/services/data/v61.0/query")

    err = exc_info.value
    assert err.status_code == 400
    assert err.error_code is None
    assert err.message == "not json"
    assert err.response_body == "not json"
    assert "not json" in str(err)


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


def test_constructing_client_does_not_set_default():
    auth = DummyAuth()
    SalesforceClient._default_instance = None
    SalesforceClient(auth)
    assert SalesforceClient._default_instance is None


def test_constructing_client_with_default_true_sets_default():
    auth = DummyAuth()
    SalesforceClient._default_instance = None
    client = SalesforceClient(auth, default=True)
    assert SalesforceClient.get_default_instance() is client


def test_set_default_instance_sets_default():
    auth = DummyAuth()
    SalesforceClient._default_instance = None
    SalesforceClient.set_default_instance(auth)
    assert isinstance(SalesforceClient.get_default_instance(), SalesforceClient)
    assert SalesforceClient.get_default_instance().auth_strategy is auth


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
