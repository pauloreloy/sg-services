"""Structured JSON logger following ADR Section 9.1 specifications."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON objects with ADR-compliant fields."""

    def __init__(self, service_name: str, environment: str = "local") -> None:
        super().__init__()
        self._service_name = service_name
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", self._service_name),
            "environment": getattr(record, "environment", self._environment),
            "message": record.getMessage(),
        }

        # Optional ADR fields from record.__dict__
        for attr in (
            "requestId",
            "attemptId",
            "correlationId",
            "stepName",
            "messageId",
            "status",
            "durationMs",
            "errorCode",
        ):
            val = getattr(record, attr, None)
            if val is not None:
                log_data[attr] = val

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def configure_structured_logging(service_name: str, log_level: str = "INFO", environment: str = "local") -> logging.Logger:
    """Configures root or named logger with structured JSON output."""
    logger = logging.getLogger(service_name)
    logger.setLevel(log_level.upper())

    # Avoid duplicate handlers if re-called
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter(service_name=service_name, environment=environment))
        logger.addHandler(handler)
        logger.propagate = False

    return logger
