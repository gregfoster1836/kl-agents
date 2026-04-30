"""Structured JSON logging to stdout.

Every log line is one JSON object. Cron-friendly, log-aggregator-friendly.
No emoji, no progress bars, no rich console output.

Usage:
    from agents.scout import logging_setup
    log = logging_setup.configure(level="INFO")
    log.info("run_started", extra={"run_id": "abc-123", "subreddits": 3})
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_RESERVED_LOG_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Renders a LogRecord as a single JSON line.

    The 'msg' parameter to a logging call becomes the 'event' field.
    Anything passed via 'extra' is merged at the top level.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "agent": getattr(record, "agent", "scout"),
            "event": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS:
                continue
            if key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure(level: str = "INFO", agent: str = "scout") -> logging.Logger:
    """Configure root logger to emit JSON to stdout. Returns the named logger.

    The 'agent' field is added by the formatter, defaulting to 'scout', so
    callers can just use logging.getLogger(...) and pass extra={...} normally.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    for existing in list(root.handlers):
        root.removeHandler(existing)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    return logging.getLogger(agent)
