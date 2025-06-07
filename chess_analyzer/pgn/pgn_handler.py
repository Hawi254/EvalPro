# chess_analyzer_project/chess_analyzer/pgn/pgn_handler.py
"""
Handles all PGN (Portable Game Notation) related operations.

This includes reading and parsing PGN files, extracting game information
(like IDs and FENs), and writing annotated PGNs. It is designed to be
resilient to common errors in PGN files.
"""
import logging
import os
import re
import threading
from collections import OrderedDict
from typing import IO, Dict, Generator, List, Optional, Set, Tuple

import chess
import chess.pgn

from chess_analyzer.config import settings
from chess_analyzer.types import MoveData
# Import exceptions from the central location
from chess_analyzer.exceptions import PGNError, PGNImportError, PGNExportError

logger = logging.getLogger(settings.APP_NAME + ".PGNHandler")


class PGNHandler:
    """Provides functionalities to read, process, and write PGN files."""
    
    _GAME_ID_EXTRACTION_PATTERNS: Dict[str, str] = OrderedDict([
        ("SiteLichess", r"lichess\.org/([a-zA-Z0-9]{8,12})"),
        ("SiteChessCom", r"chess\.com/game/live/([0-9]+)"),
        ("SiteChessComAnalysis", r"chess\.com/analysis/game/live/([0-9]+)"),
        ("LichessURL", r"lichess\.org/([a-zA-Z0-9]{8,12})"),
    ])

    def __init__(self, pgn_output_columns: int = settings.PGN_DEFAULT_COLUMNS):
        """
        Initializes the PGNHandler.

        Args:
            pgn_output_columns: The column width for wrapping move text in
                                output PGN files. 0 means no wrapping.
        """
        self.pgn_output_columns: int = pgn_output_columns
        self._is_first_export_to_handle: Dict[int, bool] = {}

    def extract_game_id(self, headers: chess.pgn.Headers) -> Optional[str]:
        """
        Extracts a unique game identifier from PGN headers.

        Prioritizes Lichess and Chess.com URLs, then falls back to the 'GameId' tag.
        """
        for tag_name in ["Site", "LichessURL"]:
            header_value = headers.get(tag_name)
            if header_value:
                for pattern in self._GAME_ID_EXTRACTION_PATTERNS.values():
                    match = re.search(pattern, header_value)
                    if match:
                        return match.group(1)
        
        game_id_tag = headers.get("GameId")
        return game_id_tag if game_id_tag and game_id_tag != "?" else None

    def get_processed_game_ids(self, output_pgn_path: str) -> Set[str]:
        """
        Efficiently scans an existing output PGN to find IDs of already processed games.
        """
        processed_ids: Set[str] = set()
        if not os.path.exists(output_pgn_path):
            return processed_ids

        logger.info(f"Scanning '{output_pgn_path}' for existing game IDs...")
        try:
            for headers in self._stream_games_headers_only(output_pgn_path):
                game_id = self.extract_game_id(headers)
                if game_id:
                    processed_ids.add(game_id)
            logger.info(f"Found {len(processed_ids)} processed game IDs.")
        except PGNImportError as e:
            logger.warning(f"Could not fully parse existing PGN for IDs due to error: {e}")
        return processed_ids

    def _stream_games_headers_only(self, pgn_path: str) -> Generator[chess.pgn.Headers, None, None]:
        """A lightweight generator that yields only the headers of games from a PGN file."""
        try:
            with open(pgn_path, 'r', encoding='utf-8', errors='replace') as pgn_file:
                while headers := chess.pgn.read_headers(pgn_file):
                    yield headers
        except (IOError, OSError) as e:
            raise PGNImportError(f"Cannot read headers from PGN file '{pgn_path}'") from e

    def stream_games(self, input_pgn_path: str, shutdown_event: Optional[threading.Event] = None) -> Generator[chess.pgn.Game, None, None]:
        """Streams full game objects one by one from an input PGN file."""
        if not os.path.exists(input_pgn_path):
            raise PGNImportError(f"Input PGN file not found: {input_pgn_path}")

        game_count = 0
        try:
            with open(input_pgn_path, 'r', encoding='utf-8', errors='replace') as pgn_file:
                while not (shutdown_event and shutdown_event.is_set()):
                    try:
                        game = chess.pgn.read_game(pgn_file)
                        if game is None:
                            break 
                        game_count += 1
                        yield game
                    except (ValueError, RuntimeError) as e:
                        logger.warning(f"Skipping malformed game at offset ~{pgn_file.tell()}: {e}")
                        continue
        except IOError as e:
            raise PGNImportError(f"IOError reading PGN file '{input_pgn_path}'") from e
        
        if not (shutdown_event and shutdown_event.is_set()):
            logger.info(f"Finished streaming {game_count} games from '{input_pgn_path}'.")

    def collect_move_data_and_fens(self, game: chess.pgn.Game) -> Tuple[List[MoveData], OrderedDict[str, None]]:
        """Iterates through a game, collecting move details and unique FENs."""
        all_move_details: List[MoveData] = []
        game_unique_fens: OrderedDict[str, None] = OrderedDict()
        
        board = game.board()
        game_unique_fens[board.fen()] = None

        for node in game.mainline():
            move = node.move
            if move is None:
                continue

            fen_before = board.fen()
            board_before_copy = board.copy(stack=False)
            
            board.push(move)
            fen_after = board.fen()

            all_move_details.append(MoveData(
                pgn_node=node,
                actual_move_obj=move,
                board_before_move=board_before_copy,
                fen_before_move=fen_before,
                fen_after_move=fen_after,
            ))
            game_unique_fens[fen_before] = None
            game_unique_fens[fen_after] = None
            
        return all_move_details, game_unique_fens

    def export_annotated_game(self, game: chess.pgn.Game, outfile_handle: IO[str]) -> None:
        """Exports a game to the provided file stream with simple, robust newline handling."""
        handle_id = id(outfile_handle)
        if handle_id not in self._is_first_export_to_handle:
            self._is_first_export_to_handle[handle_id] = outfile_handle.tell() == 0

        try:
            exporter = chess.pgn.StringExporter(
                headers=True, variations=True, comments=True,
                columns=self.pgn_output_columns if self.pgn_output_columns > 0 else None
            )
            pgn_string = game.accept(exporter)

            if not self._is_first_export_to_handle[handle_id]:
                outfile_handle.write("\n\n")

            outfile_handle.write(pgn_string)
            outfile_handle.flush()
            
            self._is_first_export_to_handle[handle_id] = False

        except (IOError, OSError) as e:
            raise PGNExportError(f"IOError exporting game: {e}") from e
        except Exception as e:
            raise PGNExportError(f"Unexpected error exporting game: {e}") from e