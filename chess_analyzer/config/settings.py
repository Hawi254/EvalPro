# chess_analyzer_project/chess_analyzer/config/settings.py
"""
Configuration settings for the Chess Analyzer application.

This module centralizes all tunable parameters, default values, thresholds,
and file paths used throughout the application. This approach promotes
maintainability by providing a single source of truth for configuration.
"""
from typing import Final, List, Tuple

# Import the data contract definitions from our new types module
from chess_analyzer.types import BrilliantMoveCriteria, GreatMoveCriteria

# --- Analysis Defaults ---
DEFAULT_ANALYSIS_DEPTH: Final[int] = 18
"""Default depth for Stockfish analysis."""

DEFAULT_MULTI_PV: Final[int] = 2
"""
Default number of lines (principal variations) Stockfish should analyze.
Set to 1 for speed. Set to 2 or more to enable Great Move detection.
"""

# --- Stockfish Engine Parameters ---
# Sensible default, can be overridden by CLI.
DEFAULT_STOCKFISH_THREADS: Final[int] = 4
"""Default number of CPU threads for Stockfish."""

DEFAULT_STOCKFISH_HASH_MB: Final[int] = 1024
"""Default hash memory (in MB) for Stockfish."""

# --- Score Interpretation and Normalization ---
MATE_SCORE_EQUIVALENT_CP: Final[float] = 30000.0
"""A large centipawn value used to numerically represent a mate."""

CPL_INDIVIDUAL_EVAL_CAP_CP: Final[float] = 1000.0
"""Maximum absolute centipawn value for individual move evaluations before CPL calculation."""

ACPL_MOVE_CPL_CAP_CP: Final[float] = 1000.0
"""Maximum CPL value for a single move when calculating average CPL or accuracy."""

# --- PGN Annotation Details ---
PV_MAX_MOVES_IN_COMMENT: Final[int] = 3
"""Maximum number of moves from the PV of the best engine line to include in a comment."""

PGN_DEFAULT_COLUMNS: Final[int] = 80
"""Default PGN move text wrapping width for output files."""


# --- CPL-based Move Classification Thresholds (Data-Driven) ---
# The list is ordered from best to worst.
# The classification logic will iterate through this list.
MOVE_CLASSIFICATION_THRESHOLDS: Final[List[Tuple[str, float]]] = [
    # (Classification Name, Max CPL for this category)
    ("Best", 5.0),
    ("Good", 40.0),
    ("OK", 70.0),
    ("Dubious", 90.0),
    ("Inaccuracy", 180.0),
    ("Mistake", 300.0),
    # The final category, "Blunder", is for any CPL above the last threshold.
]


# --- Brilliant & Great Move Detection Criteria (Default Instances) ---
# The definitions for these dataclasses live in `types.py`. This module
# creates the default, constant instances of them.
BRILLIANT_CRITERIA: Final[BrilliantMoveCriteria] = BrilliantMoveCriteria(
    max_cpl=20.0,
    eval_drop_leniency_cp=15.0,
    max_eval_before_move_cp=350.0,
    min_sacrifice_net_material_pawns=2.5,
)

GREAT_CRITERIA: Final[GreatMoveCriteria] = GreatMoveCriteria(
    min_uniqueness_gain_cp=120.0,
)


# --- File Names and Paths ---
DB_CACHE_FILENAME: Final[str] = "chess_analyzer_cache.db"
"""Filename for the SQLite database used for caching FEN analyses."""

DEFAULT_CUSTOM_REPORT_FILENAME: Final[str] = "analysis_summary_report.csv"
"""Default filename for the generated CSV summary report."""

DEFAULT_LOG_FILENAME: Final[str] = "chess_analyzer.log"
"""Default filename for the application log."""

# --- PGN Parsing and Error Handling ---
PGN_MALFORMED_SKIP_LINE_LIMIT: Final[int] = 1000
"""Maximum number of lines to skip when encountering a malformed PGN entry."""

# --- Logging ---
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
"""Default logging level for the application."""

# --- Application Specific ---
APP_NAME: Final[str] = "ChessAnalyzer"
"""Application name, used for logging and other identifiers."""

STOCKFISH_VERSION_UNKNOWN: Final[str] = "Unknown"
"""Placeholder for when the Stockfish version cannot be determined."""

# --- Lichess Accuracy Calculation Constants ---
# Formula: A * exp(B * avg_cpl) + C
ACCURACY_CONSTANT_A: Final[float] = 103.1668
ACCURACY_CONSTANT_B: Final[float] = -0.004354
ACCURACY_CONSTANT_C: Final[float] = -3.1668