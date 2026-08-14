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
    OwnerId: str | None = None
    Opportunities: list[Opportunity] | None = None