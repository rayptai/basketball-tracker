import json
from pathlib import Path

import pytest

from basketball_tracker.settings import load_settings, set_default_player


def test_missing_settings_and_round_trip(tmp_path):
    path = tmp_path / "nested" / "settings.json"
    assert load_settings(path) == {}
    assert not path.parent.exists()
    set_default_player(path, "  Zoë, Jr.  ")
    assert load_settings(path) == {"default_player": "Zoë, Jr."}
    assert "Zoë" in path.read_text(encoding="utf-8")
    set_default_player(path, "Jordan")
    assert load_settings(path)["default_player"] == "Jordan"


@pytest.mark.parametrize("contents", ["", "{", "[]", "null", '{"default_player": null}',
                                       '{"default_player": 42}', '{"default_player": " "}',
                                       '{"default_player": "A\\nB"}'])
def test_invalid_settings_are_preserved(tmp_path, contents):
    path = tmp_path / "settings.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid settings"):
        load_settings(path)
    with pytest.raises(ValueError):
        set_default_player(path, "Ray")
    assert path.read_text(encoding="utf-8") == contents


def test_unconfigured_object_and_other_settings_preserved(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"other": 123}', encoding="utf-8")
    assert "default_player" not in load_settings(path)
    set_default_player(path, "Ray")
    assert json.loads(path.read_text()) == {"other": 123, "default_player": "Ray"}


def test_replace_failure_preserves_settings_and_cleans_temp_file(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    set_default_player(path, "Ray")
    before = path.read_bytes()

    def fail_replace(self, target):
        raise PermissionError("Simulated replacement failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="Cannot save settings"):
        set_default_player(path, "Jordan")
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_encoding_and_directory(tmp_path):
    path = tmp_path / "settings.json"
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="Invalid settings"):
        load_settings(path)
    with pytest.raises(OSError, match="Cannot read settings"):
        load_settings(tmp_path)
