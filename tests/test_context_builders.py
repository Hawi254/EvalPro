# tests/test_context_builders.py
"""
Unit tests for the functions in context_builders.py.
"""
import pytest
import chess

# Import the functions and types we are testing
from chess_analyzer.context_builders import get_score_from_line, build_move_analysis_context, build_game_summary
from chess_analyzer.types import ClassificationResult, GameSummary
from chess_analyzer.config import settings

# --- Tests for get_score_from_line ---

@pytest.mark.parametrize("line, perspective, expected_score, expected_is_mate, expected_mate_in", [
    # Test case 1: White's perspective, centipawn score
    ({"Centipawn": 125, "Move": "e2e4"}, chess.WHITE, 125.0, False, None),
    # Test case 2: Black's perspective, centipawn score
    ({"Centipawn": 125, "Move": "e2e4"}, chess.BLACK, -125.0, False, None),
    # Test case 3: White's perspective, White is mating
    ({"Mate": 3, "Move": "Qh7#"}, chess.WHITE, 29997.0, True, 3),
    # Test case 4: Black's perspective, White is mating
    ({"Mate": 3, "Move": "Qh7#"}, chess.BLACK, -29997.0, True, -3),
    # Test case 5: White's perspective, Black is mating
    ({"Mate": -2, "Move": "qf2#"}, chess.WHITE, -29998.0, True, -2),
    # Test case 6: Black's perspective, Black is mating
    ({"Mate": -2, "Move": "qf2#"}, chess.BLACK, 29998.0, True, 2),
    # Test case 7: Null case (no score)
    ({}, chess.WHITE, None, False, None),
    # Test case 8: Invalid score data
    ({"Centipawn": "invalid"}, chess.WHITE, None, False, None),
    # Test case 9: Mate 0 should be treated as a draw
    ({"Mate": 0}, chess.WHITE, 0.0, False, None),
])
def test_get_score_from_line(line, perspective, expected_score, expected_is_mate, expected_mate_in):
    """
    Tests that get_score_from_line correctly parses various engine lines.
    """
    score, is_mate, mate_in = get_score_from_line(line, perspective)

    if expected_score is not None:
        assert score == pytest.approx(expected_score)
    else:
        assert score is None
        
    assert is_mate == expected_is_mate
    assert mate_in == expected_mate_in

# --- Tests for build_move_analysis_context ---

def test_build_move_analysis_context(sample_move_data_e4):
    """
    Tests that build_move_analysis_context correctly assembles the context object.
    """
    # Arrange: Create a sample analysis dictionary
    # This represents the engine's output for the positions before and after 1. e4
    analyses = {
        # FEN before 1. e4 (starting position)
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1": [
            {"Move": "e2e4", "Centipawn": 50}, # Best move
            {"Move": "g1f3", "Centipawn": 45}, # Second best
        ],
        # FEN after 1. e4
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1": [
            {"Move": "c7c5", "Centipawn": -50}, # Best response for Black (so -50 for White)
        ],
    }
    
    # Act: Call the function we are testing
    context = build_move_analysis_context(sample_move_data_e4, analyses, multipv_setting=2)

    # Assert: Check that the context object is built correctly
    # Note: The player is White, so all evals should be from White's POV.
    assert context.player_color == chess.WHITE
    
    # Evals for the position BEFORE the move (all from White's POV)
    assert context.eval_best_move == pytest.approx(50.0)
    assert context.is_mate_best_move is False
    assert context.eval_second_best_move == pytest.approx(45.0)
    assert context.is_mate_second_best_move is False
    assert context.eval_before_move == pytest.approx(50.0) # Should be same as best move

    # Eval for the player's actual move (1. e4)
    # The eval *after* 1. e4 is -50 from Black's best response perspective.
    # The get_score_from_line function converts this to +50 from White's perspective.
    assert context.eval_player_move == pytest.approx(50.0)
    assert context.is_mate_player_move is False
    
    # Check supporting data
    assert context.player_move_uci == "e2e4"
    assert context.brilliant_criteria == settings.BRILLIANT_CRITERIA

# --- Tests for build_game_summary ---

def test_build_game_summary_for_white(sample_game):
    """
    Tests that a GameSummary is correctly built for the targeted White player.
    """
    # Arrange: Create sample classification results for the 3 moves White makes
    results = [
        ClassificationResult("Best", 0, 0), # 1. e4
        ClassificationResult("N/A", 0, 0), # 1... e5 (Black's move, ignored)
        ClassificationResult("Good", 20, 18), # 2. Nf3
        ClassificationResult("N/A", 0, 0), # 2... Nc6 (Black's move, ignored)
        ClassificationResult("Mistake", 150, 145), # 3. Bb5
        ClassificationResult("N/A", 0, 0), # 3... a6 (Black's move, ignored)
    ]
    
    # Act
    summary = build_game_summary(sample_game, "game1", "Player A", results)

    # Assert
    assert isinstance(summary, GameSummary)
    assert summary.analyzed_player_name == "Player A"
    assert summary.player_color_str == "White"
    assert summary.player_cpls == [0, 20, 150]
    assert summary.move_classification_counts["Best"] == 1
    assert summary.move_classification_counts["Good"] == 1
    assert summary.move_classification_counts["Mistake"] == 1

def test_build_game_summary_no_target_player(sample_game):
    """
    Tests that build_game_summary returns None when no target player is specified.
    """
    summary = build_game_summary(sample_game, "game1", None, [])
    assert summary is None

def test_build_game_summary_player_not_in_game(sample_game):
    """
    Tests that build_game_summary returns None when the target player is not in the game.
    """
    summary = build_game_summary(sample_game, "game1", "Player C", [])
    assert summary is None