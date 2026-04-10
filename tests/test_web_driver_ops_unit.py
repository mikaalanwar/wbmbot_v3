import unittest
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import NoSuchElementException, TimeoutException

from wbmbot_v3.helpers import browser_actions as ba
from wbmbot_v3.helpers import listing_processor as lp


class DummyClickable:
    def __init__(self):
        self.clicked = False

    def click(self):
        self.clicked = True


class DummyWebDriver:
    def __init__(self):
        self.submitted = False

    def find_element(self, *args, **kwargs):
        clickable = DummyClickable()
        original_click = clickable.click

        def _click():
            self.submitted = True
            original_click()

        clickable.click = _click
        return clickable


class DummyUser:
    def __init__(self):
        self.notifications_email = None


class DummyTextElement:
    def __init__(self, text: str):
        self.text = text


class DummyNextButton:
    def __init__(self):
        self.clicked = False

    def click(self):
        self.clicked = True


class DummyPaginationList:
    def __init__(self, active_page: int, total_pages: int):
        self.active_page = active_page
        self.total_pages = total_pages

    def find_elements(self, by, selector):
        return [DummyTextElement(str(page)) for page in range(1, self.total_pages + 1)]

    def find_element(self, by, selector):
        if "contains(@class,'active')" not in selector:
            raise NoSuchElementException()
        return DummyTextElement(str(self.active_page))


class DummyPaginationDriver:
    def __init__(self, active_page: int, total_pages: int):
        self.page_list = DummyPaginationList(active_page, total_pages)
        self.next_button = DummyNextButton()

    def find_element(self, by, selector):
        if selector == "//ul[@class='pagination pagination-sm']":
            return self.page_list
        if selector == "//a[@title='Nächste Immobilien Seite']":
            return self.next_button
        raise NoSuchElementException()


class WebDriverOpsTests(unittest.TestCase):
    @patch("wbmbot_v3.helpers.listing_processor.notifications.send_email_notification")
    @patch("wbmbot_v3.helpers.listing_processor.browser_actions.fill_form")
    @patch("wbmbot_v3.helpers.listing_processor.browser_actions.ansehen_btn")
    @patch("wbmbot_v3.helpers.listing_processor.debug_artifacts.download_expose_as_pdf")
    def test_apply_to_flat_skips_pdf_when_no_debug(
        self,
        download_mock,
        ansehen_mock,
        fill_form_mock,
        send_mail_mock,
    ):
        ansehen_mock.return_value = "https://example.com/flat"
        web_driver = DummyWebDriver()
        user_profile = DummyUser()

        result = lp.apply_to_flat(
            web_driver,
            MagicMock(),
            0,
            "Test Flat",
            user_profile,
            "user@example.com",
            test=False,
            debug_dir=None,
        )

        self.assertTrue(result)
        self.assertTrue(web_driver.submitted)
        download_mock.assert_not_called()
        fill_form_mock.assert_called_once()
        send_mail_mock.assert_not_called()

    @patch("wbmbot_v3.helpers.browser_actions.WebDriverWait")
    def test_next_page_does_not_increment_if_navigation_never_advances(
        self,
        wait_mock,
    ):
        driver = DummyPaginationDriver(active_page=1, total_pages=2)
        wait_mock.return_value.until.side_effect = TimeoutException()

        page = ba.next_page(driver, current_page=1, terminate_on_last_page=False)

        self.assertEqual(page, 1)
        self.assertTrue(driver.next_button.clicked)

    def test_next_page_raises_when_already_at_last_page_in_run_once_mode(self):
        driver = DummyPaginationDriver(active_page=2, total_pages=2)

        with self.assertRaises(ba.LastPageReached):
            ba.next_page(driver, current_page=2, terminate_on_last_page=True)


if __name__ == "__main__":
    unittest.main()
