import logging
import threading
import time
from typing import Any, NoReturn

import requests
from requests.exceptions import HTTPError

from cloudy_salesforce.exceptions import SalesforceError

from .auth import BaseAuthentication, SessionAuthentication
from .config import build_auth_from_alias, load_cloudy_config, resolve_alias

logger = logging.getLogger(__name__)

_RATE_LIMIT_RETRY_DELAYS = (0.5, 1.0)


def _raise_salesforce_error(http_err: HTTPError) -> NoReturn:
    """Convert an HTTPError into a structured SalesforceError."""
    response = http_err.response
    status_code = response.status_code if response is not None else None

    if response is None:
        raise SalesforceError(
            str(http_err),
            status_code=status_code,
        ) from http_err

    try:
        body = response.json()
    except ValueError:
        raise SalesforceError(
            response.text or str(http_err),
            status_code=status_code,
            response_body=response.text,
        ) from http_err

    if isinstance(body, list) and body and isinstance(body[0], dict):
        entry = body[0]
        raise SalesforceError(
            entry.get("message", str(http_err)),
            status_code=status_code,
            error_code=entry.get("errorCode"),
            response_body=body,
        ) from http_err

    if isinstance(body, dict) and ("errorCode" in body or "message" in body):
        raise SalesforceError(
            body.get("message", str(http_err)),
            status_code=status_code,
            error_code=body.get("errorCode"),
            response_body=body,
        ) from http_err

    raise SalesforceError(
        str(http_err),
        status_code=status_code,
        response_body=body,
    ) from http_err


def _extract_error_code(http_err: HTTPError) -> str | None:
    response = http_err.response
    if response is None:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, list) and body and isinstance(body[0], dict):
        return body[0].get("errorCode")
    if isinstance(body, dict):
        return body.get("errorCode")
    return None


def _is_rate_limited(http_err: HTTPError) -> bool:
    response = http_err.response
    if response is not None and response.status_code == 429:
        return True
    return _extract_error_code(http_err) == "REQUEST_LIMIT_EXCEEDED"


class SalesforceClient:
    DEFAULT_API_VERSION = "v61.0"
    _default_instance = None

    def __init__(
        self,
        auth_strategy: BaseAuthentication,
        api_version: str = DEFAULT_API_VERSION,
        *,
        default: bool = False,
        retries: int = 2,
        timeout: float = 30.0,
    ) -> None:
        if not isinstance(auth_strategy, BaseAuthentication):
            raise TypeError(
                "auth_strategy must be an instance of a subclass of BaseAuthentication"
            )
        if retries < 0:
            raise ValueError("retries must be >= 0")
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self.auth_strategy = auth_strategy
        self.api_version = api_version
        self._retries = retries
        self._timeout = timeout
        self._auth_lock = threading.Lock()

        if default:
            self.__class__._default_instance = self

    @classmethod
    def set_default_instance(
        cls,
        auth_strategy: BaseAuthentication,
        api_version: str = DEFAULT_API_VERSION,
    ):
        """
        Sets the default SalesforceClient instance.

        :param auth_strategy: An instance of a subclass of BaseAuthentication.
        :param api_version: Salesforce REST API version (e.g. "v61.0").
        """
        cls(auth_strategy, api_version=api_version, default=True)

    @classmethod
    def get_default_instance(cls):
        """
        Retrieves the default SalesforceClient instance.

        :return: The default SalesforceClient instance.
        :raises ValueError: If the default instance has not been set.
        """
        if cls._default_instance is None:
            raise ValueError("Default instance not set")
        return cls._default_instance

    @classmethod
    def from_config(
        cls,
        alias: str = "default",
        path: str = ".cloudy_config",
        *,
        default: bool = False,
        api_version: str | None = None,
    ) -> "SalesforceClient":
        config = load_cloudy_config(path)
        alias_config = resolve_alias(config, alias)

        effective_api_version = api_version
        if effective_api_version is None:
            effective_api_version = alias_config.get(
                "api_version", cls.DEFAULT_API_VERSION
            )

        auth = build_auth_from_alias(
            alias_config, api_version=effective_api_version
        )
        return cls(
            auth,
            api_version=effective_api_version,
            default=default,
        )

    def get_session(self) -> requests.Session:
        return self.auth_strategy.session

    def get_instance_url(self) -> str:
        return self.auth_strategy.instance_url

    def _can_reauthenticate(self) -> bool:
        """Return True when the auth strategy can obtain a fresh session."""
        return not isinstance(self.auth_strategy, SessionAuthentication)

    def _reauthenticate(self) -> None:
        """Refresh session and instance URL from the auth strategy."""
        with self._auth_lock:
            session, instance_url = self.auth_strategy.authenticate()
            self.auth_strategy.session = session
            self.auth_strategy.instance_url = instance_url

    @staticmethod
    def _retry_after_seconds(http_err: HTTPError, fallback: float) -> float:
        """Parse Retry-After header, capped at 30 seconds, or return fallback."""
        response = http_err.response
        if response is None:
            return fallback
        raw = response.headers.get("Retry-After")
        if raw is None:
            return fallback
        if isinstance(raw, (int, float)):
            delay = float(raw)
        elif isinstance(raw, str):
            try:
                delay = float(raw)
            except ValueError:
                return fallback
        else:
            return fallback
        if delay < 0:
            return fallback
        return min(delay, 30.0)

    def request(
        self,
        method: str,
        url: str,
        body: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        reauthenticated = False
        rate_limit_attempt = 0

        while True:
            if url.startswith("http://") or url.startswith("https://"):
                request_url = url
            else:
                request_url = f"{self.get_instance_url()}{url}"
            try:
                response = self.get_session().request(
                    method,
                    request_url,
                    json=body,
                    params=params,
                    timeout=self._timeout,
                )
                response.raise_for_status()
                if not response.content:
                    return {}
                return response.json()

            except HTTPError as http_err:
                if (
                    _extract_error_code(http_err) == "INVALID_SESSION_ID"
                    and self._can_reauthenticate()
                    and not reauthenticated
                ):
                    self._reauthenticate()
                    reauthenticated = True
                    continue

                if _is_rate_limited(http_err) and rate_limit_attempt < self._retries:
                    delay_index = min(
                        rate_limit_attempt, len(_RATE_LIMIT_RETRY_DELAYS) - 1
                    )
                    fallback = _RATE_LIMIT_RETRY_DELAYS[delay_index]
                    time.sleep(self._retry_after_seconds(http_err, fallback))
                    rate_limit_attempt += 1
                    continue

                logger.error(f"HTTP error occurred during query: {http_err}")
                _raise_salesforce_error(http_err)
            except Exception as err:
                logger.error(f"Other error occurred during query: {err}")
                raise
