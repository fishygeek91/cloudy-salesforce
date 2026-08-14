# cloudy-salesforce

Typed Salesforce from your org's metadata — not another dynamic dict client. cloudy-salesforce connects with username/password auth, runs SOQL and composite CRUD, and generates dataclasses from live describe metadata so queries and inserts are typed against your actual fields and picklists.

## Install

Local development:

```bash
pip install -e ".[dev]"
```

Published package:

```bash
pip install cloudy-salesforce
```

Requires Python 3.10+.

## Authentication

```python
from cloudy_salesforce import SalesforceClient, UsernamePasswordAuthentication

auth = UsernamePasswordAuthentication(
    username="you@example.com",
    password="your-password",
    security_token="your-token",
)
client = SalesforceClient(auth)

# Sandbox:
auth = UsernamePasswordAuthentication(
    username="you@example.com",
    password="your-password",
    security_token="your-token",
    login_url="https://test.salesforce.com",
)
client = SalesforceClient(auth)
```

## Query

Raw dict response:

```python
from cloudy_salesforce import query

result = query("SELECT Id, Name FROM Account LIMIT 5", client=client)
```

Typed response with a generated dataclass:

```python
from cloudy_salesforce import query
from sobjects import Account  # after codegen into ./sobjects

accounts = query(
    "SELECT Id, Name, (SELECT Id, Name FROM Opportunities) FROM Account",
    client=client,
    parse_as=Account,
)
```

## Insert

```python
from cloudy_salesforce import insert

insert("Account", [{"Name": "Acme"}], client=client)
```

## Codegen

1. Copy `.cloudy_config.example` to `.cloudy_config` and set your auth aliases.
2. Create a `.env` with the credential variables referenced in the config (e.g. `SF_USERNAME`, `SF_PASSWORD`, `SF_SECURITY_TOKEN`).
3. Generate dataclasses:

```bash
cloudy-salesforce generate --alias prod
```

Optional: limit to specific sObjects:

```bash
cloudy-salesforce generate --alias prod --sobjects Account
```

Generated classes reflect your org metadata — picklists become `Literal` unions (with `| str` fallback), and child relationships become nested lists:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cloudy_salesforce.sobjects import sobject

if TYPE_CHECKING:
    from .Opportunity import Opportunity

INDUSTRYPICKLIST = Literal["Technology", "Finance", "Healthcare"] | str

@sobject()
@dataclass
class Account:
    Id: str | None = None
    Name: str | None = None
    Industry: INDUSTRYPICKLIST | None = None
    Opportunities: list[Opportunity] | None = None
```
