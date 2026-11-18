"""JSON settings, saved by replacing the destination after a complete write."""

import json
from pathlib import Path
import tempfile

from basketball_tracker.models import validate_player_name


def load_settings(path: Path) -> dict[str, object]:
    try:
        with path.open(encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
    except FileNotFoundError:
        return {}
    except (ValueError, UnicodeError) as error:
        raise ValueError(f"Invalid settings in '{path}': {error}") from error
    except OSError as error:
        raise OSError(f"Cannot read settings '{path}': {error}") from error
    try:
        if not isinstance(settings, dict):
            raise ValueError("Settings must be a JSON object.")
        if "default_player" in settings:
            settings["default_player"] = validate_player_name(settings["default_player"])
    except ValueError as error:
        raise ValueError(f"Invalid settings in '{path}': {error}") from error
    return settings


def set_default_player(path: Path, player_name: str) -> None:
    player_name = validate_player_name(player_name)
    settings = load_settings(path)  # Never overwrite corrupt configuration.
    settings["default_player"] = player_name
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as settings_file:
            temporary_path = Path(settings_file.name)
            json.dump(settings, settings_file, ensure_ascii=False, indent=2)
            settings_file.write("\n")
        temporary_path.replace(path)
    except OSError as error:
        raise OSError(f"Cannot save settings '{path}': {error}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
