from datetime import date

import pytest

from basketball_tracker.dashboard import (
    DATE_PRESET_7,
    DATE_PRESET_30,
    DATE_PRESET_90,
    DATE_PRESET_ALL,
    DATE_PRESET_CUSTOM,
    SCOPE_ALL,
    SCOPE_DEFAULT,
    SCOPE_PLAYER,
    build_history_rows,
    build_trend_points,
    filter_sessions,
    known_players,
    load_dashboard_state,
    record_session,
    resolve_date_range,
    resolve_player_scope,
    summarize_sessions,
    update_default_player,
)
from basketball_tracker.models import ShootingSession


def test_load_dashboard_state_missing_files_does_not_create_anything(tmp_path):
    settings_path = tmp_path / "settings.json"
    data_path = tmp_path / "sessions.csv"
    state = load_dashboard_state(settings_path, data_path)
    assert state.default_player is None
    assert state.sessions == ()
    assert not state.has_errors
    assert list(tmp_path.iterdir()) == []


def test_load_dashboard_state_isolates_corrupt_files(tmp_path):
    settings_path = tmp_path / "settings.json"
    data_path = tmp_path / "sessions.csv"
    settings_path.write_text("{bad", encoding="utf-8")
    data_path.write_text("bad,header\n", encoding="utf-8")
    state = load_dashboard_state(settings_path, data_path)
    assert state.has_errors
    assert state.settings_error is not None and "Invalid settings" in state.settings_error
    assert state.sessions_error is not None and "Invalid CSV" in state.sessions_error


def test_known_players_preserves_case_and_includes_default():
    sessions = [
        ShootingSession(date(2020, 1, 1), "ray", 1, 2, 0, 0, 0, 0),
        ShootingSession(date(2020, 1, 2), "Zoë, Jr.", 1, 2, 0, 0, 0, 0),
        ShootingSession(date(2020, 1, 3), "Ray", 1, 2, 0, 0, 0, 0),
    ]
    assert known_players(sessions, default_player="Jordan") == ["Jordan", "Ray", "ray", "Zoë, Jr."]


def test_resolve_player_scope_precedence_and_validation():
    unconfigured = resolve_player_scope(SCOPE_DEFAULT, default_player=None)
    assert not unconfigured.is_ready
    assert unconfigured.notice is not None and "No default player" in unconfigured.notice

    default_scope = resolve_player_scope(SCOPE_DEFAULT, default_player="Ray")
    assert default_scope.is_ready and default_scope.player_name == "Ray"

    specific = resolve_player_scope(SCOPE_PLAYER, default_player="Ray", selected_player="  Jordan  ")
    assert specific.is_ready and specific.player_name == "Jordan"

    bad_specific = resolve_player_scope(SCOPE_PLAYER, default_player="Ray", selected_player="A\nB")
    assert not bad_specific.is_ready and bad_specific.notice is not None

    all_scope = resolve_player_scope(SCOPE_ALL, default_player="Ray")
    assert all_scope.is_ready and all_scope.player_name is None
    assert "combined" in all_scope.label.lower()


def test_resolve_date_range_presets_and_validation():
    today = date(2026, 11, 20)
    assert resolve_date_range(DATE_PRESET_ALL, today=today).start is None
    last7 = resolve_date_range(DATE_PRESET_7, today=today)
    assert (last7.start, last7.end) == (date(2026, 11, 14), today)
    last30 = resolve_date_range(DATE_PRESET_30, today=today)
    assert (last30.start, last30.end) == (date(2026, 10, 22), today)
    last90 = resolve_date_range(DATE_PRESET_90, today=today)
    assert (last90.start, last90.end) == (date(2026, 8, 23), today)

    custom = resolve_date_range(
        DATE_PRESET_CUSTOM,
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 10),
        today=today,
    )
    assert custom.label == "2026-11-01 to 2026-11-10"

    with pytest.raises(ValueError, match="Start date cannot be after end date"):
        resolve_date_range(
            DATE_PRESET_CUSTOM,
            start_date=date(2026, 11, 15),
            end_date=date(2026, 11, 10),
            today=today,
        )


