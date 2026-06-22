"""Structured JSON logging to stdout for kl-agents.

Every log line is one JSON object. Cron-friendly, log-aggregator-friendly.
No emoji, no progress bars, no rich console output.

The agent name is injected at the FORMATTER, not assumed on each record:
configure(level, agent) builds a JsonFormatter(agent) that stamps every line
with that agent. This means plain logging.getLogger(__name__).info(...) calls
and module-level loggers all carry the right agent without each call site
passing it. There is no default agent: a missing agent is a wiring bug, not a
silent mislabel.

Usage:
    from shared import logging_setup
    log = logging_setup.configure(level="INFO", agent="scout")
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
    """Renders a LogRecord as a single JSON line, stamped with the agent name.

    The 'msg' parameter to a logging call becomes the 'event' field. Anything
    passed via 'extra' is merged at the top level. The agent name is held by the
    formatter (set at configure time), so every record gets it regardless of how
    the logger was obtained.
    """

    def __init__(self, agent: str) -> None:
        super().__init__()
        self._agent = agent

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "agent": self._agent,
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


def configure(level: str = "INFO", *, agent: str) -> logging.Logger:
    """Configure the root logger to emit agent-stamped JSON to stdout.

    agent is required: it is stamped onto every log line by the formatter, so
    callers can use logging.getLogger(...) normally and pass extra={...} without
    repeating the agent name. Returns the logger named after the agent.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    for existing in list(root.handlers):
        root.removeHandler(existing)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(agent))
    root.addHandler(handler)

    return logging.getLogger(agent)
