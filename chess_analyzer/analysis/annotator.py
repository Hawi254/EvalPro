# chess_analyzer_project/chess_analyzer/analysis/annotator.py
"""
Handles the generation of PGN comments based on pre-processed analysis data.

This module provides the Annotator class, which is a "dumb" formatting engine.
It takes a fully prepared AnnotationContext and assembles the final PGN comment
string, abstracting away the details of comment structure and formatting.
"""
import logging
import re
from typing import Tuple

from chess_analyzer.config import settings
from chess_analyzer.types import AnnotationContext

logger = logging.getLogger(settings.APP_NAME + ".Annotator")


class Annotator:
    """
    Creates formatted PGN comments from a pre-processed analysis context.
    This class is a "dumb" formatter and does not perform any calculations.
    """

    def __init__(self, engine_name: str = "Engine"):
        """
        Initializes the Annotator.

        Args:
            engine_name: The short name of the engine for use in comments (e.g., "SF17").
        """
        self.engine_name = engine_name
        self._our_analysis_tags_patterns = [
            re.compile(r"\[%eval\s+[^\]]+\]"),
            re.compile(r"\[Analyse\s+[^\]]+\]"),
            re.compile(r"\{(Best|Good|OK|Dubious|Inaccuracy|Mistake|Blunder|Brilliant|Great)[^}]*\}", re.IGNORECASE),
        ]
        logger.debug(f"Annotator initialized for engine '{self.engine_name}'.")

    def _format_analyse_tag(self, context: AnnotationContext) -> str:
        """Formats the [Analyse ...] tag containing engine lines and PVs."""
        if not context.engine_lines:
            return ""

        best_line = next((line for line in context.engine_lines if line.is_best_line), None)
        if not best_line:
            return ""

        # Format the primary line with its evaluation and Principal Variation (PV)
        best_line_comment = f"Best: {best_line.move_san} ({best_line.eval_str})"
        if best_line.pv_san_list:
            pv_str = " ".join(best_line.pv_san_list)
            best_line_comment += f" PV: {pv_str}"

        # Format the summary of the top N moves if MultiPV > 1
        top_n_comment = ""
        if context.multipv_setting > 1 and len(context.engine_lines) > 1:
            top_n_parts = [f"{i+1}.{line.move_san}({line.eval_str})" for i, line in enumerate(context.engine_lines)]
            top_n_comment = f"; Top: {' '.join(top_n_parts)}"

        # Assemble the full tag
        header = f"[Analyse {self.engine_name}@{context.analysis_depth}d{context.multipv_setting}pv: "
        return f"{header}{best_line_comment}{top_n_comment}]"

    def prepare_context_from_existing_comment(self, existing_comment: str) -> Tuple[str, str]:
        """
        Parses an existing comment to extract the user's portion and the clock tag.
        This is injected into the context builder to avoid circular dependencies.

        Returns:
            A tuple of (user_comment_part, clk_comment_part).
        """
        # 1. Preserve the clock tag if it exists
        clk_part_regex = re.compile(r"(\[%clk\s+[\d:\.]+\])")
        clk_match = clk_part_regex.search(existing_comment)
        clk_comment_part = clk_match.group(1) if clk_match else ""
        
        # 2. Clean our analysis tags from the original comment
        cleaned_comment = existing_comment
        if clk_comment_part:
            cleaned_comment = cleaned_comment.replace(clk_comment_part, "").strip()
            
        for pattern in self._our_analysis_tags_patterns:
            cleaned_comment = pattern.sub("", cleaned_comment).strip()
            
        # 3. Format the remaining text as the user comment, cleaning up braces
        user_comment_part = ""
        if cleaned_comment and cleaned_comment not in ["{}", ""]:
            if cleaned_comment.startswith('{') and cleaned_comment.endswith('}'):
                cleaned_comment = cleaned_comment[1:-1]
            if cleaned_comment:
                user_comment_part = f"{{{cleaned_comment}}}"

        return user_comment_part, clk_comment_part

    def generate_pgn_node_comment(self, context: AnnotationContext) -> str:
        """
        Generates a complete PGN comment string from a pre-filled context object.
        The desired order is: {Classification} [%eval] [%clk] [Analyse] {UserComment}
        """
        # 1. Format the classification part
        classification_part = ""
        if context.classification:
            classification_part = f"{{{context.classification.classification_text}}}"

        # 2. Format the [Analyse ...] tag using the helper
        analyse_part = self._format_analyse_tag(context)

        # 3. Assemble all parts in the correct order, filtering out empty strings
        final_parts = [
            classification_part,
            context.eval_after_move_wpov_str,
            context.clk_comment_part,
            analyse_part,
            context.user_comment_part,
        ]

        return " ".join(p for p in final_parts if p).strip()