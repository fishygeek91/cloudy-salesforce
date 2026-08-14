import argparse
import json
import logging
import os

from dotenv import find_dotenv, load_dotenv

from cloudy_salesforce.client import UsernamePasswordAuthentication

from .generator import SObjectGenerator

logger = logging.getLogger(__name__)


def _get_login_url(alias: dict) -> str:
    if "login_url" in alias:
        return alias["login_url"]
    if alias.get("sandbox"):
        return "https://test.salesforce.com"
    return "https://login.salesforce.com"


def _get_auth(alias: dict) -> UsernamePasswordAuthentication:
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

        kwargs: dict[str, str] = {
            "username": username,
            "password": password,
            "security_token": security_token,
            "login_url": _get_login_url(alias),
        }
        if "api_version" in alias:
            kwargs["api_version"] = alias["api_version"]
        return UsernamePasswordAuthentication(**kwargs)

    raise ValueError(f"Auth type not supported yet: {alias['type']}")


def generate(args):
    """
    Handle the 'generate' command.
    """
    sobjects = args.sobjects
    alias_name = args.alias
    logger.info(
        "Generating code with sobjects=%s and alias=%s", sobjects, alias_name
    )

    try:
        with open(".cloudy_config", "r") as file:
            config = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(".cloudy_config not found")

    if not config or "auth" not in config:
        raise ValueError("Invalid .cloudy_config: missing auth section")

    auth_details = config["auth"]

    if alias_name == "default":
        alias_name = auth_details["default_alias"]

    alias = auth_details["aliases"][alias_name]
    auth = _get_auth(alias)

    generator = SObjectGenerator(auth)
    generator.generate_all(sobjects)


def main():
    parser = argparse.ArgumentParser(
        description="Generate typed Salesforce sObject dataclasses from org metadata.",
        usage="%(prog)s [command] [options]",
    )

    subparsers = parser.add_subparsers(title="Commands", dest="command")
    subparsers.required = True

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
