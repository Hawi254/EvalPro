# chess_analyzer_project/main.py
"""
Main entry point for the ChessAnalyzer application.

This script handles command-line argument parsing, sets up logging,
and initiates the analysis process by creating and running the main
AnalysisPipeline.
"""
import argparse
import logging
import os
import sys
from typing import Optional

# Adjust the Python path to include the project's root directory.
# This allows the script to be run directly from the project root via `python main.py`.
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from chess_analyzer.pipeline import AnalysisPipeline
from chess_analyzer.utils.logging_config import setup_logging
from chess_analyzer.config import settings

def find_stockfish_executable() -> Optional[str]:
    """Tries to find the Stockfish executable in common locations."""
    # Priority 1: Environment variable
    if 'STOCKFISH_PATH' in os.environ:
        path = os.environ['STOCKFISH_PATH']
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path

    # Priority 2: Common relative paths for local development
    common_paths = ['./stockfish/stockfish', './stockfish', './stockfish.exe']
    for path in common_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return os.path.abspath(path)

    # Priority 3: System PATH (for globally installed Stockfish)
    from shutil import which
    if (path := which('stockfish')):
        return path
    
    return None

def main():
    """Parses command-line arguments and runs the chess analysis pipeline."""
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="Analyzes chess games from a PGN file using the Stockfish engine.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("input_pgn", help="Path to the input PGN file.")
    parser.add_argument(
        "-o", "--output-pgn", required=True,
        help="Path to the output PGN file where annotated games will be saved."
    )
    parser.add_argument(
        "-s", "--stockfish",
        default=find_stockfish_executable(),
        help="Path to the Stockfish executable. Tries to find it automatically if not provided."
    )
    parser.add_argument(
        "-p", "--player", dest="target_player_name", default=None,
        help="Target player name (case-insensitive) to generate a detailed summary report for."
    )
    parser.add_argument(
        "-r", "--report", dest="report_path", default=None,
        help=f"Path for the CSV summary report. Defaults to '{settings.DEFAULT_CUSTOM_REPORT_FILENAME}'."
    )
    parser.add_argument(
        "-d", "--depth", type=int, default=settings.DEFAULT_ANALYSIS_DEPTH,
        help="Stockfish analysis depth."
    )
    parser.add_argument(
        "--multipv", type=int, default=settings.DEFAULT_MULTI_PV,
        help="Number of lines (principal variations) for Stockfish to analyze."
    )
    parser.add_argument(
        "--threads", type=int,
        default=min(settings.DEFAULT_STOCKFISH_THREADS, (os.cpu_count() or 1)),
        help="Number of CPU threads for Stockfish to use."
    )
    parser.add_argument(
        "--hash", type=int, default=settings.DEFAULT_STOCKFISH_HASH_MB,
        help="Hash memory (in MB) for Stockfish."
    )
    parser.add_argument(
        "--pgn-columns", type=int, default=settings.PGN_DEFAULT_COLUMNS,
        help="Column width for wrapping move text in the output PGN. 0 for no wrapping."
    )
    parser.add_argument(
        "--log-level", default=settings.DEFAULT_LOG_LEVEL,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help="Set the logging level for console and file output."
    )
    parser.add_argument(
        "--log-file", default=settings.DEFAULT_LOG_FILENAME,
        help="Path to the log file."
    )
    parser.add_argument(
        "--no-console-log", action="store_true", help="Disable logging to the console."
    )

    args = parser.parse_args()
    
    # --- Initial Setup ---
    setup_logging(
        log_level_str=args.log_level,
        log_file=args.log_file,
        log_to_console=not args.no_console_log
    )
    
    if not args.stockfish:
        logging.critical("Stockfish executable not found. Please specify the path with the -s/--stockfish argument or set the STOCKFISH_PATH environment variable.")
        sys.exit(1)
        
    logging.info(f"{settings.APP_NAME} starting up...")
    
    # --- Pipeline Initialization and Execution ---
    try:
        pipeline_kwargs = {
            'analysis_depth': args.depth,
            'multipv_count': args.multipv,
            'stockfish_threads': args.threads,
            'stockfish_hash_mb': args.hash,
            'pgn_write_columns': args.pgn_columns
        }
        
        pipeline = AnalysisPipeline(stockfish_path=args.stockfish, **pipeline_kwargs)
        
        pipeline.run(
            input_pgn_path=args.input_pgn,
            output_pgn_path=args.output_pgn,
            target_player=args.target_player_name,
            report_path=args.report_path
        )
        
    except Exception as e:
        logging.critical(f"A fatal, unhandled exception occurred at the top level: {e}", exc_info=True)
        sys.exit(1)
    
    logging.info(f"{settings.APP_NAME} has finished successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()