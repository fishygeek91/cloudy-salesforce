import json
from unittest.mock import MagicMock, patch

from cloudy_salesforce.client.auth import (
    JWT_BEARER_GRANT_TYPE,
    JwtBearerAuthentication,
    SessionAuthentication,
)
from cloudy_salesforce.client.config import build_auth_from_alias
from cloudy_salesforce.client.salesforceclient import SalesforceClient
from tests.conftest import DummyAuth
from tests.test_client import _mock_http_error_response


def test_session_authentication_sets_bearer_header_and_instance_url():
    auth = SessionAuthentication("my-token", "https://na1.salesforce.com")

    assert auth.instance_url == "https://na1.salesforce.com"
    assert auth.session.headers["Authorization"] == "Bearer my-token"
    assert auth.session.headers["Content-Type"] == "application/json"

    session, instance_url = auth.authenticate()
    assert session is auth.session
    assert instance_url == "https://na1.salesforce.com"


@patch("cloudy_salesforce.client.auth.jwt.encode", return_value="signed-jwt")
@patch("requests.Session.post")
def test_jwt_bearer_authentication_posts_jwt_assertion(mock_post, mock_encode):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "token123",
        "instance_url": "https://na1.salesforce.com",
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    auth = JwtBearerAuthentication(
        client_id="client-id",
        username="user@example.com",
        private_key="fake-pem-key",
        login_url="https://login.salesforce.com",
    )

    mock_post.assert_called_once()
    posted_url = mock_post.call_args.args[0]
    posted_data = mock_post.call_args.kwargs["data"]
    assert posted_url == "https://login.salesforce.com/services/oauth2/token"
    assert posted_data["grant_type"] == JWT_BEARER_GRANT_TYPE
    assert posted_data["assertion"] == "signed-jwt"
    mock_encode.assert_called_once()
    encode_kwargs = mock_encode.call_args.kwargs
    assert encode_kwargs["algorithm"] == "RS256"
    payload = mock_encode.call_args.args[0]
    assert payload["iss"] == "client-id"
    assert payload["sub"] == "user@example.com"
    assert payload["aud"] == "https://login.salesforce.com"
    assert auth.instance_url == "https://na1.salesforce.com"
    assert auth.session.headers["Authorization"] == "Bearer token123"


def test_build_auth_from_alias_jwt(monkeypatch):
    monkeypatch.setenv("SF_CLIENT_ID", "client-id")
    monkeypatch.setenv("SF_USERNAME", "user@example.com")
    monkeypatch.setenv("SF_PRIVATE_KEY", "pem-key")

    alias = {
        "type": "jwt",
        "login_url": "https://login.salesforce.com",
        "credentials": {
            "client_id": "SF_CLIENT_ID",
            "username": "SF_USERNAME",
            "private_key": "SF_PRIVATE_KEY",
        },
    }

    with patch("cloudy_salesforce.client.config.find_dotenv", return_value=".env"):
        with patch("cloudy_salesforce.client.config.load_dotenv"):
            with patch(
                "cloudy_salesforce.client.config.JwtBearerAuthentication"
            ) as mock_jwt_auth:
                mock_jwt_auth.return_value = DummyAuth()
                auth = build_auth_from_alias(alias)

    mock_jwt_auth.assert_called_once_with(
        client_id="client-id",
        username="user@example.com",
        login_url="https://login.salesforce.com",
        private_key="pem-key",
    )
    assert isinstance(auth, DummyAuth)


def test_build_auth_from_alias_session(monkeypatch):
    monkeypatch.setenv("SF_ACCESS_TOKEN", "access-token")
    monkeypatch.setenv("SF_INSTANCE_URL", "https://na1.salesforce.com")

    alias = {
        "type": "session",
        "credentials": {
            "access_token": "SF_ACCESS_TOKEN",
            "instance_url": "SF_INSTANCE_URL",
        },
    }

    with patch("cloudy_salesforce.client.config.find_dotenv", return_value=".env"):
        with patch("cloudy_salesforce.client.config.load_dotenv"):
            with patch(
                "cloudy_salesforce.client.config.SessionAuthentication"
            ) as mock_session_auth:
                mock_session_auth.return_value = DummyAuth()
                auth = build_auth_from_alias(alias)

    mock_session_auth.assert_called_once_with(
        "access-token",
        "https://na1.salesforce.com",
    )
    assert isinstance(auth, DummyAuth)


@patch("cloudy_salesforce.client.salesforceclient.time.sleep")
def test_request_retries_on_429_then_succeeds(mock_sleep):
    auth = DummyAuth()
    client = SalesforceClient(auth)

    success_response = MagicMock()
    success_response.content = b'{"ok": true}'
    success_response.json.return_value = {"ok": True}
    success_response.raise_for_status = MagicMock()

    rate_limit_response = _mock_http_error_response(
        status_code=429,
        content=b"{}",
        json_return={},
    )

    auth.session.request = MagicMock(
        side_effect=[rate_limit_response, success_response]
    )

    result = client.request("GET", "/services/data/v61.0/query")

    assert result == {"ok": True}
    assert auth.session.request.call_count == 2
    mock_sleep.assert_called_once_with(0.5)


@patch("cloudy_salesforce.client.salesforceclient.time.sleep")
def test_request_retries_on_request_limit_exceeded_then_succeeds(mock_sleep):
    auth = DummyAuth()
    client = SalesforceClient(auth)

    success_response = MagicMock()
    success_response.content = b'{"ok": true}'
    success_response.json.return_value = {"ok": True}
    success_response.raise_for_status = MagicMock()

    limit_response = _mock_http_error_response(
        status_code=403,
        content=json.dumps(
            [{"errorCode": "REQUEST_LIMIT_EXCEEDED", "message": "Limit exceeded"}]
        ).encode("utf-8"),
        json_return=[
            {"errorCode": "REQUEST_LIMIT_EXCEEDED", "message": "Limit exceeded"}
        ],
    )

    auth.session.request = MagicMock(side_effect=[limit_response, success_response])

    result = client.request("GET", "/services/data/v61.0/query")

    assert result == {"ok": True}
    assert auth.session.request.call_count == 2
    mock_sleep.assert_called_once_with(0.5)
