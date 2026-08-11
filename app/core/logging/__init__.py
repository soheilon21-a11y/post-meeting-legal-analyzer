from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from app.core.config.settings import LoggingSettings, get_settings


def configure_logging(settings: LoggingSettings | None = None) -> None:
    if settings is None:
        settings = get_settings().logging

    log_level = getattr(logging, settings.level.upper(), logging.INFO)

    if settings.format == "json":
        _configure_json_logging(log_level)
    else:
        _configure_text_logging(log_level)


def _configure_json_logging(log_level: int) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.contextvars.merge_contextvars,
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.PATHNAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            ),
            structlog.processors.format_exc_info,
            timestamper,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(serializer=_orjson_dumps),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configure_root_handler(logging.StreamHandler(sys.stdout), log_level)


def _configure_text_logging(log_level: int) -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.contextvars.merge_contextvars,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configure_root_handler(logging.StreamHandler(sys.stdout), log_level)


def _configure_root_handler(handler: logging.Handler, log_level: int) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def _orjson_dumps(obj: Any, default: Any = None) -> str:
    try:
        import orjson

        return orjson.dumps(obj, default=default).decode("utf-8")
    except ImportError:
        import json

        return json.dumps(obj, default=default)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    structlog.contextvars.unbind_contextvars(*keys)
