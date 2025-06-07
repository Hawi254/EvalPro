# chess_analyzer_project/chess_analyzer/game_processor.py
"""
Processes a single chess game from analysis to annotation.

This module contains the GameProcessor class, which encapsulates the logic
for analyzing all moves in a single game, classifying them, and preparing
the game for final output. It delegates data fetching to an AnalysisProvider.
"""
import logging
from typing import List, Optional, Tuple

import chess.pgn

# Import services and data contracts
from chess_analyzer.analysis.analysis_provider import AnalysisProvider
from chess_analyzer.pgn.pgn_handler import PGNHandler
from chess_analyzer.analysis.move_classifier import MoveClassifier
from chess_analyzer.analysis.annotator import Annotator
from chess_analyzer.types import (
    ProcessedGameResult,
    ClassificationResult,
    ProgressReporter,
)
import chess_analyzer.context_builders as builders
from chess_analyzer.exceptions import StockfishError, CacheError, PGNError

logger = logging.getLogger(__name__.split('.')[0] + ".GameProcessor")


class GameProcessor:
    """
    A worker that executes the move-by-move analysis workflow for a game,
    using pre-fetched analysis data.
    """

    def __init__(
        self,
        # --- Analysis Parameters (for context builders) ---
        analysis_depth: int,
        multipv_count: int,
        # --- Service Components (Injected) ---
        pgn_handler: PGNHandler,
        analysis_provider: AnalysisProvider, # The new provider
        move_classifier: MoveClassifier,
        annotator: Annotator,
    ):
        """Initializes the GameProcessor with required components and settings."""
        self.analysis_depth = analysis_depth
        self.multipv_count = multipv_count
        self.pgn_handler = pgn_handler
        self.analysis_provider = analysis_provider
        self.move_classifier = move_classifier
        self.annotator = annotator
        logger.debug("GameProcessor initialized.")

    def process_game(
        self,
        game: chess.pgn.Game,
        target_player: Optional[str],
        progress: ProgressReporter,
    ) -> Tuple[ProcessedGameResult, int, int]:
        """
        Executes an efficient, targeted processing pipeline for a single game.
        """
        game_id = self.pgn_handler.extract_game_id(game.headers) or "N/A"

        # Step 1: Delegate ALL data fetching to the new provider.
        # This one call replaces a large block of complex logic.
        all_analyses, cache_hits, engine_runs = self.analysis_provider.get_analyses_for_game(
            game, progress
        )
        
        # Step 2: Extract move data (this is a simple, fast operation)
        move_data_list, _ = self.pgn_handler.collect_move_data_and_fens(game)

        if not move_data_list:
            logger.info(f"Game {game_id} has no moves to process.")
            return ProcessedGameResult(annotated_game=game, summary=None), 0, 0
        
        # --- The GameProcessor's CORE responsibility: move-by-move workflow ---
        all_classification_results: List[ClassificationResult] = []
        for move_data in move_data_list:
            move_context = builders.build_move_analysis_context(move_data, all_analyses, self.multipv_count)
            class_result = self.move_classifier.classify_move(move_context)
            all_classification_results.append(class_result)
            
            annotation_context = builders.build_annotation_context(
                move_data=move_data, result=class_result, analyses=all_analyses,
                analysis_depth=self.analysis_depth, multipv_setting=self.multipv_count,
                prepare_comment_func=self.annotator.prepare_context_from_existing_comment
            )
            move_data.pgn_node.comment = self.annotator.generate_pgn_node_comment(annotation_context)
            
        # Step 3: Finalize the results
        game_summary = builders.build_game_summary(game, game_id, target_player, all_classification_results)
        self._add_final_pgn_headers(game, all_classification_results)
        result = ProcessedGameResult(annotated_game=game, summary=game_summary)
        
        return result, cache_hits, engine_runs

    def _add_final_pgn_headers(self, game: chess.pgn.Game, results: List[ClassificationResult]):
        """Adds calculated ACPL values to the game headers."""
        white_cpls = [r.cpl for i, r in enumerate(results) if i % 2 == 0]
        black_cpls = [r.cpl for i, r in enumerate(results) if i % 2 != 0]
        
        game.headers["WhiteACPL"] = f"{sum(white_cpls) / len(white_cpls):.1f}" if white_cpls else "0.0"
        game.headers["BlackACPL"] = f"{sum(black_cpls) / len(black_cpls):.1f}" if black_cpls else "0.0"