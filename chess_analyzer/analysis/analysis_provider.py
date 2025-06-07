# chess_analyzer_project/chess_analyzer/analysis/analysis_provider.py
"""
Provides chess analysis data by coordinating cache and engine services.

This module contains the AnalysisProvider class, which is responsible for
efficiently fetching engine analyses for all required positions in a game.
It encapsulates the logic of checking the cache first, then running the
engine for any cache misses, and finally caching the new results.
"""
import logging
from typing import Dict, List, Any, Optional, Set, Tuple

import chess.pgn

# Import services and data contracts
from chess_analyzer.engine.stockfish_controller import StockfishController
from chess_analyzer.cache.db_manager import DBManager, CacheKey, CacheEntry
from chess_analyzer.pgn.pgn_handler import PGNHandler
from chess_analyzer.types import ProgressReporter, MoveData
from chess_analyzer.exceptions import StockfishError, CacheError

logger = logging.getLogger(__name__.split('.')[0] + ".AnalysisProvider")


class AnalysisProvider:
    """
    A service that fetches engine analyses, using a cache-first strategy.
    """

    def __init__(
        self,
        # --- Analysis Parameters ---
        analysis_depth: int,
        multipv_count: int,
        stockfish_path: str,
        stockfish_version: str,
        # --- Service Components (Injected) ---
        db_manager: DBManager,
        stockfish_controller: StockfishController,
    ):
        """
        Initializes the AnalysisProvider with required components and settings.
        """
        self.analysis_depth = analysis_depth
        self.multipv_count = multipv_count
        self.stockfish_path = stockfish_path
        self.stockfish_version = stockfish_version
        self.db_manager = db_manager
        self.stockfish_controller = stockfish_controller

        logger.debug("AnalysisProvider initialized.")

    def _get_required_fens(self, game: chess.pgn.Game) -> Set[str]:
        """
        Performs a quick pass over a game to identify all FENs that will require analysis.
        This ensures we analyze the starting position and the position after every move.
        """
        required_fens: Set[str] = set()
        board = game.board()
        required_fens.add(board.fen())

        for node in game.mainline():
            if not node.move:
                continue
            
            # We need the analysis for the position *before* the move...
            required_fens.add(board.fen())
            # ...and the position *after* the move.
            board.push(node.move)
            required_fens.add(board.fen())
        
        return required_fens

    def get_analyses_for_game(
        self, game: chess.pgn.Game, progress: ProgressReporter
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], int, int]:
        """
        The single public method for this class. It encapsulates all the logic
        for planning and fetching analyses for a given game.

        Returns:
            A tuple of (analyses_dict, cache_hits, engine_analyses_count).
        """
        # Step 1: Plan the analysis by finding all unique positions.
        required_fens = self._get_required_fens(game)
        if not required_fens:
            return {}, 0, 0
        
        progress.reset(total=len(required_fens))
        game_id_short = (game.headers.get("GameId") or "N/A")[:8]
        
        # Step 2: Fetch all possible results from the cache in a single batch.
        progress.set_description(f"  Game {game_id_short} (Cache)")
        cached_analyses = self.db_manager.get_cached_analyses_batch(
            fens=list(required_fens),
            analysis_depth=self.analysis_depth,
            multipv_count=self.multipv_count,
            stockfish_path_canon=self.stockfish_path,
            stockfish_version=self.stockfish_version,
        )
        cache_hits = len(cached_analyses)
        progress.update(cache_hits)

        # Step 3: Determine which FENs were cache misses and need engine analysis.
        all_analyses = cached_analyses.copy()
        fens_to_analyze = [fen for fen in required_fens if fen not in cached_analyses]
        engine_runs = len(fens_to_analyze)

        # Step 4: Run the engine for all cache misses in a single batch.
        if fens_to_analyze:
            progress.set_description(f"  Game {game_id_short} (Engine)")
            
            # The progress callback is passed directly to the engine controller.
            engine_callback = lambda: progress.update(1)
            
            newly_analyzed = self.stockfish_controller.analyze_fens_batch(
                fens_to_analyze, progress_callback=engine_callback
            )
            all_analyses.update(newly_analyzed)

            # Step 5: Cache the new results for future runs.
            entries_to_cache = [
                CacheEntry(
                    key=CacheKey(fen, self.analysis_depth, self.multipv_count, self.stockfish_path, self.stockfish_version),
                    analysis_result=result
                )
                for fen, result in newly_analyzed.items() if result is not None
            ]
            if entries_to_cache:
                self.db_manager.store_analyses_batch(entries_to_cache)

        return all_analyses, cache_hits, engine_runs