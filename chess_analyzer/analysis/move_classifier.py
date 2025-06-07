# chess_analyzer_project/chess_analyzer/analysis/move_classifier.py
"""
Classifies chess moves based on engine analysis and defined heuristics.

This module provides the `MoveClassifier` class, which evaluates player moves
by calculating Centipawn Loss (CPL), and identifies special categories like
"Brilliant" or "Great" moves according to specific criteria.
"""
import logging
from typing import Optional

import chess

from chess_analyzer.config import settings
from chess_analyzer.types import ClassificationResult, MoveAnalysisContext
from chess_analyzer.utils.chess_utils import get_material_diff

logger = logging.getLogger(settings.APP_NAME + ".MoveClassifier")

# --- Helper Function ---
def _cap_score(score_cp: Optional[float], is_mate: bool) -> float:
    """Caps a regular centipawn evaluation, leaving mate scores untouched."""
    if score_cp is None:
        return 0.0
    if is_mate:
        return score_cp
    cap = settings.CPL_INDIVIDUAL_EVAL_CAP_CP
    return min(cap, max(-cap, score_cp))


class MoveClassifier:
    """Analyzes and classifies chess moves based on engine evaluations and heuristics."""

    def __init__(self):
        """Initializes the MoveClassifier."""
        logger.debug("MoveClassifier initialized.")

    def _is_significant_piece_sacrifice(self, context: MoveAnalysisContext) -> bool:
        """Determines if a move involved a significant piece sacrifice."""
        diff_before = get_material_diff(context.board_before_move, context.player_color)
        diff_after = get_material_diff(context.board_after_move, context.player_color)
        
        # A sacrifice means the player's material advantage decreased.
        # e.g., before: +1 (up a pawn), after: -2 (down a knight for the pawn).
        # Change in diff = (-2) - (1) = -3. Net loss is 3.
        net_material_loss = diff_before - diff_after
        
        criteria = context.brilliant_criteria
        return net_material_loss >= criteria.min_sacrifice_net_material_pawns

    def _check_for_brilliant(self, context: MoveAnalysisContext, raw_cpl: float) -> Optional[ClassificationResult]:
        """Checks if a move qualifies as 'Brilliant ✨'."""
        criteria = context.brilliant_criteria
        
        # Condition 0: Required evals must exist.
        if context.eval_player_move is None or context.eval_before_move is None:
            return None
        
        # Condition 1: Move is objectively good (low raw CPL).
        if raw_cpl > criteria.max_cpl:
            return None

        # Condition 2: Position was not already decisively won.
        if context.is_mate_before_move and context.eval_before_move > 0:
             return None # Already delivering mate.
        if not context.is_mate_before_move and context.eval_before_move > criteria.max_eval_before_move_cp:
            return None

        # Condition 3: Evaluation after the move is sound (doesn't drop too much).
        eval_drop = context.eval_before_move - context.eval_player_move
        if eval_drop > criteria.eval_drop_leniency_cp:
            return None
            
        # Condition 4: Involves a significant piece sacrifice.
        if not self._is_significant_piece_sacrifice(context):
            return None

        logger.debug(f"Move {context.player_move_uci} by {chess.COLOR_NAMES[context.player_color]} classified as Brilliant.")
        return ClassificationResult("Brilliant ✨", 0.0, raw_cpl, is_brilliant=True)

    def _check_for_great(self, context: MoveAnalysisContext, is_top_choice: bool) -> Optional[ClassificationResult]:
        """Checks if a move qualifies as 'Great Move !'."""
        criteria = context.great_criteria

        # Condition 1: Player played the engine's best move, and MultiPV >= 2.
        if not is_top_choice or context.engine_multipv < 2:
            return None
            
        # Condition 2: Required evals must exist.
        if context.eval_best_move is None or context.eval_second_best_move is None:
            return None

        # Condition 3: Not a mate scenario (where CPL is less meaningful).
        if context.is_mate_best_move or context.is_mate_second_best_move:
            return None

        # Condition 4: The best move is significantly better than the second best.
        uniqueness_gain = context.eval_best_move - context.eval_second_best_move
        if uniqueness_gain < criteria.min_uniqueness_gain_cp:
            return None

        logger.debug(f"Move {context.player_move_uci} by {chess.COLOR_NAMES[context.player_color]} classified as Great.")
        # CPL for a great move is 0, as it's the engine's best.
        return ClassificationResult("Great Move !", 0.0, 0.0, is_great=True, is_engine_top_choice=True, is_engine_top_n_choice=True)

    def _get_standard_classification(self, cpl: float) -> str:
        """Gets the classification text based on CPL using the data-driven settings."""
        for name, threshold in settings.MOVE_CLASSIFICATION_THRESHOLDS:
            if cpl <= threshold:
                return name
        return "Blunder" # Fallback for anything above the last threshold

    def classify_move(self, context: MoveAnalysisContext) -> ClassificationResult:
        """
        Classifies a player's move using a structured context and delegates to helpers.
        """
        # --- Pre-calculation ---
        if context.eval_best_move is None or context.eval_player_move is None:
            return ClassificationResult("Unavailable (eval error)", 0.0, 0.0)

        capped_eval_best = _cap_score(context.eval_best_move, context.is_mate_best_move)
        capped_eval_player = _cap_score(context.eval_player_move, context.is_mate_player_move)
        
        raw_cpl = capped_eval_best - capped_eval_player
        cpl_for_metrics = min(settings.ACPL_MOVE_CPL_CAP_CP, max(0.0, raw_cpl))

        is_top_choice = bool(context.engine_top_lines and context.player_move_uci == context.engine_top_lines[0].get('Move'))
        is_top_n_choice = is_top_choice or any(
            context.player_move_uci == line.get('Move') for line in context.engine_top_lines
        )

        # --- Classification Logic (Delegation) ---
        
        # 1. Check for Brilliant (highest priority)
        if (brilliant_result := self._check_for_brilliant(context, raw_cpl)):
            # Use dataclasses.replace to create a new instance with updated fields
            return brilliant_result.__class__(
                **brilliant_result.__dict__, 
                is_engine_top_choice=is_top_choice, 
                is_engine_top_n_choice=is_top_n_choice
            )

        # 2. Check for Great
        if (great_result := self._check_for_great(context, is_top_choice)):
            return great_result

        # 3. Standard CPL-based classification
        classification_name = self._get_standard_classification(cpl_for_metrics)
        
        # Add CPL to the text for user feedback, unless it's the best move.
        if classification_name == "Best":
            classification_text = classification_name
        elif classification_name == "Blunder":
            classification_text = f"Blunder !!! (CPL: {cpl_for_metrics:.0f})"
        else:
            classification_text = f"{classification_name} (CPL: {cpl_for_metrics:.0f})"

        return ClassificationResult(
            classification_text=classification_text,
            cpl=cpl_for_metrics,
            raw_cpl=raw_cpl,
            is_engine_top_choice=is_top_choice,
            is_engine_top_n_choice=is_top_n_choice
        )