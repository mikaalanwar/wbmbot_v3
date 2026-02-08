import os
import re
import sys
import time
from urllib.parse import urljoin

from handlers import flat
from helpers import constants, notifications
from httpsWrapper import httpPageDownloader as hpd
from logger import wbm_logger
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utility import io_operations, misc_operations

__appname__ = os.path.splitext(os.path.basename(__file__))[0]
color_me = wbm_logger.ColoredLogger(__appname__)
LOG = color_me.create_logger()


class LastPageReached(Exception):
    """Raised when pagination has reached the final page in run-once mode."""


def _format_delay(seconds: int) -> str:
    """Return a human-readable string for the given delay seconds."""

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
    Wait before proceeding to the next application while showing a CLI countdown.
    """

    if delay_seconds <= 0:
        return

    LOG.info(
        color_me.cyan(
            f"Waiting {_format_delay(delay_seconds)} before the next application ⏱️"
        )
    )


def _sanitize_filename(value: str, fallback: str = "snapshot") -> str:
    """
    Sanitize a string for use in file names.
    """

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

    screenshot_path = os.path.join(img_dir, f"{safe_label}.png")
    try:
        web_driver.save_screenshot(screenshot_path)
    except Exception:
        screenshot_path = None

    return {"html": html_path, "screenshot": screenshot_path}


def _extract_pdf_link_from_html(page_source: str, base_url: str) -> str | None:
    """
    Try to find a PDF link inside the page source.
    """

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

    for remaining in range(delay_seconds, 0, -1):
        sys.stdout.write(
            f"\rNext application in {_format_delay(remaining)} ...".ljust(60)
        )
        sys.stdout.flush()
        time.sleep(1)

    sys.stdout.write("\rNext application starting now!             \n")
    sys.stdout.flush()


def next_page(web_driver, current_page: int, terminate_on_last_page: bool = False):
    """
    Attempts to navigate to the next page of a paginated list.

    This function checks if a next page button is present and, if so, clicks it to navigate to the next page.
    It logs the action and handles any exceptions that may occur during the process.

    Parameters:
        curr_page_num (int): The current page number.

    Returns:
        int: The updated page number after attempting to navigate to the next page.
    """

    try:
        # Attempt to find the next page button using its XPath
        next_page_button = web_driver.find_element(
            By.XPATH, "//a[@title='Nächste Immobilien Seite']"
        )

        # If the next page button is found, click it and log the action
        if next_page_button:
            page_list = web_driver.find_element(
                By.XPATH, "//ul[@class='pagination pagination-sm']"
            )
            # -2 to exclude the < and > arrows of next and previous pages
            total_pages = (
                len(page_list.find_elements(By.TAG_NAME, "li")) - 2
            )  # Adjust for non-page list items
            LOG.info(
                color_me.cyan(
                    f"Another page of flats was detected, switching to page {current_page + 1}/{total_pages} 🔀"
                )
            )
            next_page_button.click()
            return current_page + 1
    except NoSuchElementException as e:
        # Log an error if the next page button is not found
        LOG.error(color_me.red("Failed to switch page, last page reached ❌"))
        if terminate_on_last_page:
            LOG.info(color_me.cyan("Run-once mode enabled; exiting after last page."))
            raise LastPageReached()
    except Exception as e:
        # Log any other exceptions that occur
        LOG.error(color_me.red(f"Failed to switch page, returning to main page ❌"))

    # Return the current page number if navigation to the next page was not possible
    return current_page


def _find_expose_download_link(web_driver):
    """Try to locate an expose download link using multiple resilient selectors."""

    selectors = [
        (
            By.CSS_SELECTOR,
            "a.openimmo-detail__intro-expose-button",
        ),
        (
            By.XPATH,
            "//a[contains(@class,'openimmo-detail__intro-expose-button')]",
        ),
        (
            By.XPATH,
            "//a[contains(@class,'download') and contains(@href,'.pdf')]",
        ),
        (
            By.XPATH,
            "//a[@download and contains(@href,'.pdf')]",
        ),
        (
            By.XPATH,
            "//a[contains(@href,'.pdf') and contains(@class,'btn')]",
        ),
        (
            By.XPATH,
            "//a[contains(@href,'.pdf') and (contains(.,'Expose') or contains(.,'Exposé') or contains(.,'Expos') or contains(.,'Download'))]",
        ),
        (
            By.XPATH,
            "//a[contains(@href,'expos')]",
        ),
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


def download_expose_as_pdf(web_driver, flat_name: str, debug_dir: str | None = None):
    """
    Gets the EXPOSE link and saves it as a PDF in your localy directory
    """

    # Log the attempt to find the continue button
    LOG.info(color_me.cyan(f"Attempting to download expose for '{flat_name}' 📥"))

    if debug_dir:
        _debug_dump_page(
            web_driver, debug_dir, f"details_before_expose_{flat_name}"
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
                web_driver, debug_dir, f"details_missing_expose_{flat_name}"
            )
        LOG.warning(
            color_me.yellow(
                f"Expose download link not found for '{flat_name}'. Continuing without PDF. 🚧"
            )
        )
        return None

    pdf_path = hpd.download_pdf_file(
        download_link, f"{constants.offline_apartment_path}{constants.now}"
    )

    if not pdf_path:
        if debug_dir:
            _debug_dump_page(
                web_driver, debug_dir, f"details_failed_download_{flat_name}"
            )
        LOG.warning(
            color_me.yellow(
                f"Expose download failed for '{flat_name}'. Continuing without PDF. 🚧"
            )
        )

    return pdf_path


def ansehen_btn(web_driver, flat_element, index: int):
    """
    Finds and clicks the 'ansehen' button to navigate to the details page of a flat.

    This function searches for a button with the title "Details", logs its href attribute,
    scrolls it into view, and navigates to the linked details page.
    """

    try:
        # Log the attempt to find the ansehen button
        LOG.info(color_me.cyan("Looking for 'Ansehen' button 🔎"))
        # Attempt to find the ansehen button by its XPath
        ansehen_button = flat_element.find_element(
            By.XPATH, f"(//a[@title='Details'][contains(.,'Ansehen')])[{index+1}]"
        )

        # Log the href attribute of the found button
        flat_link = ansehen_button.get_attribute("href")
        LOG.info(color_me.green(f"Flat link found: {flat_link} 🎯"))

        # Scroll the button into view
        ansehen_button.location_once_scrolled_into_view

        # Navigate to the href of the ansehen button
        web_driver.get(flat_link)
        return flat_link
    except NoSuchElementException as e:
        # Log an error if the Ansehen button is not found
        LOG.error(color_me.red(f"'Ansehen' button not found ❌"))
    except StaleElementReferenceException as e:
        # Log an error if the Ansehen button is stale
        LOG.error(color_me.red(f"Stale 'Ansehen' button ❌"))


def fill_form(web_driver, user_obj, email: str, test: str):
    """
    Fills out a web form with user information and a specified email address.

    This function locates various input fields on a web form and populates them with data from the user object.
    It also logs the process and handles any exceptions that may occur during form filling.

    Parameters:
        web_driver (WebDriver): The Selenium WebDriver used to interact with the web page.
        user (User): The user object containing data to fill the form.
        email (str): The email address to be used in the form.
    """

    try:
        # Log the start of the form filling process
        LOG.info(color_me.cyan(f"Filling out form for email address '{email}' 🤖"))

        # If the user has WBS
        if user_obj.wbs and not test:
            # Click the radio button or checkbox before filling in text fields
            web_driver.find_element(
                By.XPATH, "//label[@for='powermail_field_wbsvorhanden_1']"
            ).click()

            # Fill in the user's WBS date
            web_driver.find_element(
                By.XPATH, "//input[@id='powermail_field_wbsgueltigbis']"
            ).send_keys(user_obj.wbs_date)

            # Fill in the user's WBS rooms
            web_driver.find_element(
                By.XPATH, "//select[@id='powermail_field_wbszimmeranzahl']"
            ).send_keys(user_obj.wbs_rooms)

            # Fill in the user's WBS number
            web_driver.find_element(
                By.XPATH,
                "//select[@id='powermail_field_einkommensgrenzenacheinkommensbescheinigung9']",
            ).send_keys(user_obj.wbs_num)

            # Click on Special Housing Needs if required
            if user_obj.wbs_special_housing_needs:
                web_driver.find_element(
                    By.XPATH,
                    "//label[@for='powermail_field_wbsmitbesonderemwohnbedarf_1']",
                ).click()
        else:
            web_driver.find_element(
                By.XPATH, "//label[@for='powermail_field_wbsvorhanden_2']"
            ).click()

        # Select the user's sex/gender
        web_driver.find_element(
            By.XPATH,
            "//select[@id='powermail_field_anrede']",
        ).send_keys(user_obj.sex)

        # Fill in the user's last name
        web_driver.find_element(
            By.XPATH, "//input[@id='powermail_field_name']"
        ).send_keys(user_obj.last_name)

        # Fill in the user's first name
        web_driver.find_element(
            By.XPATH, "//input[@id='powermail_field_vorname']"
        ).send_keys(user_obj.first_name)

        # Fill in the user's street address
        web_driver.find_element(
            By.XPATH, "//input[@id='powermail_field_strasse']"
        ).send_keys(user_obj.street)

        # Fill in the user's postal code
        web_driver.find_element(
            By.XPATH, "//input[@id='powermail_field_plz']"
        ).send_keys(user_obj.zip_code)

        # Fill in the user's city
        web_driver.find_element(
            By.XPATH, "//input[@id='powermail_field_ort']"
        ).send_keys(user_obj.city)

        # Fill in the email address
        web_driver.find_element(
            By.XPATH, "//input[@id='powermail_field_e_mail']"
        ).send_keys(email)

        # Fill in the user's phone number
        web_driver.find_element(
            By.XPATH, "//input[@id='powermail_field_telefon']"
        ).send_keys(user_obj.phone)

        # Click on Datenschutz
        web_driver.find_element(
            By.XPATH, "//label[@for='powermail_field_datenschutzhinweis_1']"
        ).click()

        time.sleep(10) if test else None
    except NoSuchElementException as e:
        # Log an error if any element is not found
        LOG.error(color_me.red(f"Element not found during form filling ❌"))


def accept_cookies(web_driver):
    """
    Check if the cookie dialog is displayed on the page and accept it if present.

    Parameters:
    - driver: The Selenium WebDriver instance to interact with the browser.
    - logger: A logging.Logger instance for logging messages.

    Returns:
    - bool
    """

    try:
        # Define the XPath for the 'Accept Cookies' button
        accept_button_xpath = "//button[@class='cm-btn cm-btn-success']"

        # Wait for the cookie dialog to be present and clickable
        WebDriverWait(web_driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, accept_button_xpath))
        )

        # Click the 'Accept Cookies' button
        web_driver.find_element(By.XPATH, accept_button_xpath).click()
        LOG.info(color_me.green("Cookies have been accepted 🍪"))
        return True
    except TimeoutException as e:
        return False


def close_live_chat_button(web_driver):
    """
    Close the 'Live Chat' dialog button
    """

    try:
        # Define the XPath for the 'Close Live Chat' button
        close_button_xpath = '//*[@id="removeConvaiseChat"]'

        # Wait for the Close Live Chat dialog to be present and clickable
        WebDriverWait(web_driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, close_button_xpath))
        )

        # Click the 'Close Live Chat' button
        web_driver.find_element(By.XPATH, close_button_xpath).click()
        return True
    except TimeoutException as e:
        # If the Close Live Chat does not appear within the timeout, log a message
        return False


def reset_to_start_page(
    web_driver, start_url: str, current_page: int, previous_page: int
):
    """
    Resets the WebDriver to the start URL and resets the current and previous page counters.

    This function is typically used when the page has not changed from the last iteration,
    indicating that there is only one page or the last page was reached. It reloads the first
    page and resets the page counters.

    Parameters:
    - driver: The Selenium WebDriver instance to interact with the browser.
    - start_url: The URL of the start page to load.

    Returns:
    - curr_page_num, prev_page_num
    """

    web_driver.get(start_url)
    current_page = 1
    previous_page = 1

    return current_page, previous_page


def find_flats(web_driver):
    """Find and return a list of flats from the webpage."""

    return web_driver.find_elements(By.CSS_SELECTOR, ".row.openimmo-search-list-item")


def sort_flats_by_rent(flat_elements, test: bool):
    """
    Return metadata about flats sorted by lowest rent first.
    """

    sorted_entries = []
    for index, element in enumerate(flat_elements):
        try:
            flat_source = element.get_attribute("outerHTML")
        except Exception:
            flat_source = element.text
        flat_obj = flat.Flat(flat_source, test)
        rent_value = misc_operations.convert_rent(flat_obj.total_rent)
        rent_key = rent_value if isinstance(rent_value, (int, float)) else float("inf")
        sorted_entries.append(
            {
                "index": index,
                "rent_key": rent_key,
                "display_rent": flat_obj.total_rent or "unknown",
                "title": flat_obj.title or f"Flat #{index + 1}",
                "flat": flat_obj,
            }
        )

    sorted_entries.sort(
        key=lambda entry: (
            entry["rent_key"],
            entry["title"].lower() if entry["title"] else "",
        )
    )
    return sorted_entries


def apply_to_flat(
    web_driver,
    flat_element,
    flat_index: int,
    flat_title: str,
    user_profile,
    email: str,
    test: bool,
    debug_dir: str | None = None,
):
    """Apply to the flat using the provided email."""

    # Find and click "Ansehen" button on current flat
    flat_link = ansehen_btn(web_driver, flat_element, flat_index)
    if "seniorenwohnungen" in flat_link:
        return False
    if debug_dir:
        _debug_dump_page(web_driver, debug_dir, f"details_loaded_{flat_title}")
    # Fill out application form on current flat using info stored in user object
    fill_form(web_driver, user_profile, email, test)

    # Download as PDF (only in debug mode)
    pdf_path = None
    if not test and debug_dir:
        pdf_path = download_expose_as_pdf(web_driver, flat_title, debug_dir)

    # Submit form
    if not test:
        web_driver.find_element(By.XPATH, "//button[@type='submit']").click()

    # Send e-mail
    if not test and user_profile.notifications_email:
        notifications.send_email_notification(
            email,
            user_profile.notifications_email,
            f"[Applied] {flat_title}",
            f"Appartment Link: {flat_link}\n\nYour Profile:\n\n{user_profile}",
            pdf_path,
        )

    return True


def process_flats(
    web_driver,
    user_profiles,
    start_url: str,
    current_page: int,
    previous_page: int,
    page_changed: bool,
    refresh_internal: int,
    test: bool,
    application_delay_seconds: int,
    run_once: bool = False,
    exit_on_last_page: bool = False,
    application_store=None,
    debug_dir: str | None = None,
):
    """Process each flat by checking criteria and applying if applicable."""

    while True:

        if not misc_operations.check_internet_connection():
            LOG.error(
                color_me.red("No internet connection found. Retrying in 10 seconds ⚠️")
            )
            if run_once:
                LOG.error(color_me.red("Run-once mode enabled; exiting."))
                return
            time.sleep(10)
            continue

        if not page_changed:
            current_page, previous_page = reset_to_start_page(
                web_driver, start_url, current_page, previous_page
            )

        accept_cookies(web_driver)
        close_live_chat_button(web_driver)

        # Find all flat offers displayed on current page
        LOG.info(color_me.cyan("Looking for flats 👀"))
        all_flats = find_flats(web_driver)
        if not all_flats:
            LOG.info(color_me.cyan("Currently no flats available 😔"))
            if run_once:
                LOG.info(color_me.cyan("Run-once mode enabled; exiting."))
                return
            time.sleep(int(refresh_internal) * 60)
            continue

        LOG.info(color_me.green(f"Found {len(all_flats)} flat(s) in total 💡"))

        # Save locally
        if not test:
            snapshot_path = os.path.join(
                constants.offline_angebote_path,
                constants.now,
                f"page_{current_page}.html",
            )
            hpd.save_rendered_page(web_driver.page_source, snapshot_path)
            LOG.info(
                color_me.cyan(
                    f"Saved HTML snapshot for page {current_page} at {snapshot_path} 💾"
                )
            )
        if debug_dir:
            _debug_dump_page(web_driver, debug_dir, f"list_page_{current_page}")

        restart_processing = False
        sorted_entries = sort_flats_by_rent(all_flats, test)
        if sorted_entries:
            preview = ", ".join(
                f"{entry['title']} ({entry['display_rent']})"
                for entry in sorted_entries[:3]
            )
            LOG.info(
                color_me.cyan(
                    "Processing flats in ascending rent order 🧮"
                    + (f" | Preview: {preview}" if preview else "")
                )
            )

        for position, entry in enumerate(sorted_entries):
            time.sleep(2)  # Sleep to mimic human behavior and avoid detection

            # Refresh Flat Elements to avoid staleness
            all_flats = find_flats(web_driver)
            flat_index = entry["index"]
            if flat_index >= len(all_flats):
                LOG.warning(
                    color_me.yellow(
                        "Flat list changed while iterating; restarting processing loop 🔄"
                    )
                )
                restart_processing = True
                break
            flat_elem = all_flats[flat_index]
            # Create flat object
            flat_obj = entry.get("flat")
            if not flat_obj:
                try:
                    flat_source = flat_elem.get_attribute("outerHTML")
                except Exception:
                    flat_source = flat_elem.text
                flat_obj = flat.Flat(flat_source, test)
                entry["flat"] = flat_obj

            if test:
                LOG.info(color_me.magenta(f"Flat Element: {flat_elem.text}"))
                LOG.info(color_me.magenta(f"Flat Obj: {flat_obj}"))

            for user_profile in user_profiles:
                if not getattr(user_profile, "emails", None):
                    continue
                for email in user_profile.emails:
                    # Proceed to check whether we should apply to the flat or skip
                    if application_store is None:
                        raise RuntimeError("Application store is not configured.")

                    if not application_store.has_applied(email, flat_obj):
                        if misc_operations.contains_filter_keywords(
                            flat_elem, user_profile.exclude
                        )[0]:
                            LOG.warning(
                                color_me.yellow(
                                    f"Ignoring flat '{flat_obj.title}' because it contains exclude keyword(s) --> {misc_operations.contains_filter_keywords(flat_elem, user_profile.exclude)[1]} 🙈"
                                )
                            )
                            continue
                        if flat_obj.wbs and not user_profile.wbs:
                            LOG.warning(
                                color_me.yellow(
                                    f"Ignoring flat '{flat_obj.title}' because it requires WBS and your profile has no WBS 🙈"
                                )
                            )
                            continue
                        if not misc_operations.verify_flat_rent(
                            misc_operations.convert_rent(flat_obj.total_rent),
                            user_profile.flat_rent_below,
                        ):
                            LOG.warning(
                                color_me.yellow(
                                    f"Ignoring flat '{flat_obj.title}' because the rent doesn't match our criteria --> Flat Rent: {misc_operations.convert_rent(flat_obj.total_rent)} € | User wants it below: {user_profile.flat_rent_below} € 🙈"
                                )
                            )
                            continue
                        if not misc_operations.verify_flat_size(
                            misc_operations.convert_size(flat_obj.size),
                            user_profile.flat_size_above,
                        ):
                            LOG.warning(
                                color_me.yellow(
                                    f"Ignoring flat '{flat_obj.title}' because the size doesn't match our criteria --> Flat Size: {misc_operations.convert_size(flat_obj.size)} m² | User wants it above: {user_profile.flat_size_above} m² 🙈"
                                )
                            )
                            continue
                        if not misc_operations.verify_flat_rooms(
                            misc_operations.get_zimmer_count(flat_obj.rooms),
                            user_profile.flat_rooms_above,
                        ):
                            LOG.warning(
                                color_me.yellow(
                                    f"Ignoring flat '{flat_obj.title}' because the rooms don't match our criteria --> Flat Rooms: {misc_operations.get_zimmer_count(flat_obj.rooms)} | User wants it above: {user_profile.flat_rooms_above} 🙈"
                                )
                            )
                            continue
                        applied = apply_to_flat(
                            web_driver,
                            flat_elem,
                            flat_index,
                            flat_obj.title,
                            user_profile,
                            email,
                            test,
                            debug_dir,
                        )
                        if applied:
                            LOG.info(
                                color_me.cyan(
                                    f"Applying to flat: {flat_obj.title} for '{email}' 📩"
                                )
                            )
                            application_store.record_application(email, flat_obj)
                            LOG.info(color_me.green("Done ✅"))
                            wait_before_next_application(application_delay_seconds)
                            web_driver.get(start_url)
                            time.sleep(1.5)
                            restart_processing = True
                            break
                        else:
                            LOG.warning(
                                color_me.yellow(
                                    f"Ignoring flat: {flat_obj.title} because it is for Seniors only ('seniorenwohnungen') 🙈"
                                )
                            )
                    else:
                        LOG.warning(
                            color_me.yellow(
                                f"Oops, we already applied for flat: {flat_obj.title} 🚫"
                            )
                        )
                        continue

                if restart_processing:
                    break

            if restart_processing:
                break

            # Try to switch to next page if exists, in the last iteration
            if position == len(sorted_entries) - 1:
                previous_page = current_page
                try:
                    current_page = next_page(
                        web_driver,
                        current_page,
                        terminate_on_last_page=run_once or exit_on_last_page,
                    )
                except LastPageReached:
                    return
                page_changed = current_page != previous_page

        if restart_processing:
            continue

        if (run_once or exit_on_last_page) and not page_changed:
            LOG.info(
                color_me.cyan(
                    "Exit condition met (run-once/exit-on-last-page); exiting."
                )
            )
            return

        if not page_changed:
            time.sleep(int(refresh_internal) * 60)
        else:
            time.sleep(1.5)

        LOG.info(color_me.cyan("Reloading main page 🔄"))
