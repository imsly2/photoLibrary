"""Wire error codes. Unlisted codes are not used."""

from __future__ import annotations


class AppError(Exception):
    def __init__(self, code: str, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


HTTP_STATUS = {
    "invalid-argument": 400,
    "choice-required": 400,
    "not-found": 404,
    "unavailable": 404,
    "update-unavailable": 404,
    "preview-unavailable": 404,
    "picker-unavailable": 404,
    "models-missing": 404,
    "busy": 409,
    "port-in-use": 409,
    "volume-identity-unavailable": 409,
    "invalid-range": 416,
    "io-error": 500,
    "invalid-catalog": 500,
    "decode-error": 500,
    "internal-error": 500,
}


def fail(code: str) -> AppError:
    return AppError(code, HTTP_STATUS[code])
