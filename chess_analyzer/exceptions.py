# chess_analyzer_project/chess_analyzer/exceptions.py
"""
Defines custom exceptions for the Chess Analyzer application.

Centralizing exceptions here avoids circular dependencies when different
modules need to catch exceptions defined by other components.
"""

# --- General ---
class ChessAnalyzerError(Exception):
    """Base class for all application-specific errors."""
    pass

# --- Stockfish Controller Errors ---
class StockfishError(ChessAnalyzerError):
    """Base class for Stockfish controller errors."""
    pass

class StockfishInitializationError(StockfishError):
    """Error during Stockfish engine initialization."""
    pass

class StockfishAnalysisError(StockfishError):
    """Error during FEN analysis by Stockfish."""
    pass

# --- Cache Errors ---
class CacheError(ChessAnalyzerError):
    """Base class for cache-related errors."""
    pass

class CacheConnectionError(CacheError):
    """Error connecting to or initializing the cache database."""
    pass

class CacheReadError(CacheError):
    """Error reading from the cache."""
    pass

class CacheWriteError(CacheError):
    """Error writing to the cache."""
    pass

# --- PGN Handler Errors ---
class PGNError(ChessAnalyzerError):
    """Base class for PGN handling errors."""
    pass

class PGNImportError(PGNError):
    """Error encountered while reading or parsing a PGN file."""
    pass

class PGNExportError(PGNError):
    """Error encountered while writing or exporting a PGN file."""
    pass

# --- Reporting Errors ---
class ReportGenerationError(ChessAnalyzerError):
    """Base class for errors encountered during report generation."""
    pass

class CSVReportError(ReportGenerationError):
    """Specific error for CSV report generation issues."""
    pass