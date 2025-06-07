# chess_analyzer_project/chess_analyzer/context_builders.py
"""
Data transformation functions for the analysis pipeline.

This module contains pure, testable functions responsible for building the
structured `dataclass` context objects used by various components. It
isolates the "messy" work of converting raw analysis data into a clean,
usable format.
"""
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

import chess
import chess.pgn

from chess_analyzer.config import settings
from chess_analyzer.types import (
    AnnotationContext,
    ClassificationResult,
    EngineLineInfo,
    GameSummary,
    MoveAnalysisContext,
    MoveData,
)

# --- Score Transformation ---

def get_score_from_line(
    line: Optional[Dict[str, Any]], perspective: chess.Color
) -> Tuple[Optional[float], bool, Optional[int]]:
    if not line:
        return None, False, None

    is_mate = False
    score_wpov = None
    mate_moves_wpov = None

    mate_val = line.get("Mate")
    cp_val = line.get("Centipawn")

    if mate_val is not None:
        try:
            mate_moves_wpov = int(mate_val)
            is_mate = True
            if mate_moves_wpov == 0:
                is_mate = False
                score_wpov = 0.0
            elif mate_moves_wpov > 0:
                score_wpov = settings.MATE_SCORE_EQUIVALENT_CP - abs(mate_moves_wpov)
            else:
                score_wpov = -settings.MATE_SCORE_EQUIVALENT_CP + abs(mate_moves_wpov)
        except (TypeError, ValueError):
            mate_moves_wpov = None
            is_mate = False
    elif cp_val is not None:
        try:
            score_wpov = float(cp_val)
        except (TypeError, ValueError):
            score_wpov = None

    if score_wpov is None:
        return None, False, None

    if perspective == chess.WHITE:
        return score_wpov, is_mate, mate_moves_wpov
    else:
        mate_moves_for_black = -mate_moves_wpov if is_mate and mate_moves_wpov is not None else None
        return -score_wpov, is_mate, mate_moves_for_black

# --- Context Builders ---

def build_move_analysis_context(
    move_data: MoveData,
    analyses: Dict[str, List[Dict[str, Any]]],
    multipv_setting: int,
) -> MoveAnalysisContext:
    """Constructs the context object required by the MoveClassifier."""
    lines_before = analyses.get(move_data.fen_before_move)
    lines_after = analyses.get(move_data.fen_after_move)
    player = move_data.board_before_move.turn

    # Get evals from the moving player's perspective
    best_line = lines_before[0] if lines_before else None
    second_best_line = lines_before[1] if lines_before and len(lines_before) > 1 else None
    player_move_line = lines_after[0] if lines_after else None

    eval_best, mate_best, _ = get_score_from_line(best_line, player)
    eval_second, mate_second, _ = get_score_from_line(second_best_line, player)
    eval_player, mate_player, _ = get_score_from_line(player_move_line, player)

    # The evaluation of the position before the move is the same as the engine's best move eval
    eval_before, mate_before = eval_best, mate_best

    return MoveAnalysisContext(
        eval_best_move=eval_best, is_mate_best_move=mate_best,
        eval_second_best_move=eval_second, is_mate_second_best_move=mate_second,
        eval_player_move=eval_player, is_mate_player_move=mate_player,
        eval_before_move=eval_before, is_mate_before_move=mate_before,
        engine_top_lines=lines_before or [],
        player_move_uci=move_data.actual_move_obj.uci(),
        board_before_move=move_data.board_before_move,
        board_after_move=move_data.pgn_node.board(),
        player_color=player,
        engine_multipv=multipv_setting,
        brilliant_criteria=settings.BRILLIANT_CRITERIA,
        great_criteria=settings.GREAT_CRITERIA,
    )

