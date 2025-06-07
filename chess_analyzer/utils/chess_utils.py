# chess_analyzer_project/chess_analyzer/utils/chess_utils.py
"""
Generic chess-related utility functions.

This module provides helper functions that operate on chess concepts,
boards, or pieces, and are not tied to a specific component like
PGN handling or engine interaction. These are pure functions, making
them easy to test and reason about.
"""
from typing import Final, Dict

import chess

# --- Piece Material Values ---
# Centralized for maintainability and clarity. Using floats for precision, which
# is critical for accurately calculating sacrifices for "Brilliant" move detection.
PIECE_VALUES: Final[Dict[chess.PieceType, float]] = {
    chess.PAWN: 1.0,
    chess.KNIGHT: 3.0,
    chess.BISHOP: 3.2,  # Valued slightly higher than a knight
    chess.ROOK: 5.0,
    chess.QUEEN: 9.0,
    chess.KING: 0.0,   # Kings do not have material value in this context
}


def get_material_value(board: chess.Board, color: chess.Color) -> float:
    """
    Calculates the total material value for a given color on the board.

    Uses the standard piece values defined in the `PIECE_VALUES` constant.

    Args:
        board: A `chess.Board` object representing the position.
        color: A `chess.Color` (chess.WHITE or chess.BLACK) for which to
               calculate material.

    Returns:
        The total material value in pawn units as a float.
    """
    material: float = 0.0
    for piece_type, value in PIECE_VALUES.items():
        # board.pieces() returns a PieceMap (a set-like view of squares)
        count = len(board.pieces(piece_type, color))
        material += count * value
    return material


def get_material_diff(board: chess.Board, perspective_color: chess.Color) -> float:
    """
    Calculates the material difference from the perspective of a given color.

    This is an efficient implementation that iterates through the pieces on the
    board only once. A positive value means the `perspective_color` has more
    material; a negative value means it has less.

    Args:
        board: A `chess.Board` object representing the position.
        perspective_color: The `chess.Color` from whose perspective the
                           material difference is calculated.

    Returns:
        The material difference in pawn units as a float, rounded to 2 decimal places.
    """
    diff: float = 0.0
    # `board.piece_map()` is an efficient way to iterate over all pieces at once.
    # It returns a dictionary of {square_index: Piece}.
    for piece in board.piece_map().values():
        value = PIECE_VALUES.get(piece.piece_type, 0.0)
        if piece.color == perspective_color:
            diff += value
        else:
            diff -= value
    # Round to a reasonable precision to avoid floating point artifacts
    return round(diff, 2)