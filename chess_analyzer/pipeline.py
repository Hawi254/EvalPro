# chess_analyzer_project/chess_analyzer/pipeline.py
"""
The main analysis pipeline for the Chess Analyzer application.
...
"""
import logging
import os
import time
import threading
from typing import Optional, List
from tqdm import tqdm

# Import services and data contracts
from chess_analyzer.engine.stockfish_controller import StockfishController, StockfishError
from chess_analyzer.cache.db_manager import DBManager, CacheError
from chess_analyzer.pgn.pgn_handler import PGNHandler, PGNError
from chess_analyzer.analysis.move_classifier import MoveClassifier
from chess_analyzer.analysis.annotator import Annotator
from chess_analyzer.reporting.report_generator import ReportGenerator, ReportGenerationError
from chess_analyzer.statistics import StatisticsTracker
from chess_analyzer.game_processor import GameProcessor
from chess_analyzer.analysis.analysis_provider import AnalysisProvider # New Import
from chess_analyzer.utils.signal_manager import SignalManager
from chess_analyzer.config import settings
from chess_analyzer.types import GameSummary, ProgressReporter # New Import

logger = logging.getLogger(settings.APP_NAME + ".Pipeline")

# --- TQDM Adapter for our ProgressReporter Protocol ---
class TqdmProgressReporter:
    """An adapter that makes a tqdm progress bar conform to our ProgressReporter protocol."""
    def __init__(self, pbar: tqdm):
        self._pbar = pbar

    def reset(self, total: int = 0) -> None:
        self._pbar.reset(total=total)

    def update(self, n: int = 1) -> None:
        self._pbar.update(n)

    def set_description(self, desc: str) -> None:
        self._pbar.set_description_str(desc)
    
    def close(self) -> None:
        self._pbar.close()

class AnalysisPipeline:
    """
    Orchestrates the full chess analysis workflow from PGN input to report output.
    """

    def __init__(self, stockfish_path: str, **kwargs):
        """Initializes the entire application stack via dependency injection."""
        # --- Core Parameters ---
        self.analysis_depth = kwargs.get('analysis_depth', settings.DEFAULT_ANALYSIS_DEPTH)
        self.multipv_count = kwargs.get('multipv_count', settings.DEFAULT_MULTI_PV)
        self.stockfish_path = os.path.realpath(stockfish_path)
        
        # --- Component Initialization ---
        self.pgn_handler = PGNHandler(pgn_output_columns=kwargs.get('pgn_write_columns', settings.PGN_DEFAULT_COLUMNS))
        self.db_manager = DBManager()
        self.stockfish_controller = StockfishController(path=self.stockfish_path, depth=self.analysis_depth, **kwargs)
        self.move_classifier = MoveClassifier()
        
        sf_version = self.stockfish_controller.get_stockfish_version()
        engine_short_name = f"SF{sf_version.split('.')[0]}" if sf_version and sf_version != settings.STOCKFISH_VERSION_UNKNOWN else "Engine"
        self.annotator = Annotator(engine_name=engine_short_name)
        
        self.report_generator = ReportGenerator()
        self.stats_tracker = StatisticsTracker()

        # --- NEW: Initialize the AnalysisProvider ---
        self.analysis_provider = AnalysisProvider(
            analysis_depth=self.analysis_depth,
            multipv_count=self.multipv_count,
            stockfish_path=self.stockfish_path,
            stockfish_version=sf_version,
            db_manager=self.db_manager,
            stockfish_controller=self.stockfish_controller
        )

        # --- UPDATED: Worker Initialization (Injecting the new provider) ---
        self.game_processor = GameProcessor(
            analysis_depth=self.analysis_depth,
            multipv_count=self.multipv_count,
            pgn_handler=self.pgn_handler,
            analysis_provider=self.analysis_provider, # Inject the provider
            move_classifier=self.move_classifier,
            annotator=self.annotator
        )
        
        self.shutdown_event = threading.Event()

    def run(self, input_pgn_path: str, output_pgn_path: str, **kwargs):
        """Executes the main analysis run."""
        start_time = time.time()
        self.stats_tracker.reset()
        
        target_player = kwargs.get('target_player')
        report_file = kwargs.get('report_path') or settings.DEFAULT_CUSTOM_REPORT_FILENAME
        self.stats_tracker.set_report_path(report_file)
        self.stats_tracker.set_db_path(self.db_manager.db_path)

        logger.info(f"Starting analysis run...")

        with SignalManager(self.shutdown_event), self.db_manager, self.stockfish_controller:
            try:
                processed_ids = self.pgn_handler.get_processed_game_ids(output_pgn_path)
                self.stats_tracker.add_game_skipped(f"already_processed', {len(processed_ids)}")
                game_summaries: List[GameSummary] = []
                
                with open(output_pgn_path, 'a+', encoding='utf-8') as outfile, \
                     tqdm(total=0, unit="FENs", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}") as fen_pbar:
                    
                    fen_progress_reporter = TqdmProgressReporter(fen_pbar)

                    for game in self.pgn_handler.stream_games(input_pgn_path, self.shutdown_event):
                        if self.shutdown_event.is_set(): break
                        self.stats_tracker.add_game_read()
                        
                        try:
                            result, cache_hits, engine_runs = self.game_processor.process_game(
                                game, target_player, fen_progress_reporter
                            )
                            
                            self.stats_tracker.add_fen_cache_hits(cache_hits)
                            self.stats_tracker.add_fens_analyzed_by_engine(engine_runs)

                            self.pgn_handler.export_annotated_game(result.annotated_game, outfile)
                            self.stats_tracker.add_game_analyzed()
                            
                            if result.summary:
                                game_summaries.append(result.summary)
                                
                        except (StockfishError, CacheError, PGNError) as e:
                            logger.error(f"Critical error processing game: {e}. Skipping.", exc_info=False)
                            self.stats_tracker.add_game_with_error()
                            continue

                if game_summaries:
                    self.stats_tracker.set_games_summarized_for_report(len(game_summaries))
                    self.report_generator.generate_csv_report(game_summaries, report_file)

            except Exception as e:
                logger.critical(f"An unexpected fatal error occurred in the pipeline: {e}", exc_info=True)
            finally:
                run_duration = time.time() - start_time
                logger.info(f"Analysis run finished in {run_duration:.2f} seconds.")
                self.stats_tracker.log_summary()