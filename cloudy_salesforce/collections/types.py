from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DmlResult:
    id: str | None
    success: bool
    errors: list[Any]
    created: bool | None = None
    record: dict[str, Any] | None = None
