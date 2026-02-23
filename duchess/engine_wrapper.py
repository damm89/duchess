# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""UCI engine subprocess wrapper — communicates with duchess_cli via stdin/stdout."""
import os
import sys
import subprocess
import threading
from pathlib import Path

from duchess.chess_types import Piece, Color, Move


def _parse_info_line(line):
    """Parse a UCI info line into a dict with depth, score_cp, score_mate, pv, nodes, nps, time."""
    tokens = line.split()
    info = {}
    i = 1  # skip "info"
    while i < len(tokens):
        tok = tokens[i]
        if tok == "depth" and i + 1 < len(tokens):
            info["depth"] = int(tokens[i + 1])
            i += 2
        elif tok == "score" and i + 2 < len(tokens):
            if tokens[i + 1] == "cp":
                info["score_cp"] = int(tokens[i + 2])
            elif tokens[i + 1] == "mate":
                info["score_mate"] = int(tokens[i + 2])
            i += 3
        elif tok == "nodes" and i + 1 < len(tokens):
            info["nodes"] = int(tokens[i + 1])
            i += 2
        elif tok == "nps" and i + 1 < len(tokens):
            info["nps"] = int(tokens[i + 1])
            i += 2
        elif tok == "time" and i + 1 < len(tokens):
            info["time"] = int(tokens[i + 1])
            i += 2
        elif tok == "pv":
            info["pv"] = tokens[i + 1:]
            break
        else:
            i += 1
    return info


def _engine_path():
    """Locate the duchess_cli binary."""
    exe_name = "duchess_cli.exe" if os.name == "nt" else "duchess_cli"
    
    # PyInstaller bundle
    base = getattr(sys, '_MEIPASS', None)
    if base:
        p = Path(base) / exe_name
        if p.exists():
            return str(p)

    # Development: engine/build/duchess_cli
    dev = Path(__file__).resolve().parent.parent / "engine" / "build" / exe_name
    if dev.exists():
        return str(dev)
        
    # Windows MSVC Release folder
    dev_release = Path(__file__).resolve().parent.parent / "engine" / "build" / "Release" / exe_name
    if dev_release.exists():
        return str(dev_release)

    raise FileNotFoundError(f"Cannot find {exe_name} binary")


