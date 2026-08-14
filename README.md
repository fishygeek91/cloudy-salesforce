# cloudy-salesforce

Typed Salesforce from your org's metadata — not another dynamic dict client.

[![CI](https://github.com/fishygeek91/cloudy-salesforce/actions/workflows/ci.yml/badge.svg)](https://github.com/fishygeek91/cloudy-salesforce/actions/workflows/ci.yml)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10--3.13-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/github/license/fishygeek91/cloudy-salesforce)](https://github.com/fishygeek91/cloudy-salesforce/blob/main/LICENSE)

Generate dataclasses from your org's live describe metadata — picklist `Literal` unions, child relationships as nested lists — then query with `parse_as` and get real attributes instead of dict keys.

```python
from cloudy_salesforce import SalesforceClient, UsernamePasswordAuthentication, query
from sobjects import Account  # generated from your org

client = SalesforceClient(UsernamePasswordAuthentication(
    username="you@example.com", password="...", security_token="...",
))
accounts = query(
    "SELECT Id, Name, Industry, (SELECT Id, Name FROM Opportunities) FROM Account LIMIT 1",
    client=client,
    parse_as=Account,
)
account = accounts[0]
account.Industry          # Literal["Technology", "Finance", ...] | str
account.Opportunities     # list[Opportunity] | None
```

Full generated output: [`examples/generated/Account.py`](examples/generated/Account.py).

| Before (dict client) | After (cloudy-salesforce) |
|---|---|
| `result["records"][0]["Industry"]` | `account.Industry` |
| untyped string keys | IDE autocomplete on your org's fields |
| nested subqueries as nested dicts | `account.Opportunities[0].Name` |

## Install

```bash
pip install -e ".[dev]"   # local development
pip install cloudy-salesforce   # published install (coming soon)
```

Requires Python 3.10+.

## Generate dataclasses

```bash
cloudy-salesforce init
```

Copy `.env.example` to `.env` and fill in `SF_USERNAME`, `SF_PASSWORD`, and `SF_SECURITY_TOKEN`, then run codegen against your org:

```bash
cloudy-salesforce generate --alias prod
```

Limit to specific sObjects:

```bash
cloudy-salesforce generate --alias prod --sobjects Account
```

Codegen writes dataclass modules to `./sobjects/` by default.

## Query

Raw dict response (same shape as the REST API):

```python
from cloudy_salesforce import query

result = query("SELECT Id, Name, Industry FROM Account LIMIT 5", client=client)
industry = result["records"][0]["Industry"]
```

Typed response with a generated dataclass. Pagination is automatic, including nested subquery pages:

```python
from cloudy_salesforce import query
from sobjects import Account

accounts = query(
    "SELECT Id, Name, Industry, (SELECT Id, Name FROM Opportunities) FROM Account",
    client=client,
    parse_as=Account,
)
account = accounts[0]
account.Industry
```

Set a default client once from an auth strategy and omit `client=` on later calls:

```python
SalesforceClient.set_default_instance(auth)
accounts = query("SELECT Id FROM Account", parse_as=Account)
```

## Insert, update, upsert, delete

DML currently takes an object name and `list[dict]` — not generated dataclass instances.

```python
from cloudy_salesforce import insert, update, upsert, delete

insert("Account", [{"Name": "Acme"}], client=client)
update("Account", [{"Id": "001...", "Name": "Acme Corp"}], client=client)
upsert("Account", [{"Name": "Acme", "External_Id__c": "x1"}], external_id_field="External_Id__c", client=client)
delete("Account", [{"Id": "001..."}], client=client)
```

Operations use the Salesforce composite collection API and batch records automatically (default batch size 200).

## How codegen works

```mermaid
flowchart LR
  A[Org describe API] --> B["cloudy-salesforce generate"]
  B --> C[Dataclass modules in ./sobjects/]
  C --> D["query(..., parse_as=Account)"]
  C --> E["insert / update / upsert / delete"]
```

| Metadata | Generated type |
|---|---|
| Picklist / multipicklist field | `Literal["Value1", "Value2", ...] \| str` |
| Child relationship (e.g. Opportunities on Account) | `list[Opportunity] \| None` |
| Lookup / reference field | `str \| None` (Id); relationship object only if that sObject is also generated |
| Standard scalar fields | `str`, `int`, `float`, or `bool` (`date` / `datetime` currently stay `str`) |

Picklist literals reflect active values at generation time. The `| str` fallback covers values added to the org later.

## Authentication

```python
from cloudy_salesforce import SalesforceClient, UsernamePasswordAuthentication

auth = UsernamePasswordAuthentication(
    username="you@example.com",
    password="your-password",
    security_token="your-token",
)
client = SalesforceClient(auth)
```

Or load credentials from `.cloudy_config` and environment variables:

```python
client = SalesforceClient.from_config(alias="prod")
```

Sandbox:

```python
auth = UsernamePasswordAuthentication(
    username="you@example.com",
    password="your-password",
    security_token="your-token",
    login_url="https://test.salesforce.com",
)
client = SalesforceClient(auth)
```

## Comparison

| | cloudy-salesforce | [simple-salesforce](https://github.com/simple-salesforce/simple-salesforce) | [aiosalesforce](https://github.com/georgebv/aiosalesforce) |
|---|---|---|---|
| Org-generated types | Yes — dataclasses from describe | No — dict responses | No — dict responses |
| Picklist `Literal` unions | Yes | No | No |
| Nested subquery pagination | Automatic | Manual | Manual |
| Composite CRUD (batch DML) | Yes | Partial | Partial |

## Status

v0.1.0 · Python 3.10+ · [MIT License](LICENSE) · Not affiliated with Salesforce, Inc.
