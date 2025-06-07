# chess_analyzer_project/chess_analyzer/reporting/report_generator.py
"""
Generates summary reports from chess game analysis data.

This module provides the `ReportGenerator` class, which can produce
CSV reports summarizing key metrics for analyzed games, including
Lichess-style accuracy.
"""
import csv
import logging
import math
import os
from typing import List, Dict, Any

from chess_analyzer.config import settings
from chess_analyzer.types import GameSummary
# Import exceptions from the central location
from chess_analyzer.exceptions import ReportGenerationError, CSVReportError

logger = logging.getLogger(settings.APP_NAME + ".ReportGenerator")


class ReportGenerator:
    """Generates reports from chess analysis data."""
    
    _CSV_HEADERS: List[str] = [
        "GameID", "AnalyzedPlayer", "PlayerColor", "AccuracyPercent",
        "AverageCPL", "TotalMoves",
        "Brilliant", "Great", "Best", "Good", "OK", "Dubious",
        "Inaccuracy", "Mistake", "Blunder",
        "EngineTop1MatchPercent", "EngineTopNMatchPercent",
        "Event", "Site", "Date", "Round", "White", "Black", "Result",
        "WhiteACPL", "BlackACPL"
    ]

    def __init__(self):
        """Initializes the ReportGenerator."""
        logger.debug("ReportGenerator initialized.")

    def _calculate_accuracy(self, average_cpl: float) -> float:
        """
        Calculates Lichess-style accuracy from Average Centipawn Loss (ACPL).
        The result is capped between 0.0 and 100.0.
        """
        if average_cpl < 0:
            logger.warning(f"Received negative average_cpl ({average_cpl:.2f}). Clamping to 0.")
            average_cpl = 0.0
        
        try:
            accuracy = (
                settings.ACCURACY_CONSTANT_A * math.exp(settings.ACCURACY_CONSTANT_B * average_cpl) +
                settings.ACCURACY_CONSTANT_C
            )
        except OverflowError:
            accuracy = 0.0
        
        return max(0.0, min(100.0, accuracy))

    def generate_csv_report(self, game_summaries: List[GameSummary], output_report_path: str) -> None:
        """Generates a CSV summary report from a list of structured GameSummary objects."""
        if not game_summaries:
            logger.info("No game summary data provided; CSV report will not be generated.")
            return

        logger.info(f"Generating CSV summary report for {len(game_summaries)} games at: '{output_report_path}'")

        rows_to_write: List[Dict[str, Any]] = []
        for summary in game_summaries:
            total_moves = len(summary.player_cpls)
            if total_moves == 0:
                continue

            average_cpl = sum(summary.player_cpls) / total_moves
            accuracy_percent = self._calculate_accuracy(average_cpl)

            top1_match_percent = (summary.engine_top1_match_count / total_moves) * 100.0
            topN_match_percent = (summary.engine_topN_match_count / total_moves) * 100.0
            
            counts = summary.move_classification_counts
            
            row_data = {
                "GameID": summary.game_id,
                "AnalyzedPlayer": summary.analyzed_player_name,
                "PlayerColor": summary.player_color_str,
                "AccuracyPercent": f"{accuracy_percent:.1f}",
                "AverageCPL": f"{average_cpl:.1f}",
                "TotalMoves": total_moves,
                "Brilliant": counts.get("Brilliant ✨", 0),
                "Great": counts.get("Great Move !", 0),
                "Best": counts.get("Best", 0),
                "Good": counts.get("Good", 0),
                "OK": counts.get("OK", 0),
                "Dubious": counts.get("Dubious", 0),
                "Inaccuracy": counts.get("Inaccuracy", 0),
                "Mistake": counts.get("Mistake", 0),
                "Blunder": counts.get("Blunder", 0),
                "EngineTop1MatchPercent": f"{top1_match_percent:.1f}",
                "EngineTopNMatchPercent": f"{topN_match_percent:.1f}",
                **summary.pgn_headers,
            }
            rows_to_write.append(row_data)

        if not rows_to_write:
            logger.info("No valid game summaries to include in the CSV report.")
            return

        try:
            if (output_dir := os.path.dirname(output_report_path)):
                os.makedirs(output_dir, exist_ok=True)

            with open(output_report_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self._CSV_HEADERS, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(rows_to_write)
            logger.info(f"CSV summary report generated successfully: '{output_report_path}'")
        except IOError as e:
            raise CSVReportError(f"Failed to write CSV report to '{output_report_path}'") from e