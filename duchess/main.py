import argparse
import logging
import sys

from duchess.logging_config import setup_logging
from duchess.main_email import run_email_bot

logger = logging.getLogger(__name__)


def _default_mode():
    """Default to GUI when running as a PyInstaller bundle, email otherwise."""
    if getattr(sys, '_MEIPASS', None):
        return "gui"
    return "email"


def main():
    parser = argparse.ArgumentParser(description="Duchess Chess Bot")
    parser.add_argument(
        "--mode", default=_default_mode(), choices=["email", "gui"], help="Bot mode"
    )
    args = parser.parse_args()

    setup_logging()
    logger.info("Starting Duchess in %s mode", args.mode)

    if args.mode == "gui":
        try:
            import sys
            from PyQt6.QtWidgets import QApplication
            from duchess.gui.main_window import MainWindow
        except ImportError:
            logger.error("PyQt6 is required for GUI mode. Install it with: pip install PyQt6")
            return
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    elif args.mode == "email":
        run_email_bot()


if __name__ == "__main__":
    main()
