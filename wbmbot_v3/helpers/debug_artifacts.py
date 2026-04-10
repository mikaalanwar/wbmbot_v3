import os
import re
import sys
import time
from urllib.parse import urljoin

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from wbmbot_v3.helpers import constants
from wbmbot_v3.httpsWrapper import httpPageDownloader as hpd
from wbmbot_v3.logger import wbm_logger
from wbmbot_v3.utility import io_operations

__appname__ = os.path.splitext(os.path.basename(__file__))[0]
color_me = wbm_logger.ColoredLogger(__appname__)
LOG = color_me.create_logger()


def _format_delay(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"

    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"

    hours, minutes = divmod(minutes, 60)
    parts = [f"{hours}h"]
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts)


def wait_before_next_application(delay_seconds: int) -> None:
    """
    Wait before the next application while showing a CLI countdown.
    """

    if delay_seconds <= 0:
        return

    LOG.info(
        color_me.cyan(
            f"Waiting {_format_delay(delay_seconds)} before the next application ⏱️"
        )
    )

    for remaining in range(delay_seconds, 0, -1):
        sys.stdout.write(
            f"\rNext application in {_format_delay(remaining)} ...".ljust(60)
        )
        sys.stdout.flush()
        time.sleep(1)

    sys.stdout.write("\rNext application starting now!             \n")
    sys.stdout.flush()


def _sanitize_filename(value: str, fallback: str = "snapshot") -> str:
    if not value:
        return fallback
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return sanitized or fallback


def _debug_dump_page(web_driver, debug_dir: str, label: str) -> dict:
    """
    Dump the current page HTML and screenshot to the debug directory.
    """

    if not debug_dir:
        return {}

    safe_label = _sanitize_filename(label)
    html_dir = os.path.join(debug_dir, "html")
    img_dir = os.path.join(debug_dir, "screenshots")
    io_operations.create_directory_if_not_exists(html_dir)
    io_operations.create_directory_if_not_exists(img_dir)

    html_path = os.path.join(html_dir, f"{safe_label}.html")
    try:
        html_source = web_driver.page_source
    except Exception:
        html_source = ""
    hpd.save_rendered_page(html_source, html_path)

    screenshot_path: str | None = os.path.join(img_dir, f"{safe_label}.png")
    try:
        web_driver.save_screenshot(screenshot_path)
    except Exception:
        screenshot_path = None

    return {"html": html_path, "screenshot": screenshot_path}


def _extract_pdf_link_from_html(page_source: str, base_url: str) -> str | None:
    if not page_source:
        return None

    patterns = [
        r"href=['\"]([^'\"]+\.pdf[^'\"]*)['\"]",
        r"data-href=['\"]([^'\"]+\.pdf[^'\"]*)['\"]",
        r"data-url=['\"]([^'\"]+\.pdf[^'\"]*)['\"]",
        r"['\"](https?://[^'\"]+\.pdf[^'\"]*)['\"]",
    ]

    seen = set()
    for pattern in patterns:
        for match in re.findall(pattern, page_source, flags=re.IGNORECASE):
            if not match:
                continue
            candidate = match.strip()
            if candidate in seen:
                continue
            seen.add(candidate)
            return urljoin(base_url, candidate)

    return None


def _find_expose_download_link(web_driver):
    selectors = [
        (By.CSS_SELECTOR, "a.openimmo-detail__intro-expose-button"),
        (
            By.XPATH,
            "//a[contains(@class,'openimmo-detail__intro-expose-button')]",
        ),
        (By.XPATH, "//a[contains(@class,'download') and contains(@href,'.pdf')]"),
        (By.XPATH, "//a[@download and contains(@href,'.pdf')]"),
        (By.XPATH, "//a[contains(@href,'.pdf') and contains(@class,'btn')]"),
        (
            By.XPATH,
            "//a[contains(@href,'.pdf') and (contains(.,'Expose') or contains(.,'Exposé') or contains(.,'Expos') or contains(.,'Download'))]",
        ),
        (By.XPATH, "//a[contains(@href,'expos')]"),
        (
            By.XPATH,
            "//button[contains(@class,'download') and (@data-href or @data-url)]",
        ),
    ]

    for by, selector in selectors:
        try:
            elements = web_driver.find_elements(by, selector)
        except Exception:
            continue

        for element in elements:
            try:
                link = (
                    element.get_attribute("href")
                    or element.get_attribute("data-href")
                    or element.get_attribute("data-url")
                )
            except StaleElementReferenceException:
                continue

            if link:
                return urljoin(web_driver.current_url, link)

    return _extract_pdf_link_from_html(web_driver.page_source, web_driver.current_url)


def download_expose_as_pdf(
    web_driver,
    flat_name: str,
    runtime_paths: constants.RuntimePaths | None = None,
    debug_dir: str | None = None,
):
    """
    Download the expose PDF for the current flat if a link can be found.
    """

    LOG.info(color_me.cyan(f"Attempting to download expose for '{flat_name}' 📥"))
    runtime_paths = runtime_paths or constants.build_runtime_paths()

    if debug_dir:
        _debug_dump_page(
            web_driver,
            debug_dir,
            f"details_before_expose_{flat_name}",
        )

    download_link = None
    try:
        download_link = WebDriverWait(web_driver, 5).until(
            lambda driver: _find_expose_download_link(driver)
        )
    except TimeoutException:
        download_link = _find_expose_download_link(web_driver)

    if not download_link:
        if debug_dir:
            _debug_dump_page(
                web_driver,
                debug_dir,
                f"details_missing_expose_{flat_name}",
            )
        LOG.warning(
            color_me.yellow(
                f"Expose download link not found for '{flat_name}'. Continuing without PDF. 🚧"
            )
        )
        return None

    pdf_path = hpd.download_pdf_file(
        download_link,
        os.path.join(runtime_paths.offline_apartment_path, runtime_paths.run_label),
    )

    if not pdf_path:
        if debug_dir:
            _debug_dump_page(
                web_driver,
                debug_dir,
                f"details_failed_download_{flat_name}",
            )
        LOG.warning(
            color_me.yellow(
                f"Expose download failed for '{flat_name}'. Continuing without PDF. 🚧"
            )
        )

    return pdf_path