def test_filter_sessions_inclusive_bounds_and_newest_first():
    sessions = [
        ShootingSession(date(2020, 1, 1), "Ray", 5, 10, 0, 0, 0, 0),
        ShootingSession(date(2020, 1, 5), "Ray", 8, 10, 0, 0, 0, 0),
        ShootingSession(date(2020, 1, 5), "ray", 9, 10, 0, 0, 0, 0),
        ShootingSession(date(2020, 1, 10), "Ray", 7, 10, 0, 0, 0, 0),
    ]
    scope = resolve_player_scope(SCOPE_PLAYER, default_player=None, selected_player="Ray")
    date_range = resolve_date_range(
        DATE_PRESET_CUSTOM,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 5),
    )
    filtered = filter_sessions(sessions, scope, date_range)
    assert [s.date for s in filtered] == [date(2020, 1, 5), date(2020, 1, 1)]
    assert all(s.player_name == "Ray" for s in filtered)


def test_summarize_sessions_and_weighted_daily_trend_points():
    sessions = [
        # Two sessions on 2020-01-02: FT 1/1 + 0/9 = 1/10 (10.0%), 2PT 0/0 (omitted), 3PT 3/6 (50.0%)
        ShootingSession(date(2020, 1, 2), "Ray", 1, 1, 0, 0, 0, 0),
        ShootingSession(date(2020, 1, 2), "Ray", 0, 9, 0, 0, 3, 6),
        # Earlier date 2020-01-01 to verify chronological sorting
        ShootingSession(date(2020, 1, 1), "Ray", 8, 10, 10, 20, 0, 0),
    ]
    category_totals, overall = summarize_sessions(sessions)
    assert category_totals["Free throws"].makes == 9
    assert category_totals["Free throws"].attempts == 20
    assert overall.makes == 22
    assert overall.attempts == 46
    assert overall.percentage == pytest.approx(100 * 22 / 46)

    points = build_trend_points(sessions)
    dates = [point.session_date for point in points]
    assert dates == sorted(dates)

    day2 = {point.category: point for point in points if point.session_date == date(2020, 1, 2)}
    assert "Two-pointers" not in day2  # Zero attempts omitted, never plotted as 0.0%
    assert day2["Free throws"].percentage == pytest.approx(10.0)
    assert day2["Free throws"].makes_attempts_label == "1/10"
    assert day2["Free throws"].session_count == 2
    assert day2["Three-pointers"].percentage == pytest.approx(50.0)
    assert day2["Overall"].makes == 4
    assert day2["Overall"].attempts == 16
    assert day2["Overall"].percentage == pytest.approx(25.0)


def test_build_history_rows_formatting():
    sessions = [
        ShootingSession(date(2020, 1, 1), "Ray", 1, 3, 0, 0, 5, 10),
        ShootingSession(date(2020, 1, 2), "Jordan", 8, 10, 12, 20, 0, 0),
    ]
    rows = build_history_rows(sessions)
    assert [row["Date"] for row in rows] == ["2020-01-02", "2020-01-01"]
    assert rows[0]["Three-Pointers"] == "0/0 (N/A)"
    assert rows[1]["Free Throws"] == "1/3 (33.3%)"


def test_write_helpers_delegate_validation_and_persistence(tmp_path):
    settings_path = tmp_path / "settings.json"
    data_path = tmp_path / "sessions.csv"
    assert update_default_player(settings_path, "  Ray  ") == "Ray"
    saved = record_session(
        data_path,
        session_date=date(2020, 1, 2),
        player_name="Jordan",
        free_throw_makes=8,
        free_throw_attempts=10,
        two_point_makes=0,
        two_point_attempts=0,
        three_point_makes=5,
        three_point_attempts=15,
    )
    assert saved.player_name == "Jordan"
    state = load_dashboard_state(settings_path, data_path)
    assert state.default_player == "Ray"  # Per-session override did not change default
    assert len(state.sessions) == 1
