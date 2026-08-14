import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cloudy_salesforce.client.config import DEFAULT_CLOUDY_CONFIG_EXAMPLE
from cloudy_salesforce.client.salesforceclient import SalesforceClient
from cloudy_salesforce.generator.cli import main
from tests.conftest import DummyAuth


def _write_cloudy_config(tmp_path: Path, *, alias: str = "prod") -> None:
    config = {
        "auth": {
            "default_alias": alias,
            "aliases": {
                alias: {
                    "type": "basic",
                    "login_url": "https://login.salesforce.com",
                    "credentials": {
                        "username": "SF_USERNAME",
                        "password": "SF_PASSWORD",
                        "security_token": "SF_SECURITY_TOKEN",
                    },
                }
            },
        }
    }
    (tmp_path / ".cloudy_config").write_text(json.dumps(config), encoding="utf-8")


def test_main_help_exits_zero(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cloudy-salesforce", "generate", "--help"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0


def test_main_configures_logging_when_no_handlers(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cloudy-salesforce", "generate", "--help"])
    monkeypatch.setattr(logging.root, "handlers", [])
    with patch("logging.basicConfig") as mock_basic_config:
        with pytest.raises(SystemExit):
            main()
        mock_basic_config.assert_called_once_with(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
        )


def test_generate_raises_without_cloudy_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["cloudy-salesforce", "generate"])
    with pytest.raises(FileNotFoundError, match=r"\.cloudy_config not found"):
        main()


def test_init_creates_config_and_env_example(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["cloudy-salesforce", "init"])
    with caplog.at_level(logging.INFO):
        main()

    config_path = tmp_path / ".cloudy_config"
    env_example_path = tmp_path / ".env.example"
    assert config_path.is_file()
    assert env_example_path.is_file()
    assert json.loads(config_path.read_text(encoding="utf-8")) == json.loads(
        DEFAULT_CLOUDY_CONFIG_EXAMPLE
    )
    assert env_example_path.read_text(encoding="utf-8") == (
        "SF_USERNAME=\n"
        "SF_PASSWORD=\n"
        "SF_SECURITY_TOKEN=\n"
        "SF_CLIENT_ID=\n"
        "SF_PRIVATE_KEY=\n"
        "SF_ACCESS_TOKEN=\n"
        "SF_INSTANCE_URL=\n"
    )
    assert "Wrote .cloudy_config" in caplog.text
    assert "Wrote .env.example" in caplog.text


def test_init_without_force_leaves_existing_config(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / ".cloudy_config"
    config_path.write_text('{"auth": {"keep": true}}', encoding="utf-8")
    (tmp_path / ".env.example").write_text("EXISTING=1\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["cloudy-salesforce", "init"])
    with caplog.at_level(logging.INFO):
        main()

    assert config_path.read_text(encoding="utf-8") == '{"auth": {"keep": true}}'
    assert (tmp_path / ".env.example").read_text(encoding="utf-8") == "EXISTING=1\n"
    assert "already exists" in caplog.text


def test_init_force_overwrites_existing_files(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / ".cloudy_config"
    env_example_path = tmp_path / ".env.example"
    config_path.write_text('{"auth": {"keep": true}}', encoding="utf-8")
    env_example_path.write_text("EXISTING=1\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["cloudy-salesforce", "init", "--force"])
    with caplog.at_level(logging.INFO):
        main()

    assert json.loads(config_path.read_text(encoding="utf-8")) == json.loads(
        DEFAULT_CLOUDY_CONFIG_EXAMPLE
    )
    assert env_example_path.read_text(encoding="utf-8") == (
        "SF_USERNAME=\n"
        "SF_PASSWORD=\n"
        "SF_SECURITY_TOKEN=\n"
        "SF_CLIENT_ID=\n"
        "SF_PRIVATE_KEY=\n"
        "SF_ACCESS_TOKEN=\n"
        "SF_INSTANCE_URL=\n"
    )
    assert "Wrote .cloudy_config" in caplog.text
    assert "Wrote .env.example" in caplog.text


def test_from_config_builds_client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_cloudy_config(tmp_path)
    monkeypatch.setenv("SF_USERNAME", "user@example.com")
    monkeypatch.setenv("SF_PASSWORD", "secret")
    monkeypatch.setenv("SF_SECURITY_TOKEN", "token")

    mock_auth = DummyAuth()
    with patch(
        "cloudy_salesforce.client.salesforceclient.build_auth_from_alias",
        return_value=mock_auth,
    ):
        client = SalesforceClient.from_config(alias="prod")

    assert client.auth_strategy is mock_auth
    assert client.api_version == SalesforceClient.DEFAULT_API_VERSION


def test_from_config_uses_alias_api_version(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = {
        "auth": {
            "default_alias": "prod",
            "aliases": {
                "prod": {
                    "type": "basic",
                    "api_version": "v59.0",
                    "credentials": {
                        "username": "SF_USERNAME",
                        "password": "SF_PASSWORD",
                        "security_token": "SF_SECURITY_TOKEN",
                    },
                }
            },
        }
    }
    (tmp_path / ".cloudy_config").write_text(json.dumps(config), encoding="utf-8")

    mock_auth = DummyAuth()
    with patch(
        "cloudy_salesforce.client.salesforceclient.build_auth_from_alias",
        return_value=mock_auth,
    ) as mock_build:
        client = SalesforceClient.from_config(alias="prod")

    assert client.api_version == "v59.0"
    mock_build.assert_called_once()
    assert mock_build.call_args.kwargs["api_version"] == "v59.0"


def test_from_config_api_version_kwarg_overrides_alias(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = {
        "auth": {
            "default_alias": "prod",
            "aliases": {
                "prod": {
                    "type": "basic",
                    "api_version": "v59.0",
                    "credentials": {
                        "username": "SF_USERNAME",
                        "password": "SF_PASSWORD",
                        "security_token": "SF_SECURITY_TOKEN",
                    },
                }
            },
        }
    }
    (tmp_path / ".cloudy_config").write_text(json.dumps(config), encoding="utf-8")

    mock_auth = DummyAuth()
    with patch(
        "cloudy_salesforce.client.salesforceclient.build_auth_from_alias",
        return_value=mock_auth,
    ) as mock_build:
        client = SalesforceClient.from_config(alias="prod", api_version="v62.0")

    assert client.api_version == "v62.0"
    mock_build.assert_called_once()
    assert mock_build.call_args.kwargs["api_version"] == "v62.0"


def test_from_config_missing_env_var_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_cloudy_config(tmp_path)
    monkeypatch.delenv("SF_USERNAME", raising=False)
    monkeypatch.delenv("SF_PASSWORD", raising=False)
    monkeypatch.delenv("SF_SECURITY_TOKEN", raising=False)

    with patch("cloudy_salesforce.client.config.find_dotenv", return_value=".env"):
        with patch("cloudy_salesforce.client.config.load_dotenv"):
            with pytest.raises(
                ValueError, match="Missing required environment variable: SF_USERNAME"
            ):
                SalesforceClient.from_config(alias="prod")


def test_from_config_unknown_alias_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_cloudy_config(tmp_path)

    with pytest.raises(ValueError, match="Unknown auth alias: missing"):
        SalesforceClient.from_config(alias="missing")


def test_from_config_missing_file_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match=r"\.cloudy_config not found"):
        SalesforceClient.from_config()


def test_from_config_default_true_registers_instance(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_cloudy_config(tmp_path)
    SalesforceClient._default_instance = None

    mock_auth = DummyAuth()
    with patch(
        "cloudy_salesforce.client.salesforceclient.build_auth_from_alias",
        return_value=mock_auth,
    ):
        client = SalesforceClient.from_config(alias="prod", default=True)

    assert SalesforceClient.get_default_instance() is client
