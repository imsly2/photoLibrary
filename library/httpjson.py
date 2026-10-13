"""JSON HTTP helpers for the local library server and CLI forwarding."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def encode(obj: Any) -> bytes:
    return json.dumps(obj, separators=(",", ":"), allow_nan=False).encode("utf-8")


def decode(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"))


def request_json(
    url: str,
    *,
    method: str = "GET",
    body: Any | None = None,
    timeout: float = 3.0,
) -> tuple[int, Any]:
    data = None if body is None else encode(body)
    headers = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            parsed: Any = None
            if payload:
                parsed = decode(payload)
            return resp.status, parsed
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        parsed = None
        if payload:
            try:
                parsed = decode(payload)
            except json.JSONDecodeError:
                parsed = None
        return exc.code, parsed
