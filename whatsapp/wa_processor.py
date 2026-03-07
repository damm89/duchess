# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""WhatsApp adapter — wraps the existing duchess game logic for WhatsApp users."""
from sqlalchemy.orm import Session

from duchess.models import User
from duchess.processor import (
    EMAIL_FOOTER,
    _get_active_game,
    _handle_move,
    _handle_resign,
    _handle_start,
    _handle_status,
)

WA_HELP = (
    "Duchess Chess — Commands:\n"
    "  new / new black  — Start a new game\n"
    "  e4 / Nf3 / e2e4  — Make a move (SAN or UCI)\n"
    "  status           — Show current board\n"
    "  resign           — Resign\n"
    "  mode image       — Board as image\n"
    "  mode text        — Board as text\n"
    "  mode both        — Image + text (default)\n"
    "  help             — Show this message"
)

# In-memory preference store: phone -> "both" | "image" | "text"
# Defaults to "both". Resets on server restart.
_prefs: dict[str, str] = {}


def get_pref(phone: str) -> str:
    return _prefs.get(phone, "both")


def _get_or_create_user(phone: str, db: Session) -> User:
    user = db.query(User).filter(User.whatsapp == phone).first()
    if user is None:
        user = User(username=f"wa_{phone}", whatsapp=phone)
        db.add(user)
        db.commit()
    return user


def _strip_footer(text: str) -> str:
    return text.replace(EMAIL_FOOTER, "").strip()


def handle_message(phone: str, text: str, db: Session) -> tuple[str, str | None]:
    """Process an incoming WhatsApp message.

    Returns (reply_text, fen_or_None).
    fen_or_None is the current board FEN if a board should be shown, else None.
    """
    user = _get_or_create_user(phone, db)
    msg = text.strip().lower()

    # Mode toggles
    if msg == "mode image":
        _prefs[phone] = "image"
        return "Board mode: image only.", None
    if msg == "mode text":
        _prefs[phone] = "text"
        return "Board mode: text only.", None
    if msg == "mode both":
        _prefs[phone] = "both"
        return "Board mode: image + text (default).", None

    # Help
    if msg in ("help", "?"):
        return WA_HELP, None

    # Game commands — route to existing processor functions
    if msg in ("new", "start", "start white", "new white"):
        plain, _ = _handle_start(user, "white", db)
    elif msg in ("start black", "new black"):
        plain, _ = _handle_start(user, "black", db)
    elif msg in ("resign", "end"):
        plain, _ = _handle_resign(user, db)
    elif msg in ("status", "show", "board"):
        plain, _ = _handle_status(user, db)
    else:
        plain, _ = _handle_move(text.strip(), user, db)

    reply = _strip_footer(plain)

    # Get FEN for board rendering
    game = _get_active_game(user, db)
    fen = game.fen if game else None

    return reply, fen
