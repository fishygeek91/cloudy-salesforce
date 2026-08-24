"""Load `.cloudy_config` and build authentication from alias definitions."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from .auth import (
    BaseAuthentication,
    JwtBearerAuthentication,
    SessionAuthentication,
    UsernamePasswordAuthentication,
)

DEFAULT_CLOUDY_CONFIG_PATH = ".cloudy_config"

DEFAULT_CLOUDY_CONFIG_EXAMPLE = """{
  "auth": {
    "default_alias": "prod",
    "aliases": {
      "prod": {
        "type": "basic",
        "login_url": "https://login.salesforce.com",
        "credentials": {
          "username": "SF_USERNAME",
          "password": "SF_PASSWORD",
          "security_token": "SF_SECURITY_TOKEN"
        }
      },
      "sandbox": {
        "type": "basic",
        "sandbox": true,
        "credentials": {
          "username": "SF_USERNAME",
          "password": "SF_PASSWORD",
          "security_token": "SF_SECURITY_TOKEN"
        }
      },
      "jwt": {
        "type": "jwt",
        "login_url": "https://login.salesforce.com",
        "credentials": {
          "client_id": "SF_CLIENT_ID",
          "username": "SF_USERNAME",
          "private_key": "SF_PRIVATE_KEY"
        }
      },
      "session": {
        "type": "session",
        "credentials": {
          "access_token": "SF_ACCESS_TOKEN",
          "instance_url": "SF_INSTANCE_URL"
        }
      }
    }
  },
  "sobjects": ["Account", "Contact", "Opportunity"]
}
"""

DEFAULT_ENV_EXAMPLE = """SF_USERNAME=
SF_PASSWORD=
SF_SECURITY_TOKEN=
SF_CLIENT_ID=
SF_PRIVATE_KEY=
SF_ACCESS_TOKEN=
SF_INSTANCE_URL=
"""


def get_login_url(alias: dict) -> str:
    if "login_url" in alias:
        return alias["login_url"]
    if alias.get("sandbox"):
        return "https://test.salesforce.com"
    return "https://login.salesforce.com"


def load_cloudy_config(path: str = DEFAULT_CLOUDY_CONFIG_PATH) -> dict:
    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"{path} not found") from None

    if not config or "auth" not in config:
        raise ValueError("Invalid .cloudy_config: missing auth section")

    return config


def resolve_alias(config: dict, alias_name: str) -> dict:
    auth_details = config["auth"]
    if alias_name == "default":
        alias_name = auth_details["default_alias"]

    aliases = auth_details.get("aliases")
    if not aliases or alias_name not in aliases:
        raise ValueError(f"Unknown auth alias: {alias_name}")

    return aliases[alias_name]


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if value is None:
        raise ValueError(f"Missing required environment variable: {var_name}")
    return value


def build_auth_from_alias(
    alias: dict,
    *,
    api_version: str | None = None,
) -> BaseAuthentication:
    """Build authentication from a `.cloudy_config` alias definition.

    Optional `.env` is loaded once from the current working directory when present;
    missing `.env` is allowed when required variables are already in the environment.
    """
    load_dotenv(dotenv_path=find_dotenv(usecwd=True), override=False)

    if alias["type"] == "basic":
        credentials = alias["credentials"]
        username_var = credentials["username"]
        password_var = credentials["password"]
        token_var = credentials["security_token"]

        username = _require_env(username_var)
        password = _require_env(password_var)
        security_token = _require_env(token_var)

        kwargs: dict[str, str] = {
            "username": username,
            "password": password,
            "security_token": security_token,
            "login_url": get_login_url(alias),
        }
        effective_api_version = api_version or alias.get("api_version")
        if effective_api_version is not None:
            kwargs["api_version"] = effective_api_version
        return UsernamePasswordAuthentication(**kwargs)

    if alias["type"] == "jwt":
        credentials = alias["credentials"]
        client_id = _require_env(credentials["client_id"])
        username = _require_env(credentials["username"])

        jwt_kwargs: dict[str, str] = {
            "client_id": client_id,
            "username": username,
            "login_url": get_login_url(alias),
        }
        if "private_key_path" in credentials:
            jwt_kwargs["private_key_path"] = credentials["private_key_path"]
        else:
            jwt_kwargs["private_key"] = _require_env(credentials["private_key"])
        return JwtBearerAuthentication(**jwt_kwargs)

    if alias["type"] == "session":
        credentials = alias["credentials"]
        access_token = _require_env(credentials["access_token"])
        instance_url = _require_env(credentials["instance_url"])
        return SessionAuthentication(access_token, instance_url)

    raise ValueError(f"Auth type not supported yet: {alias['type']}")
