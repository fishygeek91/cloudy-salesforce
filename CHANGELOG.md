# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/fishygeek91/cloudy-salesforce/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/fishygeek91/cloudy-salesforce/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/fishygeek91/cloudy-salesforce/releases/tag/v0.1.0
