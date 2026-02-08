import logging
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "wbmbot_v3"))

from helpers import webDriverOperations  # noqa: E402
from utility import io_operations  # noqa: E402


class DebugModeTests(unittest.TestCase):
    def test_initialize_debug_logging_writes_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "wbmbot-debug.log")
            io_operations.initialize_debug_logging(log_path)

            logger = logging.getLogger("debug-test")
            logger.info("debug log message")

            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.flush()

            with open(log_path, "r", encoding="utf-8") as handle:
                contents = handle.read()

            self.assertIn("debug log message", contents)

            for handler in list(root_logger.handlers):
                if isinstance(handler, logging.FileHandler) and os.path.abspath(
                    handler.baseFilename
                ) == os.path.abspath(log_path):
                    handler.close()
                    root_logger.removeHandler(handler)

    def test_extract_pdf_link_from_html(self):
        html = "<a class='download' href='/files/expose.pdf'>Expos\u00e9</a>"
        link = webDriverOperations._extract_pdf_link_from_html(
            html, "https://example.com/page"
        )
        self.assertEqual(link, "https://example.com/files/expose.pdf")


if __name__ == "__main__":
    unittest.main()
