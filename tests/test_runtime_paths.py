import datetime as dt
from pathlib import Path

from wbmbot_v3.helpers import constants


def test_build_runtime_paths_uses_single_run_timestamp(tmp_path: Path):
    paths = constants.build_runtime_paths(
        base_dir=tmp_path,
        now=dt.datetime(2026, 4, 10, 12, 34),
    )

    assert paths.base_dir == str(tmp_path.resolve())
    assert paths.run_date == dt.date(2026, 4, 10)
    assert paths.run_label == "2026-04-10_12-34"
    assert paths.wbm_config_name.endswith("configs/wbm_config.json")
    assert paths.debug_dump_path.endswith("logging/debug/2026-04-10_12-34")
    assert paths.debug_log_path.endswith(
        "logging/debug/2026-04-10_12-34/wbmbot-debug.log"
    )
    assert paths.test_wbm_url.endswith("/test-data/angebote.html")
