from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cloudy_salesforce.sobjects import sobject

if TYPE_CHECKING:
    from .Account import Account

@sobject()
@dataclass
class Opportunity:
    Id: str | None = None
    Name: str | None = None
    AccountId: str | None = None
    Account: Account | None = None
    CloseDate: str | None = None