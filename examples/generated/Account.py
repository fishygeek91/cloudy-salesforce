from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cloudy_salesforce.sobjects import sobject
from cloudy_salesforce.types import UNSET, UnsetType

if TYPE_CHECKING:
    from .Opportunity import Opportunity

INDUSTRY_PICKLIST = Literal["Technology", "Finance", "Healthcare"] | str

@sobject()
@dataclass
class Account:
    Id: str | None | UnsetType = UNSET
    Name: str | None | UnsetType = UNSET
    Industry: INDUSTRY_PICKLIST | None | UnsetType = UNSET
    OwnerId: str | None | UnsetType = UNSET
    Opportunities: list[Opportunity] | None | UnsetType = UNSET


from .Opportunity import Opportunity
