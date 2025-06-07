# chess_analyzer_project/chess_analyzer/engine/stockfish_controller.py
"""
Manages interaction with the Stockfish chess engine.

This module provides a controller class to initialize, configure,
and use the Stockfish engine for analysing chess positions. It
abstracts the underlying `python-stockfish` library and ensures
robust process management.
"""
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Callable

import chess
from stockfish import Stockfish, StockfishException

from chess_analyzer.config import settings
# Import exceptions from the central location to prevent circular dependencies
from chess_analyzer.exceptions import (
    StockfishError,
    StockfishInitializationError,
    StockfishAnalysisError
)

logger = logging.getLogger(settings.APP_NAME + ".StockfishController")


class StockfishController:
    """
    Controls and interacts with a Stockfish chess engine instance.
    This class is a context manager to ensure the engine process is terminated.
    """

    def __init__(
        self,
        path: str,
        depth: int = settings.DEFAULT_ANALYSIS_DEPTH,
        **kwargs
    ):
        """
        Initializes the StockfishController and the Stockfish engine.
        
        Args:
            path: Absolute or relative path to the Stockfish executable.
            depth: Analysis depth for Stockfish.
            **kwargs: Can include 'stockfish_threads', 'stockfish_hash_mb', 'multipv_count'.
        """
        self.stockfish_path: str = os.path.realpath(path)
        self.analysis_depth: int = depth
        self.multipv_count: int = kwargs.get('multipv_count', settings.DEFAULT_MULTI_PV)

        self._stockfish_parameters: Dict[str, Any] = {
            "Threads": kwargs.get('stockfish_threads', settings.DEFAULT_STOCKFISH_THREADS),
            "Hash": kwargs.get('stockfish_hash_mb', settings.DEFAULT_STOCKFISH_HASH_MB),
            "MultiPV": self.multipv_count,
        }
        
        self._stockfish: Optional[Stockfish] = None
        self._stockfish_version: str = settings.STOCKFISH_VERSION_UNKNOWN
        self._is_closed: bool = False

        self._initialize_engine()
        logger.info(
            f"StockfishController initialized. Version: {self._stockfish_version}, "
            f"Depth: {self.analysis_depth}, Params: {self._stockfish_parameters}"
        )

    def _validate_stockfish_path(self) -> None:
        """Checks if the Stockfish path is valid and executable."""
        if not os.path.exists(self.stockfish_path):
            raise StockfishInitializationError(f"Stockfish executable not found: {self.stockfish_path}")
        if not os.access(self.stockfish_path, os.X_OK):
            raise StockfishInitializationError(f"Stockfish executable is not executable: {self.stockfish_path}")

    def _create_and_verify_engine_instance(self) -> Stockfish:
        """Creates a Stockfish instance and performs basic verification."""
        try:
            stockfish = Stockfish(
                path=self.stockfish_path,
                depth=self.analysis_depth,
                parameters=self._stockfish_parameters.copy()
            )
            if not stockfish.is_fen_valid(chess.STARTING_FEN):
                raise StockfishInitializationError("Stockfish process started but FEN validation failed.")
            
            version_val = stockfish.get_stockfish_major_version()
            self._stockfish_version = str(version_val) if version_val else settings.STOCKFISH_VERSION_UNKNOWN
            
            return stockfish
        except StockfishException as e:
            raise StockfishInitializationError(f"Failed to initialize Stockfish via library: {e}") from e
        except Exception as e:
            raise StockfishInitializationError(f"A generic error occurred initializing Stockfish: {e}") from e

    def _initialize_engine(self) -> None:
        """Initializes or re-initializes the Stockfish engine instance."""
        if self._is_closed:
            raise StockfishError("Controller is permanently closed and cannot be re-initialized.")
        
        self._validate_stockfish_path()
        logger.debug(f"Initializing Stockfish with parameters: {self._stockfish_parameters}")
        
        try:
            self._stockfish = self._create_and_verify_engine_instance()
            logger.info(f"Stockfish engine (Version: {self._stockfish_version}) initialized successfully.")
        except StockfishInitializationError:
            self._stockfish = None
            logger.error("Stockfish initialization failed.", exc_info=True)
            raise

    def get_stockfish_version(self) -> str:
        return self._stockfish_version

    def is_ready(self) -> bool:
        """Checks if the Stockfish engine instance is initialized and responsive."""
        if self._is_closed or self._stockfish is None:
            return False
        try:
            return self._stockfish.is_fen_valid(chess.STARTING_FEN)
        except StockfishException:
            return False

    def _ensure_engine_ready(self) -> None:
        """Ensures the Stockfish engine is initialized, re-initializing if needed."""
        if self._is_closed:
            raise StockfishError("Operation on a closed StockfishController.")
        if not self.is_ready():
            logger.warning("Stockfish engine not ready. Attempting re-initialization.")
            try:
                self._initialize_engine()
            except StockfishInitializationError as e:
                raise StockfishError("Fatal: Failed to re-initialize Stockfish.") from e

    def analyze_fens_batch(
        self,
        fen_list: List[str],
        shutdown_event: Optional[threading.Event] = None,
        progress_callback: Optional[Callable[[], None]] = None,
    ) -> Dict[str, Optional[List[Dict[str, Any]]]]:
        """
        Analyzes a list of FEN positions, returning a map of FEN to analysis results.
        
        Args:
            fen_list: A list of FEN strings to analyze.
            shutdown_event: An event to signal for early shutdown.
            progress_callback: An optional callable that will be called after each FEN is analyzed.
        """
        self._ensure_engine_ready()
        assert self._stockfish is not None, "Engine should be ready after _ensure_engine_ready"

        results: Dict[str, Optional[List[Dict[str, Any]]]] = {}
        if not fen_list:
            return results

        logger.debug(f"Starting Stockfish batch analysis of {len(fen_list)} FENs.")
        
        num_moves_to_get = max(1, self.multipv_count)
        
        for fen in fen_list:
            if shutdown_event and shutdown_event.is_set():
                logger.warning("Batch analysis interrupted by shutdown signal.")
                break
            
            try:
                if not self._stockfish.is_fen_valid(fen):
                    logger.warning(f"Invalid FEN provided for analysis, skipping: {fen}")
                    results[fen] = None
                    continue

                self._stockfish.set_fen_position(fen)
                top_moves = self._stockfish.get_top_moves(num_moves_to_get)
                results[fen] = top_moves
            except StockfishException as e:
                logger.error(f"Stockfish process error on FEN '{fen}'. Aborting batch.", exc_info=True)
                self._stockfish = None
                raise StockfishAnalysisError(f"Stockfish engine failed on FEN '{fen}'.") from e
            finally:
                if progress_callback:
                    progress_callback()
        
        logger.debug(f"Stockfish batch analysis finished for {len(results)} FENs.")
        return results

    def close(self) -> None:
        """Properly terminates the Stockfish engine process and closes the controller."""
        if self._is_closed:
            return
        
        logger.info("Closing StockfishController and terminating engine process...")
        if self._stockfish and hasattr(self._stockfish, '_subprocess'):
            proc = self._stockfish._subprocess
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2.0)
                    logger.debug("Stockfish process terminated.")
                except ProcessLookupError:
                    logger.debug("Stockfish process was already gone.")
                except TimeoutError:
                    logger.warning("Stockfish process did not terminate gracefully, killing it.")
                    proc.kill()
                    proc.wait(timeout=1.0)
                except Exception as e:
                    logger.error(f"Exception during Stockfish process termination: {e}", exc_info=True)

        self._stockfish = None
        self._is_closed = True
        logger.info("StockfishController closed.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()