import logging
import sys
from unittest.mock import patch

import pytest

from cloudy_salesforce.generator.cli import main


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
