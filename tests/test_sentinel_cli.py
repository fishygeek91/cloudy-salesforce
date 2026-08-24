"""CLI tests: diff exit codes, --json, snapshot wiring, preserved subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cloudy_salesforce import cli

FIXTURES = Path(__file__).parent.parent / "examples" / "snapshots"


def _run(argv: list[str]) -> int:
    parser = cli.build_parser()
    args = parser.parse_args(argv)
    result = args.handler(args)
    assert isinstance(result, int)
    return result


def test_diff_exit_zero_when_identical(capsys):
    base = str(FIXTURES / "base.json")
    assert _run(["diff", base, base]) == 0
    assert "No schema changes." in capsys.readouterr().out


def test_diff_exit_one_on_changes(capsys):
    code = _run(["diff", str(FIXTURES / "base.json"), str(FIXTURES / "drifted.json")])
    assert code == 1
    out = capsys.readouterr().out
    assert 'Account.Industry: picklist value "Banking" removed' in out


def test_diff_json_output(capsys):
    code = _run(
        ["diff", str(FIXTURES / "base.json"), str(FIXTURES / "drifted.json"), "--json"]
    )
    assert code == 1
    decoded = json.loads(capsys.readouterr().out)
    assert {entry["kind"] for entry in decoded} == {
        "picklist_values_removed",
        "type_changed",
        "length_changed",
        "field_removed",
    }


def test_diff_slack_format(capsys):
    code = _run(
        [
            "diff",
            str(FIXTURES / "base.json"),
            str(FIXTURES / "drifted.json"),
            "--format",
            "slack",
        ]
    )
    assert code == 1
    assert capsys.readouterr().out.startswith("*4 Salesforce schema change(s)")


def test_diff_requires_second_source():
    parser = cli.build_parser()
    args = parser.parse_args(["diff", str(FIXTURES / "base.json")])
    with pytest.raises(SystemExit):
        args.handler(args)


def test_diff_rejects_file_and_alias_together():
    parser = cli.build_parser()
    args = parser.parse_args(
        ["diff", str(FIXTURES / "base.json"), str(FIXTURES / "base.json"), "--alias", "prod"]
    )
    with pytest.raises(SystemExit):
        args.handler(args)


def test_diff_live_uses_alias_and_writes_out(tmp_path, monkeypatch, capsys):
    fresh = json.loads((FIXTURES / "drifted.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(
        cli, "_snapshot_live", MagicMock(return_value=fresh)
    )
    out = tmp_path / "prod.json"
    code = _run(
        ["diff", str(FIXTURES / "base.json"), "--alias", "prod", "--out", str(out)]
    )
    assert code == 1
    cli._snapshot_live.assert_called_once_with(
        "prod", sobjects=None, all_custom=False, api_version=None
    )
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(
        json.dumps(fresh, sort_keys=True)
    )


def test_snapshot_command_writes_default_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fresh = json.loads((FIXTURES / "base.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(cli, "_snapshot_live", MagicMock(return_value=fresh))
    assert _run(["snapshot", "--alias", "prod"]) == 0
    written = tmp_path / ".schema-sentinel" / "prod.json"
    assert written.is_file()
    assert json.loads(written.read_text(encoding="utf-8"))["alias"] == "prod"


def test_snapshot_command_passes_flags(monkeypatch, tmp_path):
    fresh = json.loads((FIXTURES / "base.json").read_text(encoding="utf-8"))
    mock = MagicMock(return_value=fresh)
    monkeypatch.setattr(cli, "_snapshot_live", mock)
    out = tmp_path / "s.json"
    code = _run(
        [
            "snapshot",
            "--alias",
            "sandbox",
            "--sobjects",
            "Account, Contact",
            "--all-custom",
            "--api-version",
            "v62.0",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    mock.assert_called_once_with(
        "sandbox",
        sobjects="Account, Contact",
        all_custom=True,
        api_version="v62.0",
    )
    assert out.is_file()


def test_split_names():
    assert cli._split_names(None) is None
    assert cli._split_names(" ") is None
    assert cli._split_names("Account, Contact,,") == ["Account", "Contact"]


def test_init_and_generate_still_registered():
    parser = cli.build_parser()
    init_args = parser.parse_args(["init"])
    assert init_args.func.__name__ == "init"
    gen_args = parser.parse_args(["generate", "--alias", "prod", "--out", "x"])
    assert gen_args.func.__name__ == "generate"
    assert gen_args.out == "x"
