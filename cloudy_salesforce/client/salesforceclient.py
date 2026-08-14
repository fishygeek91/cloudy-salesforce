import logging
from typing import Any

import requests
from requests.exceptions import HTTPError

from .auth import BaseAuthentication

logger = logging.getLogger(__name__)


class SalesforceClient:
    DEFAULT_API_VERSION = "v61.0"
    _default_instance = None

    def __init__(
        self,
        auth_strategy: BaseAuthentication,
        api_version: str = DEFAULT_API_VERSION,
    ):
        if not isinstance(auth_strategy, BaseAuthentication):
            raise TypeError(
                "auth_strategy must be an instance of a subclass of BaseAuthentication"
            )
        self.auth_strategy = auth_strategy
        self.api_version = api_version

        if self._default_instance is None:
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
        cls._default_instance = cls(auth_strategy, api_version=api_version)

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

    def get_session(self) -> requests.Session:
        return self.auth_strategy.session

    def get_instance_url(self) -> str:
        return self.auth_strategy.instance_url

    def request(
        self,
        method: str,
        url: str,
        body: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        request_url = f"{self.get_instance_url()}{url}"
        try:
            response = self.get_session().request(
                method, request_url, json=body, params=params, timeout=30
            )
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()

        except HTTPError as http_err:
            logger.error(f"HTTP error occurred during query: {http_err}")
            raise
        except Exception as err:
            logger.error(f"Other error occurred during query: {err}")
            raise