def build_annotation_context(
    move_data: MoveData,
    result: ClassificationResult,
    analyses: Dict[str, List[Dict[str, Any]]],
    analysis_depth: int,
    multipv_setting: int,
    prepare_comment_func: Callable[[str], Tuple[str, str]],
) -> AnnotationContext:
    """Constructs the context object required by the Annotator."""
    lines_before = analyses.get(move_data.fen_before_move, [])
    lines_after = analyses.get(move_data.fen_after_move, [])

    # Prepare formatted engine lines for the [Analyse] tag
    engine_lines_info: List[EngineLineInfo] = []
    if lines_before:
        temp_board = move_data.board_before_move.copy(stack=False)
        for i, line in enumerate(lines_before):
            score_wpov, _, mate_val_wpov = get_score_from_line(line, chess.WHITE)
            eval_str = f"#{mate_val_wpov}" if mate_val_wpov else f"{score_wpov/100.0:.2f}"
            
            pv_san_list: List[str] = []
            if "PV" in line:
                pv_board = temp_board.copy(stack=False)
                for move_uci in line.get("PV", [])[:settings.PV_MAX_MOVES_IN_COMMENT]:
                    try:
                        move = chess.Move.from_uci(move_uci)
                        pv_san_list.append(pv_board.san(move))
                        pv_board.push(move)
                    except ValueError:
                        pv_san_list.append(f"{move_uci}?")
                        break
            
            engine_lines_info.append(
                EngineLineInfo(
                    move_san=temp_board.san(chess.Move.from_uci(line["Move"])),
                    eval_str=eval_str,
                    is_best_line=(i == 0),
                    pv_san_list=pv_san_list,
                )
            )

    # Prepare eval string for the [%eval] tag (from White's POV)
    eval_wpov, is_mate_wpov, mate_val_wpov = get_score_from_line(lines_after[0] if lines_after else None, chess.WHITE)
    eval_str_for_tag = ""
    if eval_wpov is not None:
        if is_mate_wpov and mate_val_wpov is not None:
            eval_str_for_tag = f"[%eval #{mate_val_wpov},{analysis_depth}]"
        else:
            eval_str_for_tag = f"[%eval {eval_wpov/100.0:.2f},{analysis_depth}]"

    # Preserve user comments and clock tags from the original PGN
    user_comment, clk_part = prepare_comment_func(move_data.pgn_node.comment)

    return AnnotationContext(
        classification=result,
        eval_after_move_wpov_str=eval_str_for_tag,
        clk_comment_part=clk_part,
        user_comment_part=user_comment,
        engine_lines=engine_lines_info,
        analysis_depth=analysis_depth,
        multipv_setting=multipv_setting,
    )

def build_game_summary(
    game: chess.pgn.Game,
    game_id: str,
    target_player: Optional[str],
    move_results: List[ClassificationResult],
) -> Optional[GameSummary]:
    """Builds a GameSummary object if the game is relevant for the target player."""
    if not target_player:
        return None

    white_player = game.headers.get("White", "")
    black_player = game.headers.get("Black", "")

    is_white_targeted = target_player.lower() == white_player.lower()
    is_black_targeted = target_player.lower() == black_player.lower()

    if not (is_white_targeted or is_black_targeted):
        return None

    # Filter results for the targeted player based on move index (even for White, odd for Black)
    player_results = [r for i, r in enumerate(move_results) if (is_white_targeted and i % 2 == 0) or (is_black_targeted and i % 2 != 0)]
    if not player_results:
        return None

    # Simplify classification text for counting (e.g., "Good (CPL: 30)" -> "Good")
    classification_names = [r.classification_text.split("(")[0].strip() for r in player_results]

    return GameSummary(
        game_id=game_id,
        analyzed_player_name=white_player if is_white_targeted else black_player,
        player_color_str="White" if is_white_targeted else "Black",
        player_cpls=[r.cpl for r in player_results],
        move_classification_counts=Counter(classification_names),
        engine_top1_match_count=sum(1 for r in player_results if r.is_engine_top_choice),
        engine_topN_match_count=sum(1 for r in player_results if r.is_engine_top_n_choice),
        pgn_headers=dict(game.headers),
    )