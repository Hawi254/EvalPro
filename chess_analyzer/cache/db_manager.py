# chess_analyzer_project/chess_analyzer/cache/db_manager.py
"""
Manages the SQLite database for caching FEN analysis results.
...
"""
import sqlite3
import json
import logging
import os
from typing import Optional, List, Dict, Any

from chess_analyzer.config import settings
from chess_analyzer.types import CacheKey, CacheEntry
from chess_analyzer.exceptions import (
    CacheError,
    CacheConnectionError,
    CacheReadError,
    CacheWriteError,
)

logger = logging.getLogger(settings.APP_NAME + ".DBManager")


class DBManager:
    """
    Manages an SQLite database for caching FEN analysis results.
    ...
    """
    # ... (_TABLE_NAME, _CREATE_TABLE_SQL, __init__, _ensure_connected remain the same) ...
    _TABLE_NAME: str = "fen_analysis_cache"
    _CREATE_TABLE_SQL: str = f"""
        CREATE TABLE IF NOT EXISTS {_TABLE_NAME} (
            fen TEXT NOT NULL,
            analysis_depth INTEGER NOT NULL,
            multipv_count INTEGER NOT NULL,
            stockfish_path_canon TEXT NOT NULL,
            stockfish_version TEXT NOT NULL,
            analysis_result_json TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (fen, analysis_depth, multipv_count, stockfish_path_canon, stockfish_version)
        )
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initializes the DBManager and connects to the SQLite database."""
        self.db_path: str = os.path.realpath(db_path or settings.DB_CACHE_FILENAME)
        self._conn: Optional[sqlite3.Connection] = None
        self._is_closed: bool = False

        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            self._conn = sqlite3.connect(self.db_path, timeout=10)
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._conn.execute(self._CREATE_TABLE_SQL)
            self._conn.commit()
            logger.info(f"SQLite cache '{self.db_path}' initialized/connected successfully.")
        except sqlite3.Error as e:
            logger.error(f"Error initializing SQLite DB '{self.db_path}': {e}", exc_info=True)
            self.close()
            raise CacheConnectionError(f"Failed to initialize SQLite cache at '{self.db_path}'") from e

    def _ensure_connected(self) -> sqlite3.Connection:
        """Ensures the database connection is active, returning the connection."""
        if self._is_closed:
            raise CacheError("Operation on a closed DBManager.")
        if self._conn is None:
            raise CacheConnectionError("Database connection is not active.")
        return self._conn

    def get_cached_analysis(self, key: CacheKey) -> Optional[List[Dict[str, Any]]]:
        """Retrieves a single cached analysis result using a structured key."""
        conn = self._ensure_connected()
        query = f"SELECT analysis_result_json FROM {self._TABLE_NAME} WHERE fen=? AND analysis_depth=? AND multipv_count=? AND stockfish_path_canon=? AND stockfish_version=?"
        key_tuple = (key.fen, key.analysis_depth, key.multipv_count, key.stockfish_path_canon, key.stockfish_version)
        
        try:
            cursor = conn.cursor()
            cursor.execute(query, key_tuple)
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"JSONDecodeError for cached key {key}: {e}. Treating as cache miss.")
            return None
        except sqlite3.Error as e:
            raise CacheReadError(f"Failed to read from cache for key {key}") from e

    # --- NEW OPTIMIZED BATCH READ METHOD ---
    def get_cached_analyses_batch(
        self,
        fens: List[str],
        analysis_depth: int,
        multipv_count: int,
        stockfish_path_canon: str,
        stockfish_version: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieves all available cached results for a list of FENs in a single query.

        Args:
            fens: A list of FEN strings to look up.
            Other args: The analysis parameters that must match.

        Returns:
            A dictionary mapping each FEN found in the cache to its analysis result.
            FENs not found in the cache will be absent from the dictionary.
        """
        if not fens:
            return {}
        
        conn = self._ensure_connected()
        
        # Using a parameterized query with a list of FENs
        # The '?' placeholders are generated dynamically based on the number of FENs
        placeholders = ','.join('?' for _ in fens)
        query = f"""
            SELECT fen, analysis_result_json FROM {self._TABLE_NAME}
            WHERE analysis_depth = ?
              AND multipv_count = ?
              AND stockfish_path_canon = ?
              AND stockfish_version = ?
              AND fen IN ({placeholders})
        """
        
        params = [analysis_depth, multipv_count, stockfish_path_canon, stockfish_version] + fens
        
        results: Dict[str, List[Dict[str, Any]]] = {}
        try:
            cursor = conn.cursor()
            for row in cursor.execute(query, params):
                fen, analysis_json = row
                try:
                    results[fen] = json.loads(analysis_json)
                except json.JSONDecodeError:
                    logger.warning(f"Corrupted JSON found in cache for FEN {fen}. Skipping.")
                    continue
            return results
        except sqlite3.Error as e:
            raise CacheReadError("Failed to perform batch read from cache") from e

    # ... (store_analyses_batch, close, __enter__, __exit__ remain the same) ...
    def store_analyses_batch(self, entries: List[CacheEntry]) -> None:
        if not entries: return
        conn = self._ensure_connected()
        insert_query = f"INSERT OR REPLACE INTO {self._TABLE_NAME} (fen, analysis_depth, multipv_count, stockfish_path_canon, stockfish_version, analysis_result_json) VALUES (?, ?, ?, ?, ?, ?)"
        try:
            data_to_insert = [(e.key.fen, e.key.analysis_depth, e.key.multipv_count, e.key.stockfish_path_canon, e.key.stockfish_version, json.dumps(e.analysis_result)) for e in entries]
        except (TypeError, OverflowError) as e:
            raise CacheWriteError("Failed to serialize one or more analysis results to JSON.") from e
        cursor = conn.cursor()
        try:
            cursor.executemany(insert_query, data_to_insert)
            conn.commit()
            logger.debug(f"Successfully stored {len(entries)} entries in the cache.")
        except sqlite3.Error as e:
            logger.error(f"SQLite error during batch cache store: {e}", exc_info=True)
            try: conn.rollback()
            except sqlite3.Error as rb_e: logger.error(f"Rollback failed after batch store error: {rb_e}")
            raise CacheWriteError("Failed to store analysis batch in cache.") from e

    def close(self) -> None:
        if self._is_closed: return
        logger.info(f"Closing SQLite cache connection to '{self.db_path}'.")
        if self._conn:
            try: self._conn.close()
            except sqlite3.Error as e: logger.error(f"Error closing SQLite DB connection: {e}", exc_info=True)
        self._conn = None
        self._is_closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()