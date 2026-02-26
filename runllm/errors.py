from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ErrorPayload:
    error_code: str
    error_type: str
    message: str
    details: dict[str, Any]
    expected_schema: dict[str, Any] | None = None
    received_payload: Any | None = None
    recovery_hint: str | None = None
    doc_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details,
            "expected_schema": self.expected_schema,
            "received_payload": self.received_payload,
            "recovery_hint": self.recovery_hint,
            "doc_ref": self.doc_ref,
        }


class RunLLMError(Exception):
    def __init__(self, payload: ErrorPayload) -> None:
        super().__init__(payload.message)
        self.payload = payload


def make_error(
    *,
    error_code: str,
    error_type: str,
    message: str,
    details: dict[str, Any] | None = None,
    expected_schema: dict[str, Any] | None = None,
    received_payload: Any | None = None,
    recovery_hint: str | None = None,
    doc_ref: str | None = None,
) -> RunLLMError:
    return RunLLMError(
        ErrorPayload(
            error_code=error_code,
            error_type=error_type,
            message=message,
            details=details or {},
            expected_schema=expected_schema,
            received_payload=received_payload,
            recovery_hint=recovery_hint,
            doc_ref=doc_ref,
        )
    )