class UCIEngine:
    """Manages a single long-running UCI engine subprocess."""

    def __init__(self, engine_path=None):
        path = engine_path or _engine_path()
        self._proc = subprocess.Popen(
            [path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._lock = threading.Lock()
        self.name = "Unknown"
        # Handshake — capture engine name from "id name ..." line
        self._send("uci")
        while True:
            line = self._read_line()
            if line.startswith("id name "):
                self.name = line[len("id name "):].strip()
            if line.startswith("uciok"):
                break
        self._send("isready")
        self._read_until("readyok")

        # Auto-load opening book for the default Duchess engine
        self._book_path = None
        self._book_name = None
        if engine_path is None:
            book_path = self._find_default_book()
            if book_path:
                self.set_book(book_path)

    @staticmethod
    def _find_default_book():
        """Locate the default gm2001 opening book file."""
        candidates = [
            Path(__file__).resolve().parent.parent / "data" / "gm2001.bin",
        ]
        base = getattr(sys, '_MEIPASS', None)
        if base:
            candidates.insert(0, Path(base) / "data" / "gm2001.bin")
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    @property
    def book_name(self):
        """Return the display name of the current opening book, or None."""
        return self._book_name

    def set_book(self, path):
        """Load an opening book from the given path."""
        with self._lock:
            self._send(f"setoption name BookFile value {path}")
            self._send("isready")
            self._read_until("readyok")
        self._book_path = path
        self._book_name = Path(path).stem

    def disable_book(self):
        """Disable the opening book."""
        with self._lock:
            self._send("setoption name OwnBook value false")
            self._send("isready")
            self._read_until("readyok")
        self._book_path = None
        self._book_name = None

    def reset_book(self):
        """Reset to the default gm2001 opening book."""
        path = self._find_default_book()
        if path:
            self.set_book(path)
        else:
            self.disable_book()

    def set_option(self, name, value):
        """Send a UCI setoption command."""
        with self._lock:
            self._send(f"setoption name {name} value {value}")
            self._send("isready")
            self._read_until("readyok")

    def _send(self, cmd):
        self._proc.stdin.write(cmd + "\n")
        self._proc.stdin.flush()

    def _read_line(self):
        line = self._proc.stdout.readline()
        if not line:
            raise RuntimeError("Engine process terminated unexpectedly")
        return line.rstrip("\n")

    def _read_until(self, token):
        """Read lines until one starts with the given token. Return that line."""
        while True:
            line = self._read_line()
            if line.startswith(token):
                return line

    def set_position_fen(self, fen, moves=None):
        """Send position command with a FEN string and optional move list."""
        with self._lock:
            cmd = f"position fen {fen}"
            if moves:
                cmd += " moves " + " ".join(moves)
            self._send(cmd)

    def set_position_startpos(self, moves=None):
        with self._lock:
            cmd = "position startpos"
            if moves:
                cmd += " moves " + " ".join(moves)
            self._send(cmd)

    def go_movetime(self, time_ms, info_cb=None):
        """Start search with a time limit. Returns best move UCI string.
        If info_cb is provided, it's called with a dict for each info line."""
        with self._lock:
            self._send(f"go movetime {time_ms}")
            return self._read_bestmove(info_cb)

    def go_depth(self, depth, info_cb=None):
        """Start search to a fixed depth. Returns best move UCI string."""
        with self._lock:
            self._send(f"go depth {depth}")
            return self._read_bestmove(info_cb)

    def _read_bestmove(self, info_cb=None):
        """Read lines until bestmove, calling info_cb for each info line."""
        while True:
            line = self._read_line()
            if line.startswith("bestmove"):
                return line.split()[1]
            if line.startswith("info") and info_cb:
                info_cb(_parse_info_line(line))

    def get_legal_moves(self):
        """Return list of legal move UCI strings."""
        with self._lock:
            self._send("legalmoves")
            line = self._read_line()
            # "legalmoves e2e4 d2d4 ..."
            parts = line.split()
            if len(parts) <= 1:
                return []
            return parts[1:]

    def evaluate(self):
        """Return evaluation dict: {'cp': int} or {'mate': int}."""
        with self._lock:
            self._send("eval")
            line = self._read_line()
            # "eval cp 15" or "eval mate 0"
            parts = line.split()
            if parts[1] == "mate":
                return {"mate": int(parts[2])}
            return {"cp": int(parts[2])}

    def get_gamestate(self):
        """Return 'playing', 'checkmate', or 'stalemate'."""
        with self._lock:
            self._send("gamestate")
            line = self._read_line()
            return line.split()[1]

    def get_fen(self):
        """Return current FEN string."""
        with self._lock:
            self._send("fen")
            line = self._read_line()
            # "fen rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            return line[len("fen "):].strip()

    def get_pieces(self):
        """Return list of 64 Piece enum values for squares 0-63."""
        with self._lock:
            self._send("pieces")
            line = self._read_line()
            parts = line.split()
            return [Piece(int(x)) for x in parts[1:]]

    def get_piece_at(self, sq):
        """Return Piece enum for a single square."""
        with self._lock:
            self._send(f"piece {sq}")
            line = self._read_line()
            return Piece(int(line.split()[2]))

    def get_side_to_move(self):
        """Return 'white' or 'black'."""
        with self._lock:
            self._send("side")
            line = self._read_line()
            return line.split()[1]

    def is_attacked(self, sq, color_str):
        """Check if sq is attacked by the given color ('white' or 'black')."""
        with self._lock:
            self._send(f"isattacked {sq} {color_str}")
            line = self._read_line()
            return line.split()[1] == "true"

    def new_game(self):
        with self._lock:
            self._send("ucinewgame")
            self._send("isready")
            self._read_until("readyok")

    def send_stop(self):
        """Send 'stop' without acquiring the lock — safe to call while search is running."""
        try:
            self._proc.stdin.write("stop\n")
            self._proc.stdin.flush()
        except Exception:
            pass

    def quit(self):
        try:
            with self._lock:
                self._send("quit")
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()

    def __del__(self):
        try:
            self.quit()
        except Exception:
            pass


# Singleton engine instance
_engine_instance = None
_engine_lock = threading.Lock()


def get_engine():
    """Return a shared UCIEngine singleton."""
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            _engine_instance = UCIEngine()
        return _engine_instance


def shutdown_engine():
    """Shut down the shared engine instance."""
    global _engine_instance
    with _engine_lock:
        if _engine_instance is not None:
            _engine_instance.quit()
            _engine_instance = None
