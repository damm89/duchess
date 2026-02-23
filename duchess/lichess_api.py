"""Lichess Opening Explorer API client.

Queries the Lichess Opening Explorer (https://lichess.org/api#tag/Opening-Explorer)
to retrieve opening statistics from the Masters database.

Credits:
    This module uses the free, open Lichess Opening Explorer API.
    Lichess (https://lichess.org) is a free, open-source chess server
    powered by volunteers and donations. The Opening Explorer data is
    sourced from over-the-board master games (2200+ FIDE rated).

    We gratefully acknowledge the Lichess team and community for
    providing this invaluable resource to the chess world.

    API documentation: https://lichess.org/api#tag/Opening-Explorer
    Lichess source code: https://github.com/lichess-org/lila
"""
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

MASTERS_API_URL = "https://explorer.lichess.ovh/masters"

# Polite User-Agent per Lichess API guidelines
_USER_AGENT = "Duchess Chess Application (https://github.com/damm89/duchess)"
_REQUEST_TIMEOUT = 8  # seconds


class LichessExplorerClient:
    """Queries the Lichess Masters Opening Explorer and caches results.

    Usage::

        client = LichessExplorerClient()
        result = client.query("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        for move in result["moves"]:
            print(move["san"], move["total"], move["win_pct"])
    """

    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": _USER_AGENT})

    def query(self, fen: str) -> dict:
        """Query the Lichess Masters database for the given FEN.

        Returns a dict with keys:
            - opening: str or None  (e.g. "B00 · King's Pawn Game")
            - total: int            (total games in this position)
            - moves: list[dict]     (each with san, uci, total, white, draws,
                                     black, win_pct, draw_pct, loss_pct,
                                     avg_rating, opening_eco, opening_name)

        Returns an empty-ish result on network errors (never raises).
        """
        # Normalize FEN for caching (strip move counters if desired)
        cache_key = fen.strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._fetch(fen)
        self._cache[cache_key] = result
        return result

    def _fetch(self, fen: str) -> dict:
        """Perform the HTTP request and parse the response."""
        empty = {"opening": None, "total": 0, "moves": []}
        try:
            resp = self._session.get(
                MASTERS_API_URL,
                params={"fen": fen},
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("Lichess API request failed: %s", exc)
            return empty
        except ValueError as exc:
            logger.warning("Lichess API returned invalid JSON: %s", exc)
            return empty

        return self._parse(data)

    @staticmethod
    def _parse(data: dict) -> dict:
        """Parse raw Lichess JSON into our internal format."""
        # Overall totals for the position
        total_white = data.get("white", 0)
        total_draws = data.get("draws", 0)
        total_black = data.get("black", 0)
        total = total_white + total_draws + total_black

        # Opening info (may be null for starting position)
        opening_raw = data.get("opening")
        if opening_raw:
            opening_str = f"{opening_raw.get('eco', '')} · {opening_raw.get('name', '')}"
        else:
            opening_str = None

        moves = []
        for m in data.get("moves", []):
            w = m.get("white", 0)
            d = m.get("draws", 0)
            b = m.get("black", 0)
            t = w + d + b
            if t == 0:
                continue

            # Per-move opening info
            move_opening = m.get("opening") or {}

            moves.append({
                "san": m.get("san", "?"),
                "uci": m.get("uci", ""),
                "white": w,
                "draws": d,
                "black": b,
                "total": t,
                "win_pct": round(100 * w / t, 1),
                "draw_pct": round(100 * d / t, 1),
                "loss_pct": round(100 * b / t, 1),
                "avg_rating": m.get("averageRating", 0),
                "opening_eco": move_opening.get("eco", ""),
                "opening_name": move_opening.get("name", ""),
            })

        return {
            "opening": opening_str,
            "total": total,
            "moves": moves,
        }

    def clear_cache(self):
        """Clear the in-memory cache."""
        self._cache.clear()
