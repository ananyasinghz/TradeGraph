"""Integration errors (mapped to AppError at API boundary when needed)."""

from __future__ import annotations


class IntegrationError(Exception):
    """Base integration failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ProviderNotFoundError(IntegrationError):
    def __init__(self, source_code: str) -> None:
        super().__init__(
            code="PROVIDER_NOT_FOUND",
            message=f"No provider registered for source_code={source_code}",
        )


class AdapterError(IntegrationError):
    def __init__(self, message: str, *, code: str = "ADAPTER_ERROR") -> None:
        super().__init__(code=code, message=message)


class FetchError(IntegrationError):
    def __init__(self, message: str, *, code: str = "FETCH_ERROR") -> None:
        super().__init__(code=code, message=message)
