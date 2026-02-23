"""Tests for the fast PGN importer and DB queries."""
import os
import tempfile
import pytest

from duchess.models import MasterGame
from duchess.pgn_importer import parse_and_import


SAMPLE_PGN = """
[Event "FIDE World Cup 2023"]
[Site "Baku AZE"]
[Date "2023.08.24"]
[Round "8.3"]
[White "Carlsen,M"]
[Black "Praggnanandhaa,R"]
[Result "1/2-1/2"]
[WhiteElo "2835"]
[BlackElo "2707"]
[EventDate "2023.07.30"]
[ECO "C47"]

1. e4 e5 2. Nf3 Nc6 3. Nc3 Nf6 4. a3 Bc5 5. Nxe5 O-O 
6. Nxc6 dxc6 7. h3 Re8 8. d3 Bd4 1/2-1/2

[Event "Superbet Classic 2023"]
[Site "Bucharest ROU"]
[Date "2023.05.06"]
[Round "1.1"]
[White "Caruana,F"]
[Black "Deac,Bogdan-Daniel"]
[Result "1-0"]
[WhiteElo "2764"]
[BlackElo "2700"]
[EventDate "2023.05.06"]
[ECO "D43"]

1. d4 d5 2. c4 c6 3. Nf3 Nf6 4. Nc3 e6 5. Bg5 h6 
6. Bh4 dxc4 7. e4 g5 8. Bg3 b5 1-0
"""

def test_pgn_import(db_session):
    """Verify that parse_and_import correctly extracts headers and move text."""
    # Write sample PGN to a temp file
    fd, path = tempfile.mkstemp(suffix=".pgn")
    with os.fdopen(fd, "w") as f:
        f.write(SAMPLE_PGN)

    try:
        # Import to DB
        parse_and_import(path, db=db_session)

        # Verify DB contents
        games = db_session.query(MasterGame).all()
        assert len(games) == 2

        g1 = games[0]
        assert g1.white == "Carlsen,M"
        assert g1.black == "Praggnanandhaa,R"
        assert g1.result == "1/2-1/2"
        assert g1.white_elo == 2835
        assert g1.eco == "C47"
        assert "1. e4 e5 2. Nf3" in g1.move_text

        g2 = games[1]
        assert g2.white == "Caruana,F"
        assert g2.result == "1-0"
        assert g2.eco == "D43"
        assert "1. d4 d5 2. c4 c6" in g2.move_text

    finally:
        if os.path.exists(path):
            os.remove(path)
