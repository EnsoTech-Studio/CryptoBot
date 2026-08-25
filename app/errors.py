"""Stable application errors shared by HTTP and persistence adapters."""

from __future__ import annotations


class ApplicationError(Exception):
    def __init__(self, code: str, message: str, status_code: int, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field


def not_found(resource: str) -> ApplicationError:
    return ApplicationError(f"{resource}_not_found", f"{resource.replace('_', ' ')} not found", 404)


def conflict(code: str, message: str) -> ApplicationError:
    return ApplicationError(code, message, 409)


def validation(code: str, message: str, field: str | None = None) -> ApplicationError:
    return ApplicationError(code, message, 422, field)

