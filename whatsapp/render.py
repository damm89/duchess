# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""Board rendering for WhatsApp — PNG image and ASCII text."""
import chess
import chess.svg

from duchess.board import DuchessBoard


def fen_to_png(fen: str) -> bytes:
    """Render a FEN position as a PNG image (400x400)."""
    try:
        import cairosvg
    except ImportError:
        raise RuntimeError("cairosvg is required for image rendering. Run: pip install cairosvg")
    board = chess.Board(fen)
    svg_str = chess.svg.board(board, size=400)
    return cairosvg.svg2png(bytestring=svg_str.encode())


def fen_to_ascii(fen: str) -> str:
    """Render a FEN position as a Unicode ASCII board."""
    return DuchessBoard(fen).pretty()
