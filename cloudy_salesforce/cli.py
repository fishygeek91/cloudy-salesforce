"""Thin CLI dispatcher: init / generate / snapshot / diff."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from cloudy_salesforce.client.salesforceclient import SalesforceClient
from cloudy_salesforce.generator.cli import add_generate_parser, add_init_parser
from cloudy_salesforce.sentinel import (
    Snapshot,
    build_snapshot,
    default_out_path,
    diff_snapshots,
    format_slack,
    format_text,
    load_snapshot,
    resolve_sobject_names,
    write_snapshot,
)
from cloudy_salesforce.sobjects import SObjects

logger = logging.getLogger(__name__)


def _split_names(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    names = [name.strip() for name in raw.split(",") if name.strip()]
    return names or None


def _snapshot_live(
    alias: str,
    *,
    sobjects: str | None,
    all_custom: bool,
    api_version: str | None,
    sobject_names: list[str] | None = None,
    missing_ok: bool = False,
) -> Snapshot:
    """Snapshot the live org.

    ``sobject_names`` (when given) wins over ``sobjects``/``all_custom``/config
    resolution — the live-diff path passes the baseline's exact sObject set so a
    deleted object shows up as ``sobject_removed`` instead of describe noise.
    """
    client = SalesforceClient.from_config(alias=alias, api_version=api_version)
    explicit_names = _split_names(sobjects)
    if sobject_names is None:
        sobject_names = resolve_sobject_names(
            SObjects(sf_client=client),
            sobject_names=explicit_names,
            all_custom=all_custom,
        )
        # A typo in --sobjects should fail fast; a config-list object that was
        # deleted from the org should be treated as absent.
        missing_ok = missing_ok or explicit_names is None
    return build_snapshot(
        client, sobject_names, alias=alias, missing_ok=missing_ok
    )


def snapshot_command(args: argparse.Namespace) -> int:
    """Handle ``cloudy-salesforce snapshot``."""
    snapshot = _snapshot_live(
        args.alias,
        sobjects=args.sobjects,
        all_custom=args.all_custom,
        api_version=args.api_version,
    )
    out_path = args.out or default_out_path(args.alias)
    written = write_snapshot(snapshot, out_path)
    logger.info(
        "Snapshot of %d sObject(s) written to %s", len(snapshot["sobjects"]), written
    )
    return 0


def diff_command(args: argparse.Namespace) -> int:
    """Handle ``cloudy-salesforce diff``. Exit 0 when clean, 1 on changes."""
    old = load_snapshot(args.old)

    if args.new is not None and args.alias is not None:
        raise SystemExit("diff takes either a second snapshot file or --alias, not both")

    if args.new is not None:
        new = load_snapshot(args.new)
    elif args.alias is not None:
        # Reproduce the baseline's exact sObject set and API version so the
        # live diff reports schema drift, not set/version differences.
        new = _snapshot_live(
            args.alias,
            sobjects=None,
            all_custom=False,
            api_version=args.api_version or old["api_version"] or None,
            sobject_names=sorted(old["sobjects"]),
            missing_ok=True,
        )
    else:
        raise SystemExit("diff needs a second snapshot file or --alias")

    changes = diff_snapshots(old, new)
    if args.alias is not None and args.out:
        same_file = Path(args.out).resolve() == Path(args.old).resolve()
        if changes and same_file:
            logger.warning(
                "Not overwriting baseline %s while drift is unresolved; "
                "pass a different --out to keep the fresh snapshot.",
                args.old,
            )
        else:
            write_snapshot(new, args.out)
    if args.json:
        print(json.dumps([change.to_dict() for change in changes], indent=2))
    elif args.format == "slack":
        print(format_slack(changes))
    else:
        print(format_text(changes))
    return 1 if changes else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloudy-salesforce",
        description=(
            "Typed Salesforce codegen plus schema snapshots and drift diffs."
        ),
    )
    subparsers = parser.add_subparsers(title="Commands", dest="command")
    subparsers.required = True

    add_init_parser(subparsers)
    add_generate_parser(subparsers)

    snapshot_parser = subparsers.add_parser(
        "snapshot", help="Capture the org schema for the configured sObjects."
    )
    snapshot_parser.add_argument(
        "--alias", "-a", default="default", help="Auth alias from .cloudy_config."
    )
    snapshot_parser.add_argument(
        "--sobjects",
        default=None,
        help="Comma-separated sObject names (default: .cloudy_config sobjects list).",
    )
    snapshot_parser.add_argument(
        "--all-custom",
        action="store_true",
        help="Every __c object plus a small standard allowlist.",
    )
    snapshot_parser.add_argument(
        "--out",
        default=None,
        help="Output path (default: .schema-sentinel/{alias}.json).",
    )
    snapshot_parser.add_argument(
        "--api-version", default=None, help="Override REST API version."
    )
    snapshot_parser.set_defaults(handler=snapshot_command)

    diff_parser = subparsers.add_parser(
        "diff", help="Diff two snapshots, or a snapshot against the live org."
    )
    diff_parser.add_argument("old", help="Baseline snapshot JSON file.")
    diff_parser.add_argument(
        "new", nargs="?", default=None, help="Second snapshot JSON file."
    )
    diff_parser.add_argument(
        "--alias",
        "-a",
        default=None,
        help="Snapshot the live org under this alias and diff against it.",
    )
    diff_parser.add_argument(
        "--out",
        default=None,
        help=(
            "With --alias: also write the fresh snapshot here. Refuses to "
            "overwrite the baseline file while the diff reports changes."
        ),
    )
    diff_parser.add_argument(
        "--json", action="store_true", help="Print the machine-readable change set."
    )
    diff_parser.add_argument(
        "--format",
        choices=("text", "slack"),
        default="text",
        help="Human output format (default: text).",
    )
    diff_parser.add_argument(
        "--api-version", default=None, help="Override REST API version."
    )
    diff_parser.set_defaults(handler=diff_command)

    return parser


def main() -> None:
    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
        )
    parser = build_parser()
    args = parser.parse_args()
    handler = getattr(args, "handler", None)
    if handler is not None:
        sys.exit(handler(args))
    args.func(args)


if __name__ == "__main__":
    main()
