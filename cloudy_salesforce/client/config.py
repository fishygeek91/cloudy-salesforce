"""Load `.cloudy_config` and build authentication from alias definitions."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from .auth import UsernamePasswordAuthentication

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
      }
    }
  },
  "sobjects": ["Account", "Contact", "Opportunity"]
}
"""

DEFAULT_ENV_EXAMPLE = """SF_USERNAME=
SF_PASSWORD=
SF_SECURITY_TOKEN=
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


def build_auth_from_alias(
    alias: dict,
    *,
    api_version: str | None = None,
) -> UsernamePasswordAuthentication:
    if alias["type"] == "basic":
        load_dotenv(dotenv_path=find_dotenv(raise_error_if_not_found=True))
        credentials = alias["credentials"]
        username_var = credentials["username"]
        password_var = credentials["password"]
        token_var = credentials["security_token"]

        username = os.getenv(username_var)
        password = os.getenv(password_var)
        security_token = os.environ.get(token_var)

        for var_name, value in [
            (username_var, username),
            (password_var, password),
            (token_var, security_token),
        ]:
            if value is None:
                raise ValueError(f"Missing required environment variable: {var_name}")

        assert username is not None
        assert password is not None
        assert security_token is not None

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

    raise ValueError(f"Auth type not supported yet: {alias['type']}")
