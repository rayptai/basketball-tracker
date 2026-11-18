import csv
from dataclasses import replace

import pytest

from basketball_tracker.storage import FIELD_NAMES, append_session, read_sessions


def test_missing_file_and_round_trip(tmp_path, session):
    path = tmp_path / "nested" / "sessions.csv"
    assert read_sessions(path) == []
    assert not path.parent.exists()
    quoted = replace(session, player_name='Zoë, "Junior"')
    append_session(path, quoted)
    append_session(path, quoted)
    assert read_sessions(path) == [quoted, quoted]
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.reader(source))
    assert rows[0] == list(FIELD_NAMES)
    assert len(rows) == 3


@pytest.mark.parametrize("initial", ["", ",".join(FIELD_NAMES), ",".join(FIELD_NAMES) + "\n"])
def test_empty_or_header_only_file(tmp_path, session, initial):
    path = tmp_path / "sessions.csv"
    path.write_text(initial, encoding="utf-8")
    assert read_sessions(path) == []
    append_session(path, session)
    assert read_sessions(path) == [session]


def test_append_to_record_without_final_newline(tmp_path, session):
    path = tmp_path / "sessions.csv"
    append_session(path, session)
    path.write_bytes(path.read_bytes().rstrip(b"\r\n"))
    append_session(path, session)
    assert read_sessions(path) == [session, session]


@pytest.mark.parametrize("bad_row", [
    "2020-01-02,Ray,8,10,12,20,5", "2020-01-02,Ray,8,10,12,20,5,15,extra",
    "2020-01-02,Ray,-1,10,12,20,5,15", "2020-01-02,Ray,11,10,12,20,5,15",
    "2020-01-02,Ray,1.5,10,12,20,5,15", "2020-02-30,Ray,8,10,12,20,5,15",
    "2020-01-02,,8,10,12,20,5,15", '2020-01-02,"unterminated', "",
    "9999-01-01,Ray,8,10,12,20,5,15", "2020-01-02,Ray,0,0,0,0,0,0",
])
def test_invalid_rows_prevent_append(tmp_path, session, bad_row):
    path = tmp_path / "sessions.csv"
    path.write_text(",".join(FIELD_NAMES) + "\n" + bad_row + "\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="row 2"):
        read_sessions(path)
    with pytest.raises(ValueError):
        append_session(path, session)
    assert path.read_bytes() == before


def test_incompatible_header_is_preserved(tmp_path, session):
    path = tmp_path / "sessions.csv"
    path.write_text("date,free_throw_makes\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Incompatible CSV header"):
        append_session(path, session)
    assert path.read_bytes() == before


def test_file_errors(tmp_path, session):
    path = tmp_path / "sessions.csv"
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="Invalid CSV"):
        read_sessions(path)
    with pytest.raises(OSError, match="Cannot read sessions"):
        read_sessions(tmp_path)
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    with pytest.raises(OSError):
        append_session(blocker / "sessions.csv", session)
