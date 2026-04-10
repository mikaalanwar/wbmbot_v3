"""
Compatibility facade for legacy imports.
"""

from wbmbot_v3.helpers import notifications
from wbmbot_v3.helpers.browser_actions import (
    LastPageReached,
    accept_cookies,
    ansehen_btn,
    close_live_chat_button,
    fill_form,
    find_flats,
    next_page,
    reset_to_start_page,
)
from wbmbot_v3.helpers.debug_artifacts import (
    _debug_dump_page,
    _extract_pdf_link_from_html,
    _format_delay,
    _sanitize_filename,
    download_expose_as_pdf,
    wait_before_next_application,
)
from wbmbot_v3.helpers.listing_processor import (
    apply_to_flat,
    process_flats,
    sort_flats_by_rent,
)

__all__ = [
    "LastPageReached",
    "_debug_dump_page",
    "_extract_pdf_link_from_html",
    "_format_delay",
    "_sanitize_filename",
    "accept_cookies",
    "ansehen_btn",
    "apply_to_flat",
    "close_live_chat_button",
    "download_expose_as_pdf",
    "fill_form",
    "find_flats",
    "next_page",
    "notifications",
    "process_flats",
    "reset_to_start_page",
    "sort_flats_by_rent",
    "wait_before_next_application",
]
