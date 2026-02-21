import email
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

import pytest

from duchess.email_handler import EmailBot


@pytest.fixture
def bot():
    with patch.dict("os.environ", {"GMAIL_EMAIL": "test@gmail.com", "GMAIL_APP_PASSWORD": "fake"}):
        return EmailBot()


class TestParseMove:
    def test_uci_move(self):
        assert EmailBot.parse_move("e2e4") == "e2e4"

    def test_uci_move_in_sentence(self):
        assert EmailBot.parse_move("My move is e2e4 thanks") == "e2e4"

    def test_uci_promotion(self):
        assert EmailBot.parse_move("e7e8q") == "e7e8q"

    def test_san_move(self):
        assert EmailBot.parse_move("Nf3") == "Nf3"

    def test_san_pawn(self):
        assert EmailBot.parse_move("e4") == "e4"

    def test_castling(self):
        assert EmailBot.parse_move("O-O") == "O-O"

    def test_no_move(self):
        assert EmailBot.parse_move("hello how are you") is None

    def test_strips_quoted_reply(self):
        body = "e2e4\n\nOn Mon, Jan 1 2026, someone wrote:\n> old text"
        assert EmailBot.parse_move(body) == "e2e4"

    def test_ignores_quoted_lines(self):
        body = "> e2e4\nNf3"
        assert EmailBot.parse_move(body) == "Nf3"


class TestFetchEmail:
    def test_fetch_latest_move_email(self, bot):
        # Build a fake raw email
        msg = MIMEText("e2e4")
        msg["From"] = "player@example.com"
        msg["Subject"] = "duchess"
        raw = msg.as_bytes()

        mock_imap = MagicMock()
        mock_imap.search.return_value = ("OK", [b"1 2 3"])
        mock_imap.fetch.return_value = ("OK", [(b"1", raw)])

        with patch("duchess.email_handler.imaplib.IMAP4_SSL", return_value=mock_imap):
            result = bot.fetch_latest_move_email()

        assert result is not None
        sender, subject, body = result
        assert sender == "player@example.com"
        assert subject == "duchess"
        assert "e2e4" in body

    def test_fetch_no_unseen(self, bot):
        mock_imap = MagicMock()
        mock_imap.search.return_value = ("OK", [b""])

        with patch("duchess.email_handler.imaplib.IMAP4_SSL", return_value=mock_imap):
            result = bot.fetch_latest_move_email()

        assert result is None


class TestSendReply:
    def test_send_reply(self, bot):
        mock_smtp = MagicMock()

        with patch("duchess.email_handler.smtplib.SMTP_SSL", return_value=mock_smtp):
            bot.send_reply("player@example.com", "Re: Chess", "My move: e5 (e7e5)")

        mock_smtp.login.assert_called_once()
        mock_smtp.sendmail.assert_called_once()
        mock_smtp.quit.assert_called_once()
