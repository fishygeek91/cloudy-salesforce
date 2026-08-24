# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-08-24

### Added

- `cloudy-salesforce generate --out` and `--api-version`
- `SObjects.describe_global()`
- `SalesforceClient` `retries=` and `timeout=`
- `UNSET` / `UnsetType` sentinel for omitted DML fields
- `soql_literal` support for `decimal.Decimal`

### Changed

- Generated fields default to `UNSET`; explicit `None` serializes as JSON null when the field annotation includes `UnsetType`. Pre-UNSET generated classes still omit `None` so upgrading the package without regenerating cannot wipe fields. **Regenerate sObjects** to clear fields via `None`.
- `SObjectGenerator` now takes a `SalesforceClient` instead of a bare auth strategy
- Generated `__init__.py` includes `__all__`
- Picklist aliases keep underscores and use a `_PICKLIST` suffix; empty picklists type as `str`
- Generated modules import related sObjects at runtime (after the class body)
- `SalesforceClient.request` honors `Retry-After` (capped at 30s) and re-authenticates on `INVALID_SESSION_ID` except session-token auth

### Fixed

- Typed DML omits `None` on pre-UNSET generated classes and never sends relationship fields as JSON null
- `serialize_record` does not raise `NameError` when a legacy generated module is imported without its related siblings
- `UNSET` is a copy/pickle-safe falsy singleton
- `SalesforceClient.request` rebuilds the URL after re-auth so a new instance URL is used
- Generated runtime imports include `# noqa: E402`
- Config auth no longer requires a `.env` file (`find_dotenv(usecwd=True)`, missing file is ok)
- Generate CLI uses alias `api_version` via `from_config`
- `soql_literal` no longer emits scientific notation for small floats

## [0.3.0] - 2026-08-14

### Added

- Typed SOQL builder on generated sObjects: `Account.select(...).where(...).execute()`

## [0.2.0] - 2026-08-14

### Added

- Hero README, CI badges, contributing guide, issue templates
- Fixture-backed example generated sObjects under `examples/generated/`
- mypy in CI; CLI logging for `cloudy-salesforce generate`
- `SalesforceClient.from_config()` to build a client from `.cloudy_config` and env vars
- `cloudy-salesforce init` to scaffold `.cloudy_config` and `.env.example`
- Typed `insert` / `update` / `upsert` / `delete` from `@sobject` dataclasses
- `DmlResult` return type for composite DML
- `SalesforceError` with `error_code` and `status_code` for REST failures
- JWT bearer and session-token authentication (`JwtBearerAuthentication`, `SessionAuthentication`) with `.cloudy_config` aliases
- Optional rate-limit retries on HTTP 429 and `REQUEST_LIMIT_EXCEEDED` in `SalesforceClient.request`
- GitHub Actions Trusted Publisher workflow to publish to PyPI on GitHub release

### Changed

- `SalesforceClient` no longer becomes the default instance on construction; use `default=True` or `set_default_instance()`
- Ignore local `.cloudy_config` so `init` output is not committed by accident
- Generated `date` / `datetime` fields are `datetime.date` / `datetime.datetime` instead of `str` (regenerate sObjects to pick this up)

## [0.1.0] - 2026-08-14

### Added

- Typed Salesforce client: username/password SOAP auth, SOQL with pagination and `parse_as`, composite CRUD, describe-driven dataclass codegen

[Unreleased]: https://github.com/fishygeek91/cloudy-salesforce/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/fishygeek91/cloudy-salesforce/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/fishygeek91/cloudy-salesforce/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/fishygeek91/cloudy-salesforce/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/fishygeek91/cloudy-salesforce/releases/tag/v0.1.0
