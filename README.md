# ChessAnalyzer

A professional-grade Python application for analyzing chess games from PGN files using the Stockfish engine.

This tool provides deep, move-by-move analysis, including Lichess-style accuracy percentages, CPL (Centipawn Loss) evaluations, and "Brilliant" (✨) / "Great" (!) move detection. The results are exported as an annotated PGN and a summary CSV report.

The project is architected with a modular, decoupled pipeline, making it maintainable, testable, and extensible.

## Key Features

-   **Deep Engine Analysis:** Leverages the power of the Stockfish chess engine.
-   **Intelligent Caching:** Caches FEN analysis in an SQLite database to avoid re-analyzing positions, dramatically speeding up subsequent runs.
-   **Advanced Move Classification:** Identifies Blunders, Mistakes, Inaccuracies, and detects special "Brilliant" and "Great" moves.
-   **Rich PGN Annotation:** Injects detailed comments into the PGN, including evaluations, best lines, and move classifications.
-   **CSV Reporting:** Generates a detailed summary report for a target player, including Lichess-style accuracy percentages and move statistics.
-   **Robust & Modular Design:** Built with a clean, service-oriented architecture for long-term maintainability.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd chess_analyzer_project
    ```

2.  **Set up a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Get Stockfish:** Download the Stockfish executable for your operating system from the [official website](https://stockfishchess.org/download/). Place it in the project directory or ensure it's in your system's PATH.

## Usage

The application is run from the command line. The two most important arguments are the input PGN and the path for the annotated output PGN.

**Basic Example:**
```bash
python3 main.py path/to/my_games.pgn -o path/to/annotated_games.pgn
```

**Advanced Example (analyzing for a specific player):**
```bash
python3 main.py lichess_games.pgn \
    --output-pgn annotated/lichess_analyzed.pgn \
    --stockfish /path/to/your/stockfish_executable \
    --player "MyLichessUsername" \
    --report reports/my_summary.csv \
    --depth 20
```