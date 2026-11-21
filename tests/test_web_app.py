from datetime import date
from pathlib import Path

import pytest

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from basketball_tracker.models import ShootingSession
from basketball_tracker.settings import load_settings, set_default_player
from basketball_tracker.storage import append_session, read_sessions


WEB_APP_PATH = str(Path(__file__).resolve().parents[1] / "basketball_tracker" / "web_app.py")


def _run_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv("BASKETBALL_TRACKER_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("BASKETBALL_TRACKER_DATA_FILE", str(tmp_path / "sessions.csv"))
    at = AppTest.from_file(WEB_APP_PATH, default_timeout=15)
    at.run()
    assert not at.exception
    return at


def _metrics_by_label(at: AppTest) -> dict[str, str]:
    return {metric.label: str(metric.value) for metric in at.metric}


def test_read_only_startup_creates_no_files(tmp_path, monkeypatch):
    at = _run_app(tmp_path, monkeypatch)
    assert list(tmp_path.iterdir()) == []
    metrics = _metrics_by_label(at)
    assert metrics == {
        "Sessions": "0",
        "Overall": "N/A",
        "Free Throws": "N/A",
        "Two-Pointers": "N/A",
        "Three-Pointers": "N/A",
    }
    assert any("No default player" in info.value for info in at.info)
    assert any('data-zone="free-throws"' in md.value for md in at.markdown)


def test_save_default_and_record_session_and_override(tmp_path, monkeypatch):
    at = _run_app(tmp_path, monkeypatch)

    # Save default player via sidebar form.
    at.sidebar.text_input(key="default_player_input").set_value("Ray")
    at.sidebar.button[0].click().run()
    assert not at.exception
    assert load_settings(tmp_path / "settings.json")["default_player"] == "Ray"
    assert not (tmp_path / "sessions.csv").exists()

    # Record a session for default player Ray.
    at.date_input(key="add_session_date").set_value(date(2020, 1, 2))
    at.number_input(key="ft_makes").set_value(8)
    at.number_input(key="ft_attempts").set_value(10)
    at.number_input(key="two_makes").set_value(12)
    at.number_input(key="two_attempts").set_value(20)
    at.number_input(key="three_makes").set_value(5)
    at.number_input(key="three_attempts").set_value(15)
    at.main.button[0].click().run()
    assert not at.exception

    metrics = _metrics_by_label(at)
    assert metrics["Sessions"] == "1"
    assert metrics["Overall"] == "55.6%"
    assert metrics["Free Throws"] == "80.0%"
    assert metrics["Two-Pointers"] == "60.0%"
    assert metrics["Three-Pointers"] == "33.3%"
    assert any("80.0%" in md.value and "60.0%" in md.value and "33.3%" in md.value for md in at.markdown)

    # Record another session with one-off player override without changing settings.json.
    before_settings = (tmp_path / "settings.json").read_bytes()
    at.date_input(key="add_session_date").set_value(date(2020, 1, 3))
    at.text_input(key="add_session_player").set_value("Jordan")
    at.number_input(key="ft_makes").set_value(9)
    at.number_input(key="ft_attempts").set_value(10)
    at.number_input(key="two_makes").set_value(0)
    at.number_input(key="two_attempts").set_value(0)
    at.number_input(key="three_makes").set_value(0)
    at.number_input(key="three_attempts").set_value(0)
    at.main.button[0].click().run()
    assert not at.exception
    assert (tmp_path / "settings.json").read_bytes() == before_settings
    assert len(read_sessions(tmp_path / "sessions.csv")) == 2


def test_invalid_session_submission_leaves_csv_unchanged(tmp_path, monkeypatch):
    set_default_player(tmp_path / "settings.json", "Ray")
    append_session(tmp_path / "sessions.csv", ShootingSession(date(2020, 1, 2), "Ray", 8, 10, 0, 0, 0, 0))
    before = (tmp_path / "sessions.csv").read_bytes()

    at = _run_app(tmp_path, monkeypatch)
    at.number_input(key="ft_makes").set_value(5)
    at.number_input(key="ft_attempts").set_value(3)
    at.main.button[0].click().run()
    assert not at.exception
    assert any("makes cannot exceed attempts" in err.value for err in at.error)
    assert (tmp_path / "sessions.csv").read_bytes() == before


def test_scope_and_date_range_filters_update_dashboard_dynamically(tmp_path, monkeypatch):
    set_default_player(tmp_path / "settings.json", "Ray")
    append_session(tmp_path / "sessions.csv", ShootingSession(date(2020, 1, 1), "Ray", 10, 10, 0, 0, 0, 0))
    append_session(tmp_path / "sessions.csv", ShootingSession(date(2020, 1, 10), "Ray", 0, 10, 0, 0, 0, 0))
    append_session(tmp_path / "sessions.csv", ShootingSession(date(2020, 1, 10), "Jordan", 5, 10, 0, 0, 0, 0))

    at = _run_app(tmp_path, monkeypatch)
    assert _metrics_by_label(at)["Sessions"] == "2"
    assert _metrics_by_label(at)["Overall"] == "50.0%"

    # Switch to All players (combined).
    at.sidebar.radio(key="scope_mode").set_value("all").run()
    assert not at.exception
    assert _metrics_by_label(at)["Sessions"] == "3"
    assert _metrics_by_label(at)["Overall"] == "50.0%"

    # Apply custom date range filtering down to 2020-01-10 only.
    at.sidebar.selectbox(key="date_range_preset").set_value("Custom range").run()
    at.sidebar.date_input(key="custom_start_date").set_value(date(2020, 1, 10))
    at.sidebar.date_input(key="custom_end_date").set_value(date(2020, 1, 10))
    at.run()
    assert not at.exception
    assert _metrics_by_label(at)["Sessions"] == "2"
    assert _metrics_by_label(at)["Overall"] == "25.0%"

    # Invalid custom range (start > end) reports error cleanly.
    at.sidebar.date_input(key="custom_start_date").set_value(date(2020, 1, 12))
    at.sidebar.date_input(key="custom_end_date").set_value(date(2020, 1, 10))
    at.run()
    assert not at.exception
    assert any("Start date cannot be after end date" in err.value for err in at.error)
    assert _metrics_by_label(at)["Sessions"] == "0"


def test_corrupt_files_show_errors_without_overwriting(tmp_path, monkeypatch):
    (tmp_path / "settings.json").write_text("{", encoding="utf-8")
    (tmp_path / "sessions.csv").write_text("bad,header\n", encoding="utf-8")

    at = _run_app(tmp_path, monkeypatch)
    error_messages = [err.value for err in at.error]
    assert any("Invalid settings" in msg for msg in error_messages)
    assert any("Invalid CSV" in msg for msg in error_messages)
    assert (tmp_path / "settings.json").read_text(encoding="utf-8") == "{"
    assert (tmp_path / "sessions.csv").read_text(encoding="utf-8") == "bad,header\n"
