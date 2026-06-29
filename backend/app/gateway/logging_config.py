import logging
import os
from collections.abc import Iterable, Sequence
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROCESS_LOG_HANDLER_NAME = "intelli-engine-process-log"
DEFAULT_PROCESS_LOGGER_NAMES = (
    "app",
    "deerflow",
    "langgraph",
    "langchain",
    "openai",
    "httpx",
    "httpcore",
    "uvicorn",
)
DEFAULT_PROCESS_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_PROCESS_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_logger_names(value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated logger list from an environment variable."""

    if value is None:
        return DEFAULT_PROCESS_LOGGER_NAMES

    names = tuple(name.strip() for name in value.split(",") if name.strip())
    return names or DEFAULT_PROCESS_LOGGER_NAMES


def logging_level_from_env(value: str | None, default: int = logging.INFO) -> int:
    """Resolve a logging level name/number from an environment variable."""

    if value is None or not value.strip():
        return default

    raw = value.strip()
    if raw.isdigit():
        return int(raw)

    return logging.getLevelNamesMapping().get(raw.upper(), default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _remove_named_handler(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if handler.get_name() == PROCESS_LOG_HANDLER_NAME:
            logger.removeHandler(handler)
            handler.close()


def configure_process_file_logging(
    *,
    log_path: str | os.PathLike[str],
    logger_names: Sequence[str] = DEFAULT_PROCESS_LOGGER_NAMES,
    level: int = logging.INFO,
    max_bytes: int = 100 * 1024 * 1024,
    backup_count: int = 3,
) -> RotatingFileHandler:
    """Attach one rotating file handler to runtime loggers.

    The gateway already sends stdout/stderr to systemd-managed files. This
    handler is for the richer in-process runtime stream: app, deerflow,
    LangGraph/LangChain, model provider SDK, and HTTP client logs.
    """

    path = Path(log_path)
    if path.parent and str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.set_name(PROCESS_LOG_HANDLER_NAME)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(DEFAULT_PROCESS_LOG_FORMAT, datefmt=DEFAULT_PROCESS_LOG_DATE_FORMAT))

    for logger_name in logger_names:
        target_logger = logging.getLogger(logger_name)
        _remove_named_handler(target_logger)
        target_logger.addHandler(handler)
        if target_logger.level == logging.NOTSET or level < target_logger.level:
            target_logger.setLevel(level)

    logging.captureWarnings(True)
    return handler


def configure_process_file_logging_from_env() -> tuple[RotatingFileHandler, tuple[str, ...]]:
    """Configure runtime file logging from MODEL_LOG_* environment variables."""

    logger_names = parse_logger_names(os.getenv("MODEL_LOG_LOGGERS"))
    level = logging_level_from_env(os.getenv("MODEL_LOG_LEVEL"), logging.INFO)
    handler = configure_process_file_logging(
        log_path=os.getenv("MODEL_LOG_PATH", "model.log"),
        logger_names=logger_names,
        level=level,
        max_bytes=_env_int("MODEL_LOG_MAX_BYTES", 100 * 1024 * 1024),
        backup_count=_env_int("MODEL_LOG_BACKUP_COUNT", 3),
    )
    return handler, logger_names


def remove_process_file_logging(handler: logging.Handler | None, logger_names: Iterable[str]) -> None:
    """Detach and close the process file handler installed at startup."""

    if handler is None:
        return

    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        if handler in logger.handlers:
            logger.removeHandler(handler)
    handler.close()
