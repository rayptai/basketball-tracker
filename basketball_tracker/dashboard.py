"""Pure-Python view-model, filtering, and trend helpers for the web dashboard."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from basketball_tracker.models import (
    ShootingSession,
    ShotTotals,
    aggregate_sessions,
    format_percentage,
    overall_shot_totals,
    validate_player_name,
)
from basketball_tracker.settings import load_settings, set_default_player
from basketball_tracker.storage import append_session, read_sessions


CATEGORY_LABELS = ("Free throws", "Two-pointers", "Three-pointers")
TREND_SERIES = ("Overall", *CATEGORY_LABELS)

SCOPE_DEFAULT = "default"
SCOPE_PLAYER = "player"
SCOPE_ALL = "all"

DATE_PRESET_ALL = "All dates"
DATE_PRESET_7 = "Last 7 days"
DATE_PRESET_30 = "Last 30 days"
DATE_PRESET_90 = "Last 90 days"
DATE_PRESET_CUSTOM = "Custom range"
DATE_PRESETS = (
    DATE_PRESET_ALL,
    DATE_PRESET_7,
    DATE_PRESET_30,
    DATE_PRESET_90,
    DATE_PRESET_CUSTOM,
)


@dataclass(frozen=True)
class DashboardState:
    """Snapshot of settings and sessions loaded without mutating or creating files."""

    default_player: str | None
    sessions: tuple[ShootingSession, ...]
    settings_error: str | None = None
    sessions_error: str | None = None

    @property
    def has_errors(self) -> bool:
        return self.settings_error is not None or self.sessions_error is not None


@dataclass(frozen=True)
class PlayerScope:
    """Resolved player selection mirroring CLI precedence and mutual exclusion."""

    mode: str
    player_name: str | None
    label: str
    is_ready: bool
    notice: str | None = None


@dataclass(frozen=True)
class DateRange:
    """Inclusive date filter applied across dashboard views."""

    start: date | None
    end: date | None
    label: str


@dataclass(frozen=True)
class TrendPoint:
    """One weighted daily shooting percentage point for a single shot series."""

    session_date: date
    date_label: str
    category: str
    makes: int
    attempts: int
    percentage: float
    percentage_label: str
    makes_attempts_label: str
    session_count: int


def load_dashboard_state(settings_path: Path, data_path: Path) -> DashboardState:
    """Safely load settings and sessions without creating files or raising tracebacks."""
    default_player: str | None = None
    settings_error: str | None = None
    try:
        settings = load_settings(settings_path)
        raw_default = settings.get("default_player")
        if isinstance(raw_default, str):
            default_player = raw_default
    except (ValueError, OSError) as error:
        settings_error = str(error)

    sessions: tuple[ShootingSession, ...] = ()
    sessions_error: str | None = None
    try:
        sessions = tuple(read_sessions(data_path))
    except (ValueError, OSError) as error:
        sessions_error = str(error)

    return DashboardState(
        default_player=default_player,
        sessions=sessions,
        settings_error=settings_error,
        sessions_error=sessions_error,
    )


def known_players(
    sessions: Iterable[ShootingSession],
    default_player: str | None = None,
) -> list[str]:
    """Return distinct case-sensitive player names sorted deterministically."""
    players = {session.player_name for session in sessions}
    if default_player is not None:
        players.add(default_player)
    return sorted(players, key=lambda name: (name.casefold(), name))


def resolve_player_scope(
    mode: str,
    *,
    default_player: str | None,
    selected_player: str | None = None,
) -> PlayerScope:
    """Resolve UI scope selection into a concrete player filter and clear label."""
    if mode == SCOPE_ALL:
        return PlayerScope(
            mode=SCOPE_ALL,
            player_name=None,
            label="All players (combined)",
            is_ready=True,
        )
    if mode == SCOPE_DEFAULT:
        if default_player is not None:
            return PlayerScope(
                mode=SCOPE_DEFAULT,
                player_name=default_player,
                label=default_player,
                is_ready=True,
            )
        return PlayerScope(
            mode=SCOPE_DEFAULT,
            player_name=None,
            label="No player selected",
            is_ready=False,
            notice=(
                "No default player is configured. Choose a specific player, switch to "
                "All players (combined), or save a default player in the sidebar."
            ),
        )
    if mode == SCOPE_PLAYER:
        if selected_player is None or not selected_player.strip():
            return PlayerScope(
                mode=SCOPE_PLAYER,
                player_name=None,
                label="No player selected",
                is_ready=False,
                notice="Select or enter a player name to view their statistics.",
            )
        try:
            normalized = validate_player_name(selected_player)
        except ValueError as error:
            return PlayerScope(
                mode=SCOPE_PLAYER,
                player_name=None,
                label="Invalid player name",
                is_ready=False,
                notice=str(error),
            )
        return PlayerScope(
            mode=SCOPE_PLAYER,
            player_name=normalized,
            label=normalized,
            is_ready=True,
        )
    raise ValueError(f"Unsupported scope mode: {mode}")


def resolve_date_range(
    preset: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    today: date | None = None,
) -> DateRange:
    """Resolve a preset or custom inclusive date range."""
    reference_today = today if today is not None else date.today()
    if preset == DATE_PRESET_ALL:
        return DateRange(start=None, end=None, label=DATE_PRESET_ALL)
    if preset == DATE_PRESET_7:
        start = reference_today - timedelta(days=6)
        return DateRange(start=start, end=reference_today, label=f"{start.isoformat()} to {reference_today.isoformat()}")
    if preset == DATE_PRESET_30:
        start = reference_today - timedelta(days=29)
        return DateRange(start=start, end=reference_today, label=f"{start.isoformat()} to {reference_today.isoformat()}")
    if preset == DATE_PRESET_90:
        start = reference_today - timedelta(days=89)
        return DateRange(start=start, end=reference_today, label=f"{start.isoformat()} to {reference_today.isoformat()}")
    if preset == DATE_PRESET_CUSTOM:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("Start date cannot be after end date.")
        if start_date is None and end_date is None:
            return DateRange(start=None, end=None, label=DATE_PRESET_ALL)
        if start_date is not None and end_date is not None:
            label = f"{start_date.isoformat()} to {end_date.isoformat()}"
        elif start_date is not None:
            label = f"From {start_date.isoformat()}"
        else:
            assert end_date is not None
            label = f"Through {end_date.isoformat()}"
        return DateRange(start=start_date, end=end_date, label=label)
    raise ValueError(f"Unsupported date range preset: {preset}")


def filter_sessions(
    sessions: Iterable[ShootingSession],
    scope: PlayerScope,
    date_range: DateRange | None = None,
) -> list[ShootingSession]:
    """Filter sessions by player scope and inclusive date range, sorted newest first."""
    if not scope.is_ready:
        return []
    filtered: list[ShootingSession] = []
    for session in sessions:
        if scope.player_name is not None and session.player_name != scope.player_name:
            continue
        if date_range is not None:
            if date_range.start is not None and session.date < date_range.start:
                continue
            if date_range.end is not None and session.date > date_range.end:
                continue
        filtered.append(session)
    return sorted(filtered, key=lambda item: item.date, reverse=True)


def summarize_sessions(sessions: Iterable[ShootingSession]) -> tuple[dict[str, ShotTotals], ShotTotals]:
    """Return weighted per-category totals and weighted overall totals."""
    category_totals = aggregate_sessions(sessions)
    return category_totals, overall_shot_totals(category_totals)


def build_trend_points(sessions: Iterable[ShootingSession]) -> list[TrendPoint]:
    """Build chronological weighted daily percentages, omitting zero-attempt points."""
    by_date: dict[date, list[ShootingSession]] = defaultdict(list)
    for session in sessions:
        by_date[session.date].append(session)

    points: list[TrendPoint] = []
    for session_date in sorted(by_date):
        day_sessions = by_date[session_date]
        category_totals, overall = summarize_sessions(day_sessions)
        series_totals = {"Overall": overall, **category_totals}
        date_text = session_date.isoformat()
        count = len(day_sessions)
        for category in TREND_SERIES:
            shots = series_totals[category]
            if shots.percentage is None:
                continue
            points.append(
                TrendPoint(
                    session_date=session_date,
                    date_label=date_text,
                    category=category,
                    makes=shots.makes,
                    attempts=shots.attempts,
                    percentage=shots.percentage,
                    percentage_label=format_percentage(shots.percentage),
                    makes_attempts_label=f"{shots.makes}/{shots.attempts}",
                    session_count=count,
                )
            )
    return points


def format_shot_summary(shots: ShotTotals) -> str:
    """Format a shot total pair as 'makes/attempts (pct)'."""
    return f"{shots.makes}/{shots.attempts} ({format_percentage(shots.percentage)})"


def build_history_rows(sessions: Iterable[ShootingSession]) -> list[dict[str, str]]:
    """Convert sessions to newest-first display rows for the dashboard table."""
    ordered = sorted(sessions, key=lambda item: item.date, reverse=True)
    rows: list[dict[str, str]] = []
    for session in ordered:
        totals = session.shot_totals()
        rows.append(
            {
                "Date": session.date.isoformat(),
                "Player": session.player_name,
                "Free Throws": format_shot_summary(totals["Free throws"]),
                "Two-Pointers": format_shot_summary(totals["Two-pointers"]),
                "Three-Pointers": format_shot_summary(totals["Three-pointers"]),
            }
        )
    return rows


def record_session(
    data_path: Path,
    *,
    session_date: date,
    player_name: str,
    free_throw_makes: int,
    free_throw_attempts: int,
    two_point_makes: int,
    two_point_attempts: int,
    three_point_makes: int,
    three_point_attempts: int,
) -> ShootingSession:
    """Validate and append a session through the shared domain model and CSV storage."""
    session = ShootingSession(
        date=session_date,
        player_name=player_name,
        free_throw_makes=free_throw_makes,
        free_throw_attempts=free_throw_attempts,
        two_point_makes=two_point_makes,
        two_point_attempts=two_point_attempts,
        three_point_makes=three_point_makes,
        three_point_attempts=three_point_attempts,
    )
    append_session(data_path, session)
    return session


def update_default_player(settings_path: Path, player_name: str) -> str:
    """Validate and atomically persist the default player name."""
    normalized = validate_player_name(player_name)
    set_default_player(settings_path, normalized)
    return normalized

