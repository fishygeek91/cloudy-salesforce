# Contributing

Thanks for helping improve [cloudy-salesforce](https://github.com/fishygeek91/cloudy-salesforce).

## Development setup

- **Python 3.10+** is required.
- Install the package and dev dependencies:

  ```bash
  pip install -e ".[dev]"
  ```

## Running checks

Run these before opening a pull request:

```bash
pytest
ruff check cloudy_salesforce tests
mypy cloudy_salesforce
```

Tests use mocks and fixtures. CI and the default test suite do **not** connect to a live Salesforce org.

## Secrets and local config

Do not commit `.env`, `.cloudy_config`, or any credentials. Use environment variables or local config files that stay out of version control.

## Pull requests

- Branch from `main` and open PRs against `main`.
- Keep changes focused and include tests when behavior changes.

## Code style

- Match patterns in existing modules (typing, naming, structure).
- Keep tests mocked; avoid requiring a real org unless explicitly documented as an integration test.
