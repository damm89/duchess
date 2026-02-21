import logging
import time

from duchess.database import SessionLocal
from duchess.email_handler import EmailBot
from duchess.processor import process_email_move

logger = logging.getLogger(__name__)


def run_email_bot():
    bot = EmailBot()
    logger.info("Duchess email bot started. Watching %s...", bot.email_address)

    while True:
        try:
            result = bot.fetch_latest_move_email()
            if result is not None:
                sender, subject, body = result
                logger.info("Email from %s: %r", sender, body[:80])

                move_str = bot.parse_move(body)
                logger.info("Parsed move: %r", move_str)
                if move_str is None:
                    # Couldn't parse — send it through processor as-is
                    # so it can check for active game and respond appropriately
                    move_str = body.strip()

                session = SessionLocal()
                try:
                    plain, html = process_email_move(sender, move_str, session)
                    logger.info("Processor response: %r", plain[:80])
                    bot.send_reply(sender, "duchess", plain, html)
                    logger.info("Sent reply to %s for move %s", sender, move_str)
                finally:
                    session.close()

        except Exception as e:
            logger.error("Error: %s", e, exc_info=True)

        time.sleep(10)
