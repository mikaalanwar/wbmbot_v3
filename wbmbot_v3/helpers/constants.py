import datetime as dt
import os
from dataclasses import dataclass
from pathlib import Path

bot_version = "1.1.4"
wbm_url = "https://www.wbm.de/wohnungen-berlin/angebote/"


@dataclass(frozen=True)
class RuntimePaths:
    base_dir: str
    run_date: dt.date
    run_label: str
    wbm_config_name: str
    wbm_test_config_name: str
    log_file_path: str
    script_log_path: str
    debug_dump_root: str
    debug_dump_path: str
    debug_html_path: str
    debug_screenshot_path: str
    debug_log_path: str
    offline_angebote_path: str
    offline_apartment_path: str
    test_wbm_url: str


def build_runtime_paths(
    base_dir: str | os.PathLike[str] | None = None,
    now: dt.datetime | None = None,
) -> RuntimePaths:
    """
    Build the per-run filesystem paths rooted at the current working directory.
    """

    resolved_now = now or dt.datetime.now()
    root_path = Path(base_dir or os.getcwd()).resolve()
    run_label = resolved_now.strftime("%Y-%m-%d_%H-%M")
    run_date = resolved_now.date()
    debug_dump_root = root_path / "logging" / "debug"
    debug_dump_path = debug_dump_root / run_label

    return RuntimePaths(
        base_dir=str(root_path),
        run_date=run_date,
        run_label=run_label,
        wbm_config_name=str(root_path / "configs" / "wbm_config.json"),
        wbm_test_config_name=str(root_path / "test-data" / "wbm_test_config.json"),
        log_file_path=str(root_path / "logging" / "successful_applications.json"),
        script_log_path=str(root_path / "logging" / f"wbmbot-v2_{run_date}.log"),
        debug_dump_root=str(debug_dump_root),
        debug_dump_path=str(debug_dump_path),
        debug_html_path=str(debug_dump_path / "html"),
        debug_screenshot_path=str(debug_dump_path / "screenshots"),
        debug_log_path=str(debug_dump_path / "wbmbot-debug.log"),
        offline_angebote_path=str(root_path / "offline_viewings" / "angebote_pages"),
        offline_apartment_path=str(
            root_path / "offline_viewings" / "apartments_expose_pdfs"
        ),
        test_wbm_url=(root_path / "test-data" / "angebote.html").as_uri(),
    )


def current_date() -> dt.date:
    return dt.date.today()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def get_email_password() -> str | None:
    return os.environ.get("EMAIL_PASSWORD")

intro_banner = r"""
 __      _____ __  __ ___  ___ _____       ___
 \ \    / / _ )  \/  | _ )/ _ \_   _| __ _|_  )
  \ \/\/ /| _ \ |\/| | _ \ (_) || |   \ V // /
   \_/\_/ |___/_|  |_|___/\___/ |_|    \_//___|
  _          __   __   _
 | |__ _  _  \ \ / /__| |
 | '_ \ || |  \ V / -_) |
 |_.__/\_, |   \_/\___|_|
       |__/
"""
