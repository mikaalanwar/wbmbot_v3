import argparse
import os
import time
from typing import Sequence

from wbmbot_v3.chromeDriver import chrome_driver_configurator as cdc
from wbmbot_v3.handlers import user
from wbmbot_v3.helpers import constants, webDriverOperations
from wbmbot_v3.logger import wbm_logger
from wbmbot_v3.utility import io_operations, misc_operations
from wbmbot_v3.utility.application_store import (
    CompositeApplicationStore,
    FirestoreApplicationStore,
    build_application_store,
)
from wbmbot_v3.utility.config_store import build_config_store

__appname__ = os.path.splitext(os.path.basename(__file__))[0]


def _env_choice(name: str, allowed: set[str], fallback: str) -> str:
    value = os.environ.get(name)
    if value and value.strip().lower() in allowed:
        return value.strip().lower()
    return fallback


def _env_bool(name: str, fallback: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def build_parser() -> argparse.ArgumentParser:
    """
    Parse the command line arguments
    """

    default_app_store = _env_choice(
        "APPLICATIONS_STORE", {"file", "firestore"}, "file"
    )
    default_config_store = _env_choice("CONFIG_STORE", {"file", "firestore"}, "file")
    default_debug = _env_bool("WBM_DEBUG", False)

    parser = argparse.ArgumentParser(
        prog="python -m wbmbot_v3",
        description="A Selenium-based bot that scrapes 'WBM Angebote' page and auto applies on appartments based on user exclusion filters",
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
    parser.add_argument(
        "--debug",
        dest="debug",
        action=argparse.BooleanOptionalAction,
        default=default_debug,
        required=False,
        help="Enable debug logging and dump HTML/screenshot artifacts to disk.",
    )

    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """
    Initialize & starts the bot
    If the bot crashes, it will attempt to restart itself
    """

    os.environ.setdefault("WDM_LOG", "0")
    wbm_logger.configure_logging()

    args = parse_args(argv)
    runtime_paths = constants.build_runtime_paths()

    color_me = wbm_logger.ColoredLogger(__appname__)
    LOG = color_me.create_logger()

    application_delay_seconds = misc_operations.parse_delay_to_seconds(
        args.application_delay, default_seconds=10
    )

    # Show Intro Banner
    LOG.info(color_me.cyan(constants.intro_banner))

    # Create ChromeDriver
    LOG.info(
        color_me.cyan(
            "Initializing Script "
            f"(v{constants.bot_version}) "
            f"(Headless? {args.headless}) "
            f"(Run-once? {args.run_once}) "
            f"(Exit-on-last-page? {args.exit_on_last_page}) "
            f"(Applications store: {args.applications_store}) "
            f"(Config store: {args.config_store}) "
            f"(Debug? {args.debug}) 🚀"
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

    debug_dir = None
    if args.debug:
        debug_dir = runtime_paths.debug_dump_path
        io_operations.initialize_debug_logging(runtime_paths.debug_log_path)
        LOG.info(
            color_me.cyan(
                f"Debug mode enabled; dumps/logs will be stored in {debug_dir} 🧾"
            )
        )

    config_store = build_config_store(
        args.config_store,
        (
            runtime_paths.wbm_config_name
            if not args.test
            else runtime_paths.wbm_test_config_name
        ),
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
    if args.config_store == "firestore" and config_key:
        configs = [config_store.load_config(config_key)]
    else:
        configs = config_store.list_configs()

    configs = [cfg for cfg in configs if cfg]
    if not configs:
        LOG.error(color_me.red("Failed to load WBM config(s) ❌"))
        raise SystemExit(2)

    # Create User Profiles
    user_profiles = [user.User(cfg) for cfg in configs]
    application_store = build_application_store(
        args.applications_store,
        runtime_paths.log_file_path,
        project_id=args.firestore_project_id or os.environ.get("FIRESTORE_PROJECT_ID"),
        collection=args.firestore_collection or os.environ.get("FIRESTORE_COLLECTION"),
        credentials_path=args.firestore_credentials
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        database=args.firestore_database or os.environ.get("FIRESTORE_DATABASE"),
    )
    if os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true":
        audit_collection = os.environ.get(
            "FIRESTORE_GITHUB_ACTIONS_COLLECTION",
            "wbm_applications_github_actions",
        )
        audit_store = FirestoreApplicationStore(
            project_id=args.firestore_project_id
            or os.environ.get("FIRESTORE_PROJECT_ID"),
            collection=audit_collection,
            credentials_path=args.firestore_credentials
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
            database=args.firestore_database or os.environ.get("FIRESTORE_DATABASE"),
        )
        application_store = CompositeApplicationStore(
            [application_store, audit_store], label="primary+github-actions"
    )
    application_store.initialize()
    # Get URL
    start_url = constants.wbm_url if not args.test else runtime_paths.test_wbm_url

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
                user_profiles,
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
                debug_dir,
                runtime_paths=runtime_paths,
            )
            if args.run_once or args.exit_on_last_page:
                break
        except Exception as e:
            LOG.error(
                color_me.red("Bot has crashed... Attempting to restart it now! ❤️‍🩹")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
