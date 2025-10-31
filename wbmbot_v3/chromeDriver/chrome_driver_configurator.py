import os
import stat

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class ChromeDriverConfigurator:
    """
    Class to create the WebDriver with ChromeOptions
    """

    def __init__(self, headless: bool, test: bool):
        """
        Create a ChromeDriver with default options
        """
        self.headless = headless
        self.test = test
        self.chrome_options = Options()
        self.configure_options()
        self.driver = self.create_driver()

    def configure_options(self):
        """
        Add ChromeOption defaults
        """
        self.chrome_options.add_argument("--disable-extensions")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--disable-logging")
        self.chrome_options.add_argument("--log-level=3")
        if self.headless:
            self.chrome_options.add_argument("--headless")
            self.chrome_options.add_argument("--no-sandbox")
        if self.test:
            self.chrome_options.add_argument("--log-level=0")

    def create_driver(self):
        """
        Creates the driver with the specified ChromeOptions
        """
        driver_path = self._resolve_chromedriver_path(ChromeDriverManager().install())

        self.driver = webdriver.Chrome(
            service=Service(driver_path),
            options=self.chrome_options,
        )
        # Wait 5 seconds before doing stuff
        self.driver.implicitly_wait(5)
        return self.driver

    def get_driver(self):
        return self.driver

    @staticmethod
    def _resolve_chromedriver_path(downloaded_path: str) -> str:
        """
        Ensure the path returned by webdriver-manager points to an executable chromedriver.
        """

        def ensure_executable(path: str) -> str:
            if not os.access(path, os.X_OK):
                current_mode = os.stat(path).st_mode
                os.chmod(
                    path,
                    current_mode
                    | stat.S_IXUSR
                    | stat.S_IXGRP
                    | stat.S_IXOTH,
                )
            return path

        base_name = os.path.basename(downloaded_path)
        if base_name.startswith("chromedriver") and not base_name.endswith(".chromedriver"):
            return ensure_executable(downloaded_path)

        driver_directory = (
            downloaded_path
            if os.path.isdir(downloaded_path)
            else os.path.dirname(downloaded_path)
        )
        candidates = [
            os.path.join(driver_directory, name)
            for name in os.listdir(driver_directory)
            if name.startswith("chromedriver") and not name.endswith(".chromedriver")
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return ensure_executable(candidate)

        return ensure_executable(downloaded_path)
