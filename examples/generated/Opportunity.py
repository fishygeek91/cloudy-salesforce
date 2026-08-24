from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cloudy_salesforce.sobjects import sobject
from cloudy_salesforce.types import UNSET, UnsetType

if TYPE_CHECKING:
    from .Account import Account

@sobject()
@dataclass
class Opportunity:
    Id: str | None | UnsetType = UNSET
    Name: str | None | UnsetType = UNSET
    AccountId: str | None | UnsetType = UNSET
    Account: Account | None | UnsetType = UNSET
    CloseDate: datetime.date | None | UnsetType = UNSET

# Runtime imports after the class body so circular relationships resolve.

from .Account import Account  # noqa: E402
