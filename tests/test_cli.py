from datetime import date
import os
from pathlib import Path
import subprocess
import sys

import pytest

from basketball_tracker.cli import main
from basketball_tracker.settings import load_settings
from basketball_tracker.storage import read_sessions


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def invoke(*arguments):
        return main(["--settings-file", str(tmp_path / "settings.json"),
                     "--data-file", str(tmp_path / "sessions.csv"), *arguments])

    return invoke


SHOTS = ("-1", "8", "10", "-2", "12", "20", "-3", "5", "15")


def test_complete_workflow(cli, tmp_path, capsys):
    assert cli("config", "set-player", " Ray ") == 0
    assert cli("config", "show") == 0
    assert "Default player: Ray" in capsys.readouterr().out
    assert cli("add", "--date", "2020-01-02", *SHOTS) == 0
    assert cli("add", "--date", "2020-01-01", "--player", "Jordan", *SHOTS) == 0
    assert cli("add", "--date", "2020-01-03", *SHOTS) == 0
    capsys.readouterr()
    assert cli("history") == 0
    output = capsys.readouterr().out
    assert output.index("2020-01-03") < output.index("2020-01-02")
    assert "Jordan" not in output
    assert "Free throws: 8/10 (80.0%)" in output
    assert cli("stats") == 0
    output = capsys.readouterr().out
    assert "Sessions: 2" in output
    assert "Two-pointers: 24/40 (60.0%)" in output
    assert cli("stats", "--all-players") == 0
    output = capsys.readouterr().out
    assert "all players (combined)" in output and "Sessions: 3" in output
    assert cli("stats", "--player", "Jordan") == 0
    assert "Sessions: 1" in capsys.readouterr().out
    assert cli("history", "--player", "ray") == 0
    assert "No sessions recorded" in capsys.readouterr().out
    assert cli("config", "set-player", "Jordan") == 0
    assert [s.player_name for s in read_sessions(tmp_path / "sessions.csv")] == ["Ray", "Jordan", "Ray"]


def test_override_without_settings_and_default_date(cli, tmp_path):
    before = date.today()
    assert cli("add", "--player", "Zoë, Jr.", *SHOTS) == 0
    after = date.today()
    sessions = read_sessions(tmp_path / "sessions.csv")
    assert before <= sessions[0].date <= after
    assert sessions[0].player_name == "Zoë, Jr."
    assert not (tmp_path / "settings.json").exists()


def test_override_does_not_change_default(cli, tmp_path):
    cli("config", "set-player", "Ray")
    before = (tmp_path / "settings.json").read_bytes()
    assert cli("add", "--player", "Jordan", *SHOTS) == 0
    assert (tmp_path / "settings.json").read_bytes() == before
    assert load_settings(tmp_path / "settings.json")["default_player"] == "Ray"


@pytest.mark.parametrize("arguments", [
    ("config", "show"), ("history", "--all-players"), ("stats", "--player", "Unknown"),
])
def test_read_only_commands_do_not_create_files(cli, tmp_path, arguments):
    assert cli(*arguments) == 0
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("arguments", [("add", *SHOTS), ("history",), ("stats",)])
def test_no_default(cli, tmp_path, capsys, arguments):
    assert cli(*arguments) == 1
    assert "No default player" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("command", [(), ("add",), ("history",), ("stats",), ("config",),
                                      ("config", "show"), ("config", "set-player")])
@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help(cli, tmp_path, capsys, command, flag):
    with pytest.raises(SystemExit) as result:
        cli(*command, flag)
    assert result.value.code == 0
    assert "usage:" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("arguments", [
    ("add", "--player", "Ray", "--date", "2020-02-30", *SHOTS),
    ("add", "--player", "Ray", "--date", "9999-01-01", *SHOTS),
    ("add", "--player", " ", *SHOTS),
    ("add", "--player", "Ray", "-1", "11", "10", "-2", "0", "0", "-3", "0", "0"),
    ("add", "--player", "Ray", "-1", "0", "0", "-2", "0", "0", "-3", "0", "0"),
    ("add", "--player", "Ray", "-1", "-1", "10", "-2", "0", "0", "-3", "0", "0"),
    ("add", "--player", "Ray", "-1", "-5", "10", "-2", "0", "0", "-3", "0", "0"),
])
def test_validation_preserves_existing_data(cli, tmp_path, capsys, arguments):
    assert cli("add", "--player", "Ray", *SHOTS) == 0
    before = (tmp_path / "sessions.csv").read_bytes()
    assert cli(*arguments) == 1
    assert "Error:" in capsys.readouterr().err
    assert (tmp_path / "sessions.csv").read_bytes() == before


@pytest.mark.parametrize("arguments", [
    ("add", "--player", "Ray", "-1", "oops", "10", "-2", "0", "0", "-3", "0", "0"),
    ("add", "--player", "Ray", "-1", "1", "10"),
    ("stats", "--player", "Ray", "--all-players"),
])
def test_parse_errors_are_graceful(cli, tmp_path, capsys, arguments):
    with pytest.raises(SystemExit) as result:
        cli(*arguments)
    assert result.value.code == 2
    error = capsys.readouterr().err
    assert "error:" in error and "Traceback" not in error
    assert list(tmp_path.iterdir()) == []


def test_zero_attempt_display_and_rounding(cli, capsys):
    assert cli("add", "--player", "Ray", "-1", "1", "3", "-2", "0", "0", "-3", "0", "0") == 0
    assert cli("stats", "--player", "Ray") == 0
    output = capsys.readouterr().out
    assert "33.3%" in output
    assert "Two-pointers: 0/0 (N/A)" in output


def test_corrupt_files_and_io_errors(cli, tmp_path, capsys):
    settings = tmp_path / "settings.json"
    settings.write_text("{")
    assert cli("config", "show") == 1
    assert cli("config", "set-player", "Ray") == 1
    assert settings.read_text() == "{"
    data = tmp_path / "sessions.csv"
    data.write_text("bad,header\n")
    assert cli("add", "--player", "Ray", *SHOTS) == 1
    assert cli("history", "--all-players") == 1
    assert data.read_text() == "bad,header\n"
    assert main(["--data-file", str(tmp_path), "history", "--all-players"]) == 1
    error = capsys.readouterr().err
    assert "Invalid settings" in error and "Invalid CSV" in error
    assert "Cannot read sessions" in error and "Traceback" not in error


def test_module_entry_point_in_separate_process(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root)
    completed = subprocess.run(
        [sys.executable, "-m", "basketball_tracker", "--help"],
        cwd=tmp_path, env=environment, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0
    assert "--settings-file" in completed.stdout
    assert list(tmp_path.iterdir()) == []
