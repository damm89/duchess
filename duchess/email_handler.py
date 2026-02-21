import email
import imaplib
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()


class EmailBot:
    IMAP_HOST = "imap.gmail.com"
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 465

    def __init__(self):
        self.email_address = os.environ["GMAIL_EMAIL"]
        self.app_password = os.environ["GMAIL_APP_PASSWORD"]

    def connect_imap(self):
        imap = imaplib.IMAP4_SSL(self.IMAP_HOST)
        imap.login(self.email_address, self.app_password)
        return imap

    def connect_smtp(self):
        smtp = smtplib.SMTP_SSL(self.SMTP_HOST, self.SMTP_PORT)
        smtp.login(self.email_address, self.app_password)
        return smtp

    def fetch_latest_move_email(self):
        imap = self.connect_imap()
        try:
            imap.select("INBOX")
            status, data = imap.search(None, "UNSEEN", "SUBJECT", '"duchess"')
            if status != "OK" or not data[0]:
                return None

            msg_ids = data[0].split()
            latest_id = msg_ids[-1]

            status, msg_data = imap.fetch(latest_id, "(RFC822)")
            if status != "OK":
                return None

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            sender = email.utils.parseaddr(msg["From"])[1]
            subject = msg.get("Subject", "")

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(
                            "utf-8", errors="replace"
                        )
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

            return (sender, subject, body)
        finally:
            imap.logout()

    def send_reply(self, to_email, subject, body, html_body=None):
        if html_body:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
        else:
            msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.email_address
        msg["To"] = to_email

        smtp = self.connect_smtp()
        try:
            smtp.sendmail(self.email_address, to_email, msg.as_string())
        finally:
            smtp.quit()

    @staticmethod
    def parse_move(body):
        # Strip quoted reply text (lines starting with >)
        lines = body.splitlines()
        clean_lines = []
        for line in lines:
            if line.startswith("On ") and "wrote:" in line:
                break
            if line.startswith(">"):
                continue
            clean_lines.append(line)
        text = " ".join(clean_lines).strip()

        # Check for commands first
        text_lower = text.lower()
        for cmd in (
            "start white",
            "start as white",
            "start black",
            "start as black",
            "start",
            "resign",
            "end",
            "status",
            "show",
            "help",
            "?",
        ):
            if text_lower.startswith(cmd):
                return text_lower

        # Try UCI format first (e.g. e2e4, e7e8q)
        uci_match = re.search(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b", text, re.IGNORECASE)
        if uci_match:
            return uci_match.group(1).lower()

        # Try SAN format (e.g. Nf3, e4, O-O, Qxd7+)
        san_match = re.search(
            r"\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?)\b", text
        )
        if san_match:
            return san_match.group(1)

        return None
