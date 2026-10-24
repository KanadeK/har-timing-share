"""Bounded HAR ingestion and a deliberately small output vocabulary."""

from __future__ import annotations

import json
import math
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

METHODS = frozenset(
    {"GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"}
)
PHASES = ("blocked", "dns", "connect", "ssl", "send", "wait", "receive")
MAX_NUMBER = 1_000_000_000_000
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z")


class HarError(ValueError):
    """A source-independent diagnostic. Never contains captured field values."""


def _object(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise HarError(f"{label} must be an object.")
    return value


def _number(value: Any, label: str, *, unknown: bool = False) -> float | None:
    if unknown and (value is None or value == -1) and not isinstance(value, bool):
        return None
    if type(value) not in (int, float) or not 0 <= value <= MAX_NUMBER:
        raise HarError(f"{label} must be a finite nonnegative number within the supported range.")
    if not math.isfinite(value):
        raise HarError(f"{label} must be finite.")
    return round(float(value), 3)


def _size(value: Any, label: str) -> int | None:
    if value is None or (type(value) is int and value == -1):
        return None
    if type(value) is not int or not 0 <= value <= MAX_NUMBER:
        raise HarError(f"{label} must be an integer byte count, -1, or absent.")
    return value


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or len(value) > 64 or not TIMESTAMP.fullmatch(value):
        raise HarError(f"{label} requires an ISO timestamp with a timezone.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HarError(f"{label} has an invalid date or timezone.") from None


def _resource(value: Any) -> str:
    if not isinstance(value, str):
        return "other"
    mime = value.split(";", 1)[0].strip().lower()
    if mime in {"text/html", "application/xhtml+xml"}:
        return "html"
    if mime == "text/css":
        return "css"
    if mime in {"application/javascript", "text/javascript", "application/ecmascript"}:
        return "script"
    if mime == "application/json" or mime.endswith("+json"):
        return "json"
    for prefix, category in (
        ("image/", "image"),
        ("font/", "font"),
        ("audio/", "media"),
        ("video/", "media"),
    ):
        if mime.startswith(prefix):
            return category
    return "other"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise HarError("Duplicate JSON object keys are not supported.")
        result[key] = value
    return result


def _constant(_value: str) -> None:
    raise HarError("Non-finite JSON numeric constants are not supported.")


def load_har(path: str | Path, *, max_bytes: int = 64 * 1024 * 1024) -> dict:
    """Read at most max_bytes + 1 from a regular local file, accepting a UTF-8 BOM."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise HarError("max_bytes must be a positive integer.")
    try:
        if not stat.S_ISREG(Path(path).lstat().st_mode):
            raise HarError("Input must be a regular local file, not a link or special file.")
        flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_BINARY", 0)
        )
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise HarError("Input must be a regular local file.")
            raw = source.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise HarError("Input exceeds the byte limit.")
        return _object(
            json.loads(
                raw.decode("utf-8-sig"), object_pairs_hook=_unique_object, parse_constant=_constant
            ),
            "HAR",
        )
    except HarError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise HarError("Input must be valid UTF-8 JSON within parser limits.") from None
    except OSError:
        raise HarError("Could not read the input file.") from None


def project_har(document: dict, *, max_entries: int = 10_000) -> dict:
    """Create fresh allowlisted objects. Never mutate or copy through the source."""
    if type(max_entries) is not int or max_entries <= 0:
        raise HarError("max_entries must be a positive integer.")
    log = _object(_object(document, "HAR").get("log"), "log")
    source_entries = log.get("entries")
    if not isinstance(source_entries, list):
        raise HarError("log.entries must be an array.")
    if len(source_entries) > max_entries:
        raise HarError("Entry count exceeds the limit.")
    projected = []
    dates = []
    for index, item in enumerate(source_entries, 1):
        label = f"entry {index}"
        entry = _object(item, label)
        started = _timestamp(entry.get("startedDateTime"), f"{label}.startedDateTime")
        request = _object(entry.get("request"), f"{label}.request")
        response = _object(entry.get("response"), f"{label}.response")
        content = _object(response.get("content", {}), f"{label}.response.content")
        timings = _object(entry.get("timings", {}), f"{label}.timings")
        status = response.get("status")
        if type(status) is not int or not (status == 0 or 100 <= status <= 599):
            raise HarError(f"{label}.response.status must be 0 or an integer from 100 through 599.")
        method = request.get("method")
        method = method.upper() if isinstance(method, str) else "OTHER"
        projected.append(
            {
                "id": f"request-{index:05d}",
                "method": method if method in METHODS else "OTHER",
                "status": status,
                "resource": _resource(content.get("mimeType")),
                "start_ms": 0.0,
                "duration_ms": _number(entry.get("time"), f"{label}.time"),
                "decoded_body_bytes": _size(content.get("size"), f"{label}.response.content.size"),
                "phases_ms": {
                    phase: _number(timings.get(phase), f"{label}.timings.{phase}", unknown=True)
                    for phase in PHASES
                },
            }
        )
        dates.append(started)
    if dates:
        earliest = min(dates)
        for row, started in zip(projected, dates, strict=True):
            row["start_ms"] = _number((started - earliest).total_seconds() * 1000, "Relative start")
        projected.sort(key=lambda row: (row["start_ms"], row["id"]))
    durations = sorted(row["duration_ms"] for row in projected)

    def percentile(fraction):
        return durations[math.ceil(len(durations) * fraction) - 1] if durations else None

    return {
        "schema_version": 1,
        "summary": {
            "request_count": len(projected),
            "span_ms": round(
                max((row["start_ms"] + row["duration_ms"] for row in projected), default=0.0), 3
            ),
            "p50_ms": percentile(0.50),
            "p95_ms": percentile(0.95),
            "known_decoded_body_bytes": sum(row["decoded_body_bytes"] or 0 for row in projected),
            "unknown_body_sizes": sum(row["decoded_body_bytes"] is None for row in projected),
            "http_error_count": sum(row["status"] >= 400 for row in projected),
            "network_error_count": sum(row["status"] == 0 for row in projected),
        },
        "entries": projected,
    }
