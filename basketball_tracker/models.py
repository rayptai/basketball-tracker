"""Session validation and shooting calculations, independent of storage and CLI."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
import re


def validate_player_name(name: str) -> str:
    """Normalize a player name while preserving case and internal spacing."""
    if not isinstance(name, str):
        raise ValueError("Player name must be text.")
    if len(name.splitlines()) > 1 or any(char in name for char in "\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029"):
        raise ValueError("Player name must not contain line breaks.")
    name = name.strip()
    if not name:
        raise ValueError("Player name must not be empty.")
    return name


def parse_session_date(value: str) -> date:
    """Parse an exact ISO calendar date; session validation checks future dates."""
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Date must use YYYY-MM-DD (for example, 2026-11-17).")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Date must be a valid calendar date in YYYY-MM-DD format.") from error


def shooting_percentage(makes: int, attempts: int) -> float | None:
    """Return an unrounded percentage, or None for an unpracticed category."""
    return 100 * (makes / attempts) if attempts else None


def format_percentage(percentage: float | None) -> str:
    """Format a percentage to one decimal place, or N/A when attempts are zero."""
    return "N/A" if percentage is None else f"{percentage:.1f}%"


@dataclass(frozen=True)
class ShotTotals:
    makes: int = 0
    attempts: int = 0

    @property
    def percentage(self) -> float | None:
        return shooting_percentage(self.makes, self.attempts)


@dataclass(frozen=True)
class ShootingSession:
    date: date
    player_name: str
    free_throw_makes: int
    free_throw_attempts: int
    two_point_makes: int
    two_point_attempts: int
    three_point_makes: int
    three_point_attempts: int

    def __post_init__(self) -> None:
        if type(self.date) is not date:
            raise ValueError("Session date must be a calendar date.")
        if self.date > date.today():
            raise ValueError("Session date cannot be in the future.")
        object.__setattr__(self, "player_name", validate_player_name(self.player_name))
        for label, totals in self.shot_totals().items():
            if any(type(value) is not int or value < 0 for value in (totals.makes, totals.attempts)):
                raise ValueError(f"{label}: makes and attempts must be nonnegative integers.")
            if totals.makes > totals.attempts:
                raise ValueError(f"{label}: makes cannot exceed attempts.")
        if not any(totals.attempts for totals in self.shot_totals().values()):
            raise ValueError("A session must include at least one shot attempt.")

    def shot_totals(self) -> dict[str, ShotTotals]:
        return {
            "Free throws": ShotTotals(self.free_throw_makes, self.free_throw_attempts),
            "Two-pointers": ShotTotals(self.two_point_makes, self.two_point_attempts),
            "Three-pointers": ShotTotals(self.three_point_makes, self.three_point_attempts),
        }


def aggregate_sessions(sessions: Iterable[ShootingSession]) -> dict[str, ShotTotals]:
    """Sum counts before calculating percentages; never average percentages."""
    totals = {label: ShotTotals() for label in ("Free throws", "Two-pointers", "Three-pointers")}
    for session in sessions:
        for label, shots in session.shot_totals().items():
            previous = totals[label]
            totals[label] = ShotTotals(previous.makes + shots.makes, previous.attempts + shots.attempts)
    return totals


def overall_shot_totals(totals: Mapping[str, ShotTotals]) -> ShotTotals:
    """Combine makes and attempts across all categories before computing percentage."""
    return ShotTotals(
        sum(shots.makes for shots in totals.values()),
        sum(shots.attempts for shots in totals.values()),
    )
