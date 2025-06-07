# chess_analyzer_project/chess_analyzer/types.py
"""
A central module for shared data structures and type definitions.
...
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Protocol # <-- Add Protocol

import chess
import chess.pgn

# --- All existing dataclasses remain the same ---
# ... (BrilliantMoveCriteria, MoveData, CacheKey, etc.) ...
@dataclass(frozen=True)
class BrilliantMoveCriteria:
    """Encapsulates all criteria for detecting a 'Brilliant ✨' move."""
    max_cpl: float
    eval_drop_leniency_cp: float
    max_eval_before_move_cp: float
    min_sacrifice_net_material_pawns: float

@dataclass(frozen=True)
class GreatMoveCriteria:
    """Encapsulates all criteria for detecting a 'Great Move !'."""
    min_uniqueness_gain_cp: float

@dataclass(frozen=True)
class MoveData:
    """A structured container for data related to a single move in a game."""
    pgn_node: chess.pgn.GameNode
    actual_move_obj: chess.Move
    board_before_move: chess.Board
    fen_before_move: str
    fen_after_move: str

@dataclass(frozen=True)
class CacheKey:
    """A type-safe structure for the composite cache key."""
    fen: str
    analysis_depth: int
    multipv_count: int
    stockfish_path_canon: str
    stockfish_version: str

@dataclass
class CacheEntry:
    """Represents a full record to be inserted into the cache."""
    key: CacheKey
    analysis_result: List[Dict[str, Any]]

@dataclass(frozen=True)
class ClassificationResult:
    """Represents the result of a move classification."""
    classification_text: str
    cpl: float  # CPL for metrics (capped, >= 0)
    raw_cpl: float # Raw CPL (can be negative)
    is_brilliant: bool = False
    is_great: bool = False
    is_engine_top_choice: bool = False
    is_engine_top_n_choice: bool = False

@dataclass(frozen=True)
class MoveAnalysisContext:
    """A container for all data required by the MoveClassifier."""
    # Evals from player's perspective (positive is good)
    eval_best_move: Optional[float]
    is_mate_best_move: bool
    eval_second_best_move: Optional[float]
    is_mate_second_best_move: bool
    eval_player_move: Optional[float]
    is_mate_player_move: bool
    eval_before_move: Optional[float]
    is_mate_before_move: bool
    # Supporting data
    engine_top_lines: List[Dict[str, Any]]
    player_move_uci: str
    board_before_move: chess.Board
    board_after_move: chess.Board
    player_color: chess.Color
    engine_multipv: int
    brilliant_criteria: BrilliantMoveCriteria
    great_criteria: GreatMoveCriteria

@dataclass(frozen=True)
class EngineLineInfo:
    """Holds pre-formatted data for a single engine analysis line for annotation."""
    move_san: str
    eval_str: str  # e.g., "+1.23" or "#-3"
    is_best_line: bool = False
    pv_san_list: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class AnnotationContext:
    """A container for all data required by the Annotator."""
    classification: Optional[ClassificationResult]
    eval_after_move_wpov_str: str  # e.g., "[%eval +0.50,20]"
    clk_comment_part: str
    user_comment_part: str
    engine_lines: List[EngineLineInfo]
    analysis_depth: int
    multipv_setting: int

@dataclass(frozen=True)
class GameSummary:
    """A structured container for all statistics of a single analyzed game."""
    game_id: str
    analyzed_player_name: str
    player_color_str: str
    player_cpls: List[float]
    move_classification_counts: Dict[str, int]
    engine_top1_match_count: int
    engine_topN_match_count: int
    pgn_headers: Dict[str, str]

@dataclass(frozen=True)
class ProcessedGameResult:
    """The final output from processing a single game."""
    annotated_game: chess.pgn.Game
    summary: Optional[GameSummary]

# --- NEW PROTOCOL FOR PROGRESS REPORTING ---
class ProgressReporter(Protocol):
    """
    A protocol defining the interface for reporting progress.
    This allows the core logic to report progress without being tied
    to a specific UI implementation like tqdm.
    """
    def reset(self, total: int = 0) -> None:
        """Resets the reporter for a new task with a given total."""
        ...

    def update(self, n: int = 1) -> None:
        """Updates the progress by n steps."""
        ...

    def set_description(self, desc: str) -> None:
        """Sets the description text for the current task."""
        ...

    def close(self) -> None:
        """Closes or finalizes the progress display."""
        ...