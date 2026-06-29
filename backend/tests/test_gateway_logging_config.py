import logging
from importlib import util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "gateway" / "logging_config.py"
_SPEC = util.spec_from_file_location("gateway_logging_config", _MODULE_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
gateway_logging_config = util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gateway_logging_config)

PROCESS_LOG_HANDLER_NAME = gateway_logging_config.PROCESS_LOG_HANDLER_NAME
configure_process_file_logging = gateway_logging_config.configure_process_file_logging
logging_level_from_env = gateway_logging_config.logging_level_from_env
parse_logger_names = gateway_logging_config.parse_logger_names
remove_process_file_logging = gateway_logging_config.remove_process_file_logging


def test_parse_logger_names_defaults_when_empty() -> None:
    assert "app" in parse_logger_names(None)
    assert "deerflow" in parse_logger_names("")


def test_parse_logger_names_trims_comma_separated_values() -> None:
    assert parse_logger_names(" app, deerflow ,, langgraph ") == ("app", "deerflow", "langgraph")


def test_logging_level_from_env_accepts_names_and_numbers() -> None:
    assert logging_level_from_env("debug") == logging.DEBUG
    assert logging_level_from_env("20") == logging.INFO
    assert logging_level_from_env("unknown", logging.WARNING) == logging.WARNING


def test_configure_process_file_logging_writes_to_file(tmp_path) -> None:
    log_path = tmp_path / "runtime" / "model.log"
    logger_name = "tests.gateway.runtime"
    logger = logging.getLogger(logger_name)
    original_level = logger.level

    handler = configure_process_file_logging(
        log_path=log_path,
        logger_names=(logger_name,),
        level=logging.DEBUG,
        max_bytes=1024 * 1024,
        backup_count=1,
    )
    try:
        logger.debug("runtime detail is captured")
        handler.flush()
        assert "runtime detail is captured" in log_path.read_text(encoding="utf-8")
    finally:
        remove_process_file_logging(handler, (logger_name,))
        logger.setLevel(original_level)


def test_configure_process_file_logging_replaces_existing_named_handler(tmp_path) -> None:
    logger_name = "tests.gateway.duplicate"
    logger = logging.getLogger(logger_name)
    original_level = logger.level

    first = configure_process_file_logging(
        log_path=tmp_path / "first.log",
        logger_names=(logger_name,),
        level=logging.INFO,
        max_bytes=1024 * 1024,
        backup_count=1,
    )
    second = configure_process_file_logging(
        log_path=tmp_path / "second.log",
        logger_names=(logger_name,),
        level=logging.INFO,
        max_bytes=1024 * 1024,
        backup_count=1,
    )

    try:
        named_handlers = [handler for handler in logger.handlers if handler.get_name() == PROCESS_LOG_HANDLER_NAME]
        assert named_handlers == [second]
        assert first.stream is None
    finally:
        remove_process_file_logging(second, (logger_name,))
        logger.setLevel(original_level)
