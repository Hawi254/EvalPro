# chess_analyzer_project/chess_analyzer/utils/logging_config.py
"""
Logging configuration for the Chess Analyzer application.

This module provides a centralized function to set up consistent, flexible logging
across the application, with support for distinct formatting for console and file outputs.
It can also accept pre-configured handlers for advanced use cases like TQDM integration.
"""
import logging
import sys
from typing import Optional, List, Iterable

from chess_analyzer.config import settings


def setup_logging(
    log_level_str: Optional[str] = None,
    log_file: Optional[str] = None,
    log_to_console: bool = True,
    log_to_file: bool = True,
    extra_handlers: Optional[Iterable[logging.Handler]] = None,
) -> None:
    """
    Configures application-wide logging by manipulating the root logger.

    Sets the logging level, formatters, and handlers (console and/or file).
    By configuring the root logger, all loggers created via
    `logging.getLogger(__name__)` will inherit this configuration.

    This setup allows for different log formats for console and file outputs.

    Args:
        log_level_str: The desired logging level as a string (e.g., "INFO", "DEBUG").
                       If None, defaults to `settings.DEFAULT_LOG_LEVEL`.
        log_file: The path to the log file.
                  If None, defaults to `settings.DEFAULT_LOG_FILENAME`.
        log_to_console: Whether to output logs to the console (stdout).
        log_to_file: Whether to output logs to the specified log file.
        extra_handlers: An optional iterable of pre-configured handlers to add
                        to the root logger (e.g., for TQDM integration). If
                        provided and `log_to_console` is True, these will
                        replace the default console handler.
    """
    effective_log_level_str = log_level_str or settings.DEFAULT_LOG_LEVEL
    effective_log_file = log_file or settings.DEFAULT_LOG_FILENAME

    # Validate and convert the log level string to its integer value
    level_val = logging.getLevelName(effective_log_level_str.upper())
    if not isinstance(level_val, int):
        # Fallback to INFO if the provided string is invalid and warn the user.
        logging.warning(
            f"Invalid log level string: '{effective_log_level_str}'. Defaulting to 'INFO'."
        )
        level_val = logging.INFO
        effective_log_level_str = "INFO"

    # --- Manual Root Logger Configuration for Maximum Flexibility ---

    # 1. Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level_val)

    # 2. Clear any existing handlers to prevent duplicate logs
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 3. Define formatters
    # A more concise format for the console
    console_formatter = logging.Formatter("%(levelname)-8s - %(name)s - %(message)s")
    # A more detailed format for the log file
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 4. Create and configure handlers
    handlers: List[logging.Handler] = []
    if log_to_console:
        # If extra handlers are provided (like a Tqdm handler), we assume they handle
        # console output and do not add the default StreamHandler.
        # This prevents duplicate logs to the console.
        if not extra_handlers:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(console_formatter)
            handlers.append(console_handler)

    if log_to_file:
        # Ensure the file handler uses 'a' mode (append) and UTF-8 encoding.
        file_handler = logging.FileHandler(effective_log_file, mode="a", encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
    
    # Add any extra handlers passed in. This is where the Tqdm handler will be added.
    if extra_handlers:
        for handler in extra_handlers:
            # We can optionally set a formatter if the handler doesn't have one
            if handler.formatter is None:
                handler.setFormatter(console_formatter)
            handlers.append(handler)

    # 5. Add all collected handlers to the root logger
    if not handlers:
        root_logger.addHandler(logging.NullHandler())
        logging.warning("Logging is not configured to output to console or file.")
        return

    for handler in handlers:
        root_logger.addHandler(handler)

    # Log the effective configuration using a dedicated logger
    setup_logger = logging.getLogger(__name__)
    setup_logger.info(f"Logging initialized. Level: {effective_log_level_str.upper()}.")
    if log_to_console:
        setup_logger.info("Logging to console enabled.")
    if log_to_file:
        setup_logger.info(f"Logging to file enabled: '{effective_log_file}'.")