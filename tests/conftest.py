# tests/conftest.py
"""
Shared fixtures for the ChessAnalyzer test suite.
"""
import pytest
import chess
import chess.pgn
from io import StringIO

@pytest.fixture
def sample_game() -> chess.pgn.Game:
    """
    Provides a simple, standard chess game object for testing.
    The game is: 1. e4 e5 2. Nf3 Nc6 3. Bb5 a6
    """
    # Programmatically creating the game is more reliable for tests.
    game = chess.pgn.Game()
    game.headers["Event"] = "Test Game"
    game.headers["White"] = "Player A"
    game.headers["Black"] = "Player B"
    
    # Add moves
    node = game.add_variation(chess.Move.from_uci("e2e4"))
    node = node.add_variation(chess.Move.from_uci("e7e5"))
    node = node.add_variation(chess.Move.from_uci("g1f3"))
    node = node.add_variation(chess.Move.from_uci("b8c6"))
    node = node.add_variation(chess.Move.from_uci("f1b5"))
    node = node.add_variation(chess.Move.from_uci("a7a6"))
    
    return game

@pytest.fixture
def sample_move_data_e4(sample_game: chess.pgn.Game) -> "MoveData":
    """
    Provides a MoveData object for the first move of the sample_game (1. e4).
    """
    # This requires a bit of setup to get the specific node
    from chess_analyzer.types import MoveData
    
    node = sample_game.variations[0] # This is the node for 1. e4
    board_before = sample_game.board() # The starting position
    board_after = board_before.copy()
    board_after.push(node.move)
    
    return MoveData(
        pgn_node=node,
        actual_move_obj=node.move,
        board_before_move=board_before,
        fen_before_move="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        fen_after_move="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    )