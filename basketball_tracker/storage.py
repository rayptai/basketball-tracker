"""Read validated session records and append them to a local CSV file."""

import csv
from pathlib import Path

from basketball_tracker.models import ShootingSession, parse_session_date


FIELD_NAMES = (
    "date", "player_name", "free_throw_makes", "free_throw_attempts",
    "two_point_makes", "two_point_attempts", "three_point_makes", "three_point_attempts",
)


def read_sessions(path: Path) -> list[ShootingSession]:
    sessions: list[ShootingSession] = []
    reader = None
    try:
        with path.open(encoding="utf-8", newline="") as session_file:
            reader = csv.reader(session_file, strict=True)
            header = next(reader, None)
            if header is None:
                return []
            if header != list(FIELD_NAMES):
                raise ValueError("Incompatible CSV header; expected the documented player-aware schema.")
            for row in reader:
                if len(row) != len(FIELD_NAMES):
                    raise ValueError(f"Expected {len(FIELD_NAMES)} columns, found {len(row)}.")
                counts = []
                for value in row[2:]:
                    if not value.isascii() or not value.isdecimal():
                        raise ValueError("Shot counts must be nonnegative integers.")
                    counts.append(int(value))
                sessions.append(ShootingSession(parse_session_date(row[0]), row[1], *counts))
    except FileNotFoundError:
        return []
    except (ValueError, csv.Error, UnicodeError) as error:
        line = reader.line_num if reader is not None else 1
        raise ValueError(f"Invalid CSV '{path}', row {line}: {error}") from error
    except OSError as error:
        raise OSError(f"Cannot read sessions '{path}': {error}") from error
    return sessions


def append_session(path: Path, session: ShootingSession) -> None:
    read_sessions(path)  # Validate the entire existing file before any mutation.
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        has_content = path.exists() and path.stat().st_size > 0
        needs_newline = False
        if has_content:
            with path.open("rb") as session_file:
                session_file.seek(-1, 2)
                needs_newline = session_file.read(1) not in (b"\r", b"\n")
        with path.open("a", encoding="utf-8", newline="") as session_file:
            if needs_newline:
                session_file.write("\n")
            writer = csv.writer(session_file)
            if not has_content:
                writer.writerow(FIELD_NAMES)
            writer.writerow([
                session.date.isoformat(), session.player_name,
                session.free_throw_makes, session.free_throw_attempts,
                session.two_point_makes, session.two_point_attempts,
                session.three_point_makes, session.three_point_attempts,
            ])
    except OSError as error:
        raise OSError(f"Cannot save session to '{path}': {error}") from error
