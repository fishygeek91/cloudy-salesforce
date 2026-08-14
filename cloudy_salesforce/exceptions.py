from typing import Any


class SalesforceError(Exception):
    """Structured exception for Salesforce REST API errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        response_body: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.response_body = response_body

    def __str__(self) -> str:
        if self.error_code:
            text = f"{self.error_code}: {self.message}"
        else:
            text = self.message
        if self.status_code is not None:
            text = f"{text} (HTTP {self.status_code})"
        return text
