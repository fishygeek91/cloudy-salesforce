import argparse
import logging
from pathlib import Path

from cloudy_salesforce.client.config import (
    DEFAULT_CLOUDY_CONFIG_EXAMPLE,
    DEFAULT_ENV_EXAMPLE,
    build_auth_from_alias,
    load_cloudy_config,
    resolve_alias,
)

from .generator import SObjectGenerator

logger = logging.getLogger(__name__)


def generate(args):
    """
    Handle the 'generate' command.
    """
    sobjects = args.sobjects
    alias_name = args.alias
    logger.info(
        "Generating code with sobjects=%s and alias=%s", sobjects, alias_name
    )

    config = load_cloudy_config()
    alias = resolve_alias(config, alias_name)
    auth = build_auth_from_alias(alias)

    generator = SObjectGenerator(auth)
    generator.generate_all(sobjects)


def init(args):
    """
    Handle the 'init' command.
    """
    force = args.force
    config_path = Path(".cloudy_config")
    env_example_path = Path(".env.example")

    example_config_path = Path(".cloudy_config.example")
    if example_config_path.is_file():
        config_content = example_config_path.read_text(encoding="utf-8")
    else:
        config_content = DEFAULT_CLOUDY_CONFIG_EXAMPLE

    if not config_path.exists() or force:
        config_path.write_text(config_content, encoding="utf-8")
        logger.info("Wrote %s", config_path)
    else:
        logger.info("%s already exists (use --force to overwrite)", config_path)

    if not env_example_path.exists() or force:
        env_example_path.write_text(DEFAULT_ENV_EXAMPLE, encoding="utf-8")
        logger.info("Wrote %s", env_example_path)
    else:
        logger.info(
            "%s already exists (use --force to overwrite)", env_example_path
        )


def main():
    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
        )

    parser = argparse.ArgumentParser(
        description="Generate typed Salesforce sObject dataclasses from org metadata.",
        usage="%(prog)s [command] [options]",
    )

    subparsers = parser.add_subparsers(title="Commands", dest="command")
    subparsers.required = True

    init_parser = subparsers.add_parser(
        "init", help="Create .cloudy_config and .env.example starter files."
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing .cloudy_config and .env.example files.",
    )
    init_parser.set_defaults(func=init)

    generate_parser = subparsers.add_parser(
        "generate", help="Generate code based on provided options."
    )
    generate_parser.add_argument(
        "--sobjects",
        "-sob",
        default=None,
        help="(Optional) Enter a list of sobject names or a single sobject name",
    )
    generate_parser.add_argument(
        "--alias",
        "-a",
        default="default",
        help="Auth alias from .cloudy_config (default: the config default_alias)",
    )
    generate_parser.set_defaults(func=generate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
