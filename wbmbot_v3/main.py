import argparse
import os
import time

from chromeDriver import chrome_driver_configurator as cdc
from handlers import user
from helpers import constants, webDriverOperations
from logger import wbm_logger
from utility import io_operations, misc_operations
from utility.config_store import build_config_store
from utility.application_store import build_application_store

__appname__ = os.path.splitext(os.path.basename(__file__))[0]
os.environ["WDM_LOG"] = "0"


def parse_args():
    """
    Parse the command line arguments
    """

    def _env_choice(name: str, allowed: set, fallback: str) -> str:
        value = os.environ.get(name)
        if value and value.strip().lower() in allowed:
            return value.strip().lower()
        return fallback

    default_app_store = _env_choice(
        "APPLICATIONS_STORE", {"file", "firestore"}, "file"
    )
    default_config_store = _env_choice("CONFIG_STORE", {"file", "firestore"}, "file")

    parser = argparse.ArgumentParser(
        description="A Selenium-based bot that scrapes 'WBM Angebote' page and auto applies on appartments based on user exclusion filters",
        usage=(
            "%(prog)s [-i INTERVAL] [-H|--no-headless] [-t] [-d DELAY] "
            "[--run-once] [--exit-on-last-page|--no-exit-on-last-page] "
            "[--applications-store {file,firestore}] "
            "[--config-store {file,firestore}] "
            "[--config-key KEY] "
            "[--firestore-project-id PROJECT] "
            "[--firestore-collection COLLECTION] "
            "[--firestore-config-collection COLLECTION] "
            "[--firestore-credentials PATH] "
            "[--firestore-database DATABASE]"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-i",
        "--interval",
        dest="interval",
        default=3,
        required=False,
        help="Set the time interval in 'minutes' to check for new flats (refresh) on wbm.de. [default: 3 minutes]",
    )
    parser.add_argument(
        "-H",
        "--headless",
        dest="headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        required=False,
        help="Run with a headless browser (default: true). Use --no-headless to show the browser UI.",
    )
    parser.add_argument(
        "-t",
        "--test",
        dest="test",
        action="store_true",
        default=False,
        required=False,
        help="If set, run test-run on the test data. This does not actually connect to wbm.de.",
    )
    parser.add_argument(
        "-d",
        "--delay",
        dest="application_delay",
        default="10s",
        required=False,
        help="Set the delay between applications (e.g. 10s, 30s, 1m, 5m).",
    )
    parser.add_argument(
        "--run-once",
        dest="run_once",
        action="store_true",
        default=False,
        required=False,
        help="Process listings once and exit (cron-friendly).",
    )
    parser.add_argument(
        "--exit-on-last-page",
        dest="exit_on_last_page",
        action=argparse.BooleanOptionalAction,
        default=True,
        required=False,
        help=(
            "Exit immediately after the last page is reached (default: true). "
            "Use --no-exit-on-last-page to keep running."
        ),
    )
    parser.add_argument(
        "--applications-store",
        dest="applications_store",
        choices=["file", "firestore"],
        default=default_app_store,
        required=False,
        help="Where to persist submitted applications (default: file). Can also set APPLICATIONS_STORE.",
    )
    parser.add_argument(
        "--config-store",
        dest="config_store",
        choices=["file", "firestore"],
        default=default_config_store,
        required=False,
        help="Where to load the WBM config from (default: file). Can also set CONFIG_STORE.",
    )
    parser.add_argument(
        "--config-key",
        dest="config_key",
        default=os.environ.get("WBM_USER_ID"),
        required=False,
        help="Firestore document key for the WBM config (or set WBM_USER_ID).",
    )
    parser.add_argument(
        "--firestore-project-id",
        dest="firestore_project_id",
        default=None,
        required=False,
        help="Firestore project ID (overrides FIRESTORE_PROJECT_ID).",
    )
    parser.add_argument(
        "--firestore-collection",
        dest="firestore_collection",
        default=None,
        required=False,
        help="Firestore collection name (overrides FIRESTORE_COLLECTION).",
    )
    parser.add_argument(
        "--firestore-config-collection",
        dest="firestore_config_collection",
        default=None,
        required=False,
        help="Firestore collection for WBM configs (overrides FIRESTORE_CONFIG_COLLECTION).",
    )
    parser.add_argument(
        "--firestore-credentials",
        dest="firestore_credentials",
        default=None,
        required=False,
        help="Path to a Google service account JSON key file.",
    )
    parser.add_argument(
        "--firestore-database",
        dest="firestore_database",
        default=None,
        required=False,
        help="Firestore database ID (overrides FIRESTORE_DATABASE).",
    )

    return parser.parse_args()


def main():
    """
    Initialize & starts the bot
    If the bot crashes, it will attempt to restart itself
    """

    args = parse_args()

    color_me = wbm_logger.ColoredLogger(__appname__)
    LOG = color_me.create_logger()

    application_delay_seconds = misc_operations.parse_delay_to_seconds(
        args.application_delay, default_seconds=10
    )

    # Show Intro Banner
    LOG.info(color_me.cyan(f"{constants.intro_banner}"))

    # Create ChromeDriver
    LOG.info(
        color_me.cyan(
            "Initializing Script "
            f"(v{constants.bot_version}) "
            f"(Headless? {args.headless}) "
            f"(Run-once? {args.run_once}) "
            f"(Exit-on-last-page? {args.exit_on_last_page}) "
            f"(Applications store: {args.applications_store}) "
            f"(Config store: {args.config_store}) 🚀"
        )
    )
    LOG.info(color_me.cyan("Checking for internet connection 🔎"))
    while True:
        if not misc_operations.check_internet_connection():
            LOG.error(
                color_me.red("No internet connection found. Retrying in 10 seconds ⚠️")
            )
            time.sleep(10)
        else:
            LOG.info(color_me.green("Online 🟢"))
            break

    LOG.info(
        color_me.cyan(
            f"Delay between applications set to {application_delay_seconds} seconds ⏱️"
        )
    )

    config_store = build_config_store(
        args.config_store,
        constants.wbm_config_name if not args.test else constants.wbm_test_config_name,
        allow_prompt=not args.run_once,
        project_id=args.firestore_project_id or os.environ.get("FIRESTORE_PROJECT_ID"),
        collection=args.firestore_config_collection
        or os.environ.get("FIRESTORE_CONFIG_COLLECTION"),
        credentials_path=args.firestore_credentials
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        database=args.firestore_database or os.environ.get("FIRESTORE_DATABASE"),
    )
    config_store.initialize()
    config_key = args.config_key or os.environ.get("WBM_USER_ID")
    if args.config_store == "firestore" and not config_key:
        LOG.error(
            color_me.red(
                "Firestore config store requires a config key. "
                "Use --config-key or set WBM_USER_ID."
            )
        )
        raise SystemExit(2)
    wbm_config = config_store.load_config(config_key)
    if not wbm_config:
        LOG.error(color_me.red("Failed to load WBM config ❌"))
        raise SystemExit(2)
    # Create User Profile
    user_profile = user.User(wbm_config)
    application_store = build_application_store(
        args.applications_store,
        constants.log_file_path,
        project_id=args.firestore_project_id or os.environ.get("FIRESTORE_PROJECT_ID"),
        collection=args.firestore_collection or os.environ.get("FIRESTORE_COLLECTION"),
        credentials_path=args.firestore_credentials
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        database=args.firestore_database or os.environ.get("FIRESTORE_DATABASE"),
    )
    application_store.initialize()
    # Get URL
    start_url = constants.wbm_url if not args.test else constants.test_wbm_url

    ###### Start the magic ######
    current_page = 1
    previous_page = 1
    page_changed = False
    LOG.info(color_me.cyan(f"Connecting to '{start_url}' 🔗"))

    while True:
        chrome_driver_instance = cdc.ChromeDriverConfigurator(args.headless, args.test)
        web_driver = chrome_driver_instance.get_driver()
        try:
            webDriverOperations.process_flats(
                web_driver,
                user_profile,
                start_url,
                current_page,
                previous_page,
                page_changed,
                args.interval,
                args.test,
                application_delay_seconds,
                args.run_once,
                args.exit_on_last_page,
                application_store,
            )
            if args.run_once or args.exit_on_last_page:
                break
        except Exception as e:
            LOG.error(
                color_me.red(f"Bot has crashed... Attempting to restart it now! ❤️‍🩹")
            )
            LOG.error(color_me.red(f"Crash reason: {e}"))
            if args.run_once:
                raise
            # Wait for a few seconds before restarting
            time.sleep(5)
        finally:
            try:
                web_driver.quit()
            except Exception:
                pass


# * Script Starts Here
if __name__ == "__main__":
    main()
