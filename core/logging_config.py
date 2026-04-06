import logging
import os
import sys

import structlog


def setup_logging() -> None:
    """
    Configure application-wide logging.

    In production (ENVIRONMENT=production) or when LOG_FORMAT=json, emits
    structured JSON lines via structlog — one JSON object per log record,
    compatible with Railway log drain, Datadog, and most log aggregators.

    In all other environments, emits human-readable console output with
    colours/timestamps for easy local development.
    """
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    environment = os.getenv("ENVIRONMENT", "development")
    log_format = os.getenv("LOG_FORMAT", "json" if environment == "production" else "console")
    use_json = log_format == "json"

    # Shared processors applied before the final renderer
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if use_json:
        # Production: output newline-delimited JSON
        structlog.configure(
            processors=shared_processors
            + [
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        # Also redirect stdlib logging records through structlog so third-party
        # libraries (uvicorn, SQLAlchemy) appear in the same JSON stream.
        logging.basicConfig(
            format="%(message)s",
            level=log_level,
            stream=sys.stdout,
            force=True,
        )
        logging.getLogger().handlers[0].setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=shared_processors
                + [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
            )
        )
    else:
        # Development: coloured, human-readable output
        structlog.configure(
            processors=shared_processors
            + [
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            stream=sys.stdout,
        )
