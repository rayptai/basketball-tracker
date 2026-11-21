from dataclasses import replace
from datetime import date

import pytest

from basketball_tracker.models import (
    ShotTotals, aggregate_sessions, format_percentage, overall_shot_totals,
    parse_session_date, shooting_percentage, validate_player_name,
)


def test_percentages_and_weighted_aggregation(session):
    small = replace(session, free_throw_makes=1, free_throw_attempts=1)
    large = replace(session, free_throw_makes=0, free_throw_attempts=9)
    totals = aggregate_sessions([small, large])
    assert totals["Free throws"].makes == 1
    assert totals["Free throws"].attempts == 10
    assert totals["Free throws"].percentage == 10
    assert shooting_percentage(1, 3) == pytest.approx(100 / 3)
    assert shooting_percentage(0, 0) is None
    assert format_percentage(None) == "N/A"
    assert format_percentage(100 / 3) == "33.3%"
    assert format_percentage(80.0) == "80.0%"
    assert all(total.percentage is None for total in aggregate_sessions([]).values())


def test_overall_shot_totals_is_weighted():
    totals = {
        "Free throws": ShotTotals(1, 1),       # 100%
        "Two-pointers": ShotTotals(0, 9),      # 0%
        "Three-pointers": ShotTotals(0, 0),    # N/A
    }
    overall = overall_shot_totals(totals)
    assert overall == ShotTotals(1, 10)
    assert overall.percentage == pytest.approx(10.0)
    assert overall_shot_totals(aggregate_sessions([])) == ShotTotals(0, 0)
    assert overall_shot_totals(aggregate_sessions([])).percentage is None


@pytest.mark.parametrize("changes", [
    {"free_throw_makes": -1}, {"two_point_attempts": -1},
    {"three_point_makes": 16}, {"free_throw_attempts": 0},
    {"free_throw_makes": 1.5}, {"two_point_attempts": True},
    {"three_point_makes": "2"}, {"date": date.max}, {"date": "2020-01-02"},
    {"free_throw_makes": 0, "free_throw_attempts": 0, "two_point_makes": 0,
     "two_point_attempts": 0, "three_point_makes": 0, "three_point_attempts": 0},
])
def test_invalid_session(session, changes):
    with pytest.raises(ValueError):
        replace(session, **changes)


def test_unpracticed_category_is_allowed(session):
    result = replace(session, free_throw_makes=0, free_throw_attempts=0)
    assert result.shot_totals()["Free throws"].percentage is None


@pytest.mark.parametrize("name", ["", "  ", "Ray\n", "\rRay", "A\nB", "A\u2028B", None, 123])
def test_invalid_player_names(name):
    with pytest.raises(ValueError):
        validate_player_name(name)


def test_name_normalization(session):
    assert replace(session, player_name="  Zoë, Jr.  ").player_name == "Zoë, Jr."
    assert validate_player_name("ray") != validate_player_name("Ray")


@pytest.mark.parametrize("value", ["20200102", "2020-1-02", "2020-01-2", "2020-02-30", " 2020-01-02", "0000-01-01"])
def test_invalid_date_format(value):
    with pytest.raises(ValueError):
        parse_session_date(value)


def test_leap_day():
    assert parse_session_date("2020-02-29") == date(2020, 2, 29)
