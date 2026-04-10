import os
import time

from selenium.webdriver.common.by import By

from wbmbot_v3.handlers import flat
from wbmbot_v3.helpers import browser_actions, constants, debug_artifacts, notifications
from wbmbot_v3.httpsWrapper import httpPageDownloader as hpd
from wbmbot_v3.logger import wbm_logger
from wbmbot_v3.utility import eligibility, misc_operations

__appname__ = os.path.splitext(os.path.basename(__file__))[0]
color_me = wbm_logger.ColoredLogger(__appname__)
LOG = color_me.create_logger()


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
    runtime_paths: constants.RuntimePaths | None = None,
):
    """
    Apply to the flat using the provided user profile and email.
    """

    flat_link = browser_actions.ansehen_btn(web_driver, flat_element, flat_index)
    if not flat_link:
        return False
    if "seniorenwohnungen" in flat_link:
        return False
    if debug_dir:
        debug_artifacts._debug_dump_page(
            web_driver,
            debug_dir,
            f"details_loaded_{flat_title}",
        )

    browser_actions.fill_form(web_driver, user_profile, email, test)

    pdf_path = None
    if not test and debug_dir:
        try:
            pdf_path = debug_artifacts.download_expose_as_pdf(
                web_driver,
                flat_title,
                runtime_paths=runtime_paths,
                debug_dir=debug_dir,
            )
        except Exception as exc:
            LOG.warning(
                color_me.yellow(
                    f"Expose download failed for '{flat_title}': {exc}. Continuing without PDF. 🚧"
                )
            )

    if not test:
        web_driver.find_element(By.XPATH, "//button[@type='submit']").click()

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
    runtime_paths: constants.RuntimePaths | None = None,
):
    """
    Process each flat by checking criteria and applying if applicable.
    """

    runtime_paths = runtime_paths or constants.build_runtime_paths()

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
            current_page, previous_page = browser_actions.reset_to_start_page(
                web_driver,
                start_url,
                current_page,
                previous_page,
            )

        browser_actions.accept_cookies(web_driver)
        browser_actions.close_live_chat_button(web_driver)

        LOG.info(color_me.cyan("Looking for flats 👀"))
        all_flats = browser_actions.find_flats(web_driver)
        if not all_flats:
            LOG.info(color_me.cyan("Currently no flats available 😔"))
            if run_once:
                LOG.info(color_me.cyan("Run-once mode enabled; exiting."))
                return
            time.sleep(int(refresh_internal) * 60)
            continue

        LOG.info(color_me.green(f"Found {len(all_flats)} flat(s) in total 💡"))

        if not test:
            snapshot_path = os.path.join(
                runtime_paths.offline_angebote_path,
                runtime_paths.run_label,
                f"page_{current_page}.html",
            )
            hpd.save_rendered_page(web_driver.page_source, snapshot_path)
            LOG.info(
                color_me.cyan(
                    f"Saved HTML snapshot for page {current_page} at {snapshot_path} 💾"
                )
            )
        if debug_dir:
            debug_artifacts._debug_dump_page(
                web_driver,
                debug_dir,
                f"list_page_{current_page}",
            )

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
            time.sleep(2)

            all_flats = browser_actions.find_flats(web_driver)
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
                    if application_store is None:
                        raise RuntimeError("Application store is not configured.")

                    if application_store.has_applied(email, flat_obj):
                        LOG.warning(
                            color_me.yellow(
                                f"Oops, we already applied for flat: {flat_obj.title} 🚫"
                            )
                        )
                        continue

                    is_eligible, reason = eligibility.evaluate_flat_eligibility(
                        flat_elem,
                        flat_obj,
                        user_profile,
                    )
                    if not is_eligible:
                        LOG.warning(
                            color_me.yellow(
                                f"Ignoring flat '{flat_obj.title}' because {reason} 🙈"
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
                        runtime_paths=runtime_paths,
                    )
                    if applied:
                        LOG.info(
                            color_me.cyan(
                                f"Applying to flat: {flat_obj.title} for '{email}' 📩"
                            )
                        )
                        application_store.record_application(email, flat_obj)
                        LOG.info(color_me.green("Done ✅"))
                        debug_artifacts.wait_before_next_application(
                            application_delay_seconds
                        )
                        web_driver.get(start_url)
                        time.sleep(1.5)
                        restart_processing = True
                        break

                    LOG.warning(
                        color_me.yellow(
                            f"Ignoring flat: {flat_obj.title} because it is for Seniors only ('seniorenwohnungen') 🙈"
                        )
                    )

                if restart_processing:
                    break

            if restart_processing:
                break

            if position == len(sorted_entries) - 1:
                previous_page = current_page
                try:
                    current_page = browser_actions.next_page(
                        web_driver,
                        current_page,
                        terminate_on_last_page=run_once or exit_on_last_page,
                    )
                except browser_actions.LastPageReached:
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
