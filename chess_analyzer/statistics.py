# chess_analyzer_project/chess_analyzer/statistics.py
"""
Manages statistics tracking for the Chess Analyzer application.

This module provides the StatisticsTracker class, a centralized component
for aggregating and reporting metrics from an analysis run.
"""
import logging
import os
from collections import Counter
from typing import Optional

from chess_analyzer.config import settings

logger = logging.getLogger(settings.APP_NAME + ".Statistics")


class StatisticsTracker:
    """
    A stateful class to aggregate and report statistics for an analysis run.
    """

    def __init__(self):
        """Initializes the StatisticsTracker with all counters set to zero."""
        self.stats: Counter[str] = Counter()
        self.games_summarized_for_report: int = 0
        self.db_path: Optional[str] = None
        self.report_path: Optional[str] = None
        logger.debug("StatisticsTracker initialized.")

    def reset(self) -> None:
        """Resets all statistics to their initial state for a new run."""
        self.stats.clear()
        self.games_summarized_for_report = 0
        self.db_path = None
        self.report_path = None
        logger.info("StatisticsTracker has been reset.")

    def add_game_read(self) -> None:
        """Increments the counter for total games read from the PGN."""
        self.stats["games_read"] += 1

    def add_game_skipped(self, reason: str) -> None:
        """Increments the counter for skipped games, categorized by reason."""
        self.stats["games_skipped_total"] += 1
        self.stats[f"skipped_{reason}"] += 1

    def add_game_analyzed(self) -> None:
        """Increments the counter for successfully analyzed and annotated games."""
        self.stats["games_analyzed"] += 1

    def add_game_with_error(self) -> None:
        """Increments the counter for games that failed due to a critical error."""
        self.stats["games_with_errors"] += 1

    def add_fen_cache_hits(self, count: int) -> None:
        """Adds to the total count of FENs found in the cache."""
        self.stats["fen_cache_hits"] += count

    def add_fens_analyzed_by_engine(self, count: int) -> None:
        """Adds to the total count of FENs sent to the engine for analysis."""
        self.stats["fens_analyzed_by_engine"] += count

    def set_games_summarized_for_report(self, count: int) -> None:
        """Sets the final number of games included in the CSV report."""
        self.games_summarized_for_report = count

    def set_db_path(self, path: str) -> None:
        """Stores the path to the database file for final reporting."""
        self.db_path = os.path.abspath(path)

    def set_report_path(self, path: str) -> None:
        """Stores the path to the CSV report file for final reporting."""
        self.report_path = os.path.abspath(path)

    def log_summary(self) -> None:
        """
        Logs a formatted summary of all collected statistics for the run.
        """
        logger.info("\n--- Analysis Run Summary ---")

        # Define display order and formatting for clarity in the final log output.
        display_order = [
            ("games_read", "Total Games Read from PGN"),
            ("games_analyzed", "Games Fully Analyzed"),
            ("games_skipped_total", "Total Games Skipped"),
            ("skipped_already_processed", "  - Skipped (Already Processed)"),
            ("skipped_no_moves", "  - Skipped (No Moves Found)"),
            ("games_with_errors", "Games with Critical Errors"),
            ("fen_cache_hits", "FENs Found in Cache"),
            ("fens_analyzed_by_engine", "FENs Analyzed by Engine"),
        ]

        for key, display_text in display_order:
            if key in self.stats:  # Only display if the key has been populated
                logger.info(f"{display_text}: {self.stats[key]}")

        logger.info(f"Games Included in Report: {self.games_summarized_for_report}")
        logger.info("---")
        
        if self.db_path:
            logger.info(f"FEN Cache Database: '{self.db_path}'")
        if self.report_path:
            # Check if the report was actually created before logging success
            if self.games_summarized_for_report > 0 and os.path.exists(self.report_path):
                logger.info(f"CSV Report Generated: '{self.report_path}'")
            else:
                logger.info(f"CSV Report Target (not generated as no summaries): '{self.report_path}'")