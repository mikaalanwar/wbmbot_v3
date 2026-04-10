import os
import re
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from wbmbot_v3.logger import wbm_logger

__appname__ = os.path.splitext(os.path.basename(__file__))[0]
color_me = wbm_logger.ColoredLogger(__appname__)
LOG = color_me.create_logger()


class LastPageReached(Exception):
    """Raised when pagination has reached the final page in run-once mode."""


def _extract_page_number(text: str) -> int | None:
    match = re.search(r"\b(\d+)\b", text or "")
    if not match:
        return None
    return int(match.group(1))


def _get_pagination_state(web_driver) -> tuple[int | None, int | None]:
    """
    Return the current active page number and total number of pages.
    """

    page_list = web_driver.find_element(
        By.XPATH,
        "//ul[@class='pagination pagination-sm']",
    )
    page_links = page_list.find_elements(
        By.XPATH,
        ".//a[contains(@class,'pagelink') and not(@data-action)]",
    )
    page_numbers = [
        page_number
        for link in page_links
        if (page_number := _extract_page_number(getattr(link, "text", ""))) is not None
    ]
    total_pages = max(page_numbers) if page_numbers else None

    try:
        active_link = page_list.find_element(
            By.XPATH,
            ".//li[contains(@class,'active')]/a[contains(@class,'pagelink') and not(@data-action)]",
        )
    except NoSuchElementException:
        active_page = None
    else:
        active_page = _extract_page_number(getattr(active_link, "text", ""))

    return active_page, total_pages


def next_page(web_driver, current_page: int, terminate_on_last_page: bool = False):
    """
    Attempt to navigate to the next page of listings.
    """

    try:
        active_page, total_pages = _get_pagination_state(web_driver)
        page_number = active_page or current_page
        if total_pages is not None and page_number >= total_pages:
            LOG.error(color_me.red("Failed to switch page, last page reached ❌"))
            if terminate_on_last_page:
                LOG.info(
                    color_me.cyan("Run-once mode enabled; exiting after last page.")
                )
                raise LastPageReached()
            return current_page

        next_page_button = web_driver.find_element(
            By.XPATH,
            "//a[@title='Nächste Immobilien Seite']",
        )

        if next_page_button:
            target_page = (
                min(page_number + 1, total_pages)
                if total_pages is not None
                else page_number + 1
            )
            LOG.info(
                color_me.cyan(
                    f"Another page of flats was detected, switching to page {target_page}/{total_pages or '?'} 🔀"
                )
            )
            next_page_button.click()
            try:
                WebDriverWait(web_driver, 5).until(
                    lambda driver: (
                        (_get_pagination_state(driver)[0] or page_number) > page_number
                    )
                )
            except TimeoutException:
                LOG.warning(
                    color_me.yellow(
                        "Next-page navigation did not advance; treating this as the last reachable page 🚧"
                    )
                )
                return current_page

            updated_page, _ = _get_pagination_state(web_driver)
            return updated_page or target_page
    except LastPageReached:
        raise
    except NoSuchElementException:
        LOG.error(color_me.red("Failed to switch page, last page reached ❌"))
        if terminate_on_last_page:
            LOG.info(color_me.cyan("Run-once mode enabled; exiting after last page."))
            raise LastPageReached()
    except Exception:
        LOG.error(color_me.red("Failed to switch page, returning to main page ❌"))

    return current_page


def ansehen_btn(web_driver, flat_element, index: int):
    """
    Open the details page for a flat.
    """

    try:
        LOG.info(color_me.cyan("Looking for 'Ansehen' button 🔎"))
        ansehen_button = flat_element.find_element(
            By.XPATH,
            f"(//a[@title='Details'][contains(.,'Ansehen')])[{index + 1}]",
        )

        flat_link = ansehen_button.get_attribute("href")
        LOG.info(color_me.green(f"Flat link found: {flat_link} 🎯"))
        ansehen_button.location_once_scrolled_into_view
        web_driver.get(flat_link)
        return flat_link
    except NoSuchElementException:
        LOG.error(color_me.red("'Ansehen' button not found ❌"))
    except StaleElementReferenceException:
        LOG.error(color_me.red("Stale 'Ansehen' button ❌"))
    return None


def fill_form(web_driver, user_obj, email: str, test: bool):
    """
    Fill the WBM form with the provided user data.
    """

    try:
        LOG.info(color_me.cyan(f"Filling out form for email address '{email}' 🤖"))

        if user_obj.wbs and not test:
            web_driver.find_element(
                By.XPATH,
                "//label[@for='powermail_field_wbsvorhanden_1']",
            ).click()
            web_driver.find_element(
                By.XPATH,
                "//input[@id='powermail_field_wbsgueltigbis']",
            ).send_keys(user_obj.wbs_date)
            web_driver.find_element(
                By.XPATH,
                "//select[@id='powermail_field_wbszimmeranzahl']",
            ).send_keys(user_obj.wbs_rooms)
            web_driver.find_element(
                By.XPATH,
                "//select[@id='powermail_field_einkommensgrenzenacheinkommensbescheinigung9']",
            ).send_keys(user_obj.wbs_num)

            if user_obj.wbs_special_housing_needs:
                web_driver.find_element(
                    By.XPATH,
                    "//label[@for='powermail_field_wbsmitbesonderemwohnbedarf_1']",
                ).click()
        else:
            web_driver.find_element(
                By.XPATH,
                "//label[@for='powermail_field_wbsvorhanden_2']",
            ).click()

        web_driver.find_element(
            By.XPATH,
            "//select[@id='powermail_field_anrede']",
        ).send_keys(user_obj.sex)
        web_driver.find_element(
            By.XPATH,
            "//input[@id='powermail_field_name']",
        ).send_keys(user_obj.last_name)
        web_driver.find_element(
            By.XPATH,
            "//input[@id='powermail_field_vorname']",
        ).send_keys(user_obj.first_name)
        web_driver.find_element(
            By.XPATH,
            "//input[@id='powermail_field_strasse']",
        ).send_keys(user_obj.street)
        web_driver.find_element(
            By.XPATH,
            "//input[@id='powermail_field_plz']",
        ).send_keys(user_obj.zip_code)
        web_driver.find_element(
            By.XPATH,
            "//input[@id='powermail_field_ort']",
        ).send_keys(user_obj.city)
        web_driver.find_element(
            By.XPATH,
            "//input[@id='powermail_field_e_mail']",
        ).send_keys(email)
        web_driver.find_element(
            By.XPATH,
            "//input[@id='powermail_field_telefon']",
        ).send_keys(user_obj.phone)
        web_driver.find_element(
            By.XPATH,
            "//label[@for='powermail_field_datenschutzhinweis_1']",
        ).click()

        if test:
            time.sleep(10)
    except NoSuchElementException:
        LOG.error(color_me.red("Element not found during form filling ❌"))


def accept_cookies(web_driver) -> bool:
    """
    Accept the cookie dialog if it is shown.
    """

    try:
        accept_button_xpath = "//button[@class='cm-btn cm-btn-success']"
        WebDriverWait(web_driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, accept_button_xpath))
        )
        web_driver.find_element(By.XPATH, accept_button_xpath).click()
        LOG.info(color_me.green("Cookies have been accepted 🍪"))
        return True
    except TimeoutException:
        return False


def close_live_chat_button(web_driver) -> bool:
    """
    Close the live chat dialog if it is shown.
    """

    try:
        close_button_xpath = '//*[@id="removeConvaiseChat"]'
        WebDriverWait(web_driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, close_button_xpath))
        )
        web_driver.find_element(By.XPATH, close_button_xpath).click()
        return True
    except TimeoutException:
        return False


def reset_to_start_page(
    web_driver,
    start_url: str,
    current_page: int,
    previous_page: int,
):
    """
    Reset the webdriver to the first page.
    """

    web_driver.get(start_url)
    current_page = 1
    previous_page = 1
    return current_page, previous_page


def find_flats(web_driver):
    """Find and return all flat listing elements on the current page."""

    return web_driver.find_elements(By.CSS_SELECTOR, ".row.openimmo-search-list-item")
