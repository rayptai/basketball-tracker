"""Command parsing and text presentation for the shooting tracker."""

import argparse
from collections.abc import Sequence
from datetime import date
import importlib.util
from pathlib import Path
import subprocess
import sys

from basketball_tracker.models import (
    ShootingSession, ShotTotals, aggregate_sessions, format_percentage,
    parse_session_date, validate_player_name,
)
from basketball_tracker.settings import load_settings, set_default_player
from basketball_tracker.storage import append_session, read_sessions


DASHBOARD_THEME_ARGS = (
    "--theme.base", "dark",
    "--theme.backgroundColor", "#0B1120",
    "--theme.secondaryBackgroundColor", "#131C2E",
    "--theme.primaryColor", "#F97316",
    "--theme.textColor", "#F8FAFC",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="basketball-tracker",
        description="Record basketball shooting sessions and review player statistics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--settings-file", type=Path, default=Path("data/settings.json"),
                        help="JSON settings path (default: data/settings.json, relative to current directory)")
    parser.add_argument("--data-file", type=Path, default=Path("data/sessions.csv"),
                        help="CSV sessions path (default: data/sessions.csv, relative to current directory)")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser(
        "add", help="Record one session", description="Record a session. All shot counts must be nonnegative integers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Usage tips for adding a new entry:\n"
            '  Set a default player once: basketball-tracker config set-player "Ray"\n'
            "  Record today's session for that player:\n"
            "    basketball-tracker add -1 8 10 -2 12 20 -3 5 15\n"
            "  Supply all three shot options, each as MAKES ATTEMPTS.\n"
            "  Use 0 0 for a shot type you did not practice.\n"
            "  Override the player or record an earlier date:\n"
            '    basketball-tracker add --player "Jordan Smith" --date 2020-01-02 '
            "-1 8 10 -2 0 0 -3 5 15\n"
            "  Each add command saves a separate session, even on the same date."
        ),
    )
    add.add_argument("--date", help="Session date in YYYY-MM-DD format (default: local today)")
    add.add_argument("--player", help="Player name; overrides the configured default without changing it")
    command_parsers = [add]
    for number, destination, label in (
        (1, "free_throws", "Free throws"), (2, "two_pointers", "Two-pointers"),
        (3, "three_pointers", "Three-pointers"),
    ):
        add.add_argument(f"-{number}", dest=destination, nargs=2, type=int, required=True,
                         metavar=("MAKES", "ATTEMPTS"),
                         help=f"{label}: makes followed by attempts; use 0 0 if not practiced")
    for name in ("history", "stats"):
        command = commands.add_parser(
            name, help="Display sessions" if name == "history" else "Display aggregate statistics",
            description="Select a player or use the configured default. --all-players includes everyone.",
            epilog=f'Example: python -m basketball_tracker {name} --player "Ray"',
        )
        if name == "history":
            command.formatter_class = argparse.RawDescriptionHelpFormatter
            command.epilog = (
                "Usage tips for showing history:\n"
                "  Default player's sessions: basketball-tracker history\n"
                '  A specific player: basketball-tracker history --player "Jordan Smith"\n'
                "  Everyone's sessions: basketball-tracker history --all-players\n"
                "  Sessions appear newest date first, with makes, attempts, and percentages.\n"
                "  Without a default player, use --player or --all-players.\n"
                "  Run from the same directory to use the same default data file."
            )
        selection = command.add_mutually_exclusive_group()
        selection.add_argument("--player", help="Player name; overrides the configured default")
        selection.add_argument("--all-players", action="store_true", help="Include every player")
        command_parsers.append(command)
    config = commands.add_parser("config", help="Inspect or change default settings",
                                 epilog='Example: python -m basketball_tracker config set-player "Ray"')
    config_commands = config.add_subparsers(dest="config_command", required=True)
    show = config_commands.add_parser("show", help="Show settings without creating files")
    set_player = config_commands.add_parser("set-player", help="Save the default player name")
    set_player.add_argument("player_name", help='Default player name; quote names containing spaces')
    web = commands.add_parser(
        "web",
        help="Launch the dark-themed local web dashboard",
        description="Start the local Streamlit web dashboard using the selected settings and session files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Usage tips for the web dashboard:\n"
            "  Launch locally: basketball-tracker web\n"
            "  Custom data files (global options go before web):\n"
            '    basketball-tracker --settings-file custom/settings.json --data-file custom/sessions.csv web\n'
            "  Custom port without opening a browser tab:\n"
            "    basketball-tracker web --port 8502 --no-browser"
        ),
    )
    web.add_argument("--host", default="127.0.0.1", help="Host address to bind (default: 127.0.0.1)")
    web.add_argument("--port", type=int, default=8501, help="Port number to serve on (default: 8501)")
    web.add_argument("--no-browser", action="store_true", help="Do not automatically open a browser window")
    command_parsers.extend([config, show, set_player, web])
    # Reuse each command's help so the complete reference stays in sync with it.
    parser.epilog = (
        "Global file options go before the command.\n"
        "Use COMMAND --help for help on a single command.\n\n"
        "Command reference:\n\n"
        + "\n\n".join(command.format_help().strip() for command in command_parsers)
    )
    return parser


def select_player(explicit_player: str | None, settings_path: Path) -> str:
    if explicit_player is not None:
        return validate_player_name(explicit_player)
    settings = load_settings(settings_path)
    if "default_player" not in settings:
        raise ValueError('No default player. Supply --player NAME or run config set-player "NAME". '
                         'For history/stats, --all-players is also available.')
    return validate_player_name(settings["default_player"])


def display_totals(totals: dict[str, ShotTotals]) -> None:
    for label, shots in totals.items():
        print(f"  {label}: {shots.makes}/{shots.attempts} ({format_percentage(shots.percentage)})")


def build_streamlit_command(
    settings_file: Path,
    data_file: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8501,
    no_browser: bool = False,
) -> list[str]:
    if not 1 <= port <= 65535:
        raise ValueError("Port must be an integer between 1 and 65535.")
    if not host or not host.strip():
        raise ValueError("Host must not be empty.")
    app_path = Path(__file__).with_name("web_app.py")
    command = [
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.address", host.strip(),
        "--server.port", str(port),
        "--browser.gatherUsageStats", "false",
        *DASHBOARD_THEME_ARGS,
    ]
    if no_browser:
        command.extend(["--server.headless", "true"])
    command.extend([
        "--",
        "--settings-file", str(settings_file),
        "--data-file", str(data_file),
    ])
    return command


def launch_web_dashboard(arguments: argparse.Namespace) -> int:
    command = build_streamlit_command(
        arguments.settings_file,
        arguments.data_file,
        host=arguments.host,
        port=arguments.port,
        no_browser=arguments.no_browser,
    )
    if importlib.util.find_spec("streamlit") is None:
        raise ValueError('Streamlit is not installed. Install dependencies with: python -m pip install -e "."')
    try:
        completed = subprocess.run(command, check=False)
    except KeyboardInterrupt:
        return 0
    except OSError as error:
        raise OSError(f"Cannot launch web dashboard: {error}") from error
    return completed.returncode


def run_command(arguments: argparse.Namespace) -> int:
    if arguments.command == "web":
        return launch_web_dashboard(arguments)

    if arguments.command == "config":
        if arguments.config_command == "show":
            settings = load_settings(arguments.settings_file)
            print(f"Settings file: {arguments.settings_file}")
            print(f"Default player: {settings.get('default_player', '(not configured)')}")
        else:
            set_default_player(arguments.settings_file, arguments.player_name)
            print(f"Default player saved: {validate_player_name(arguments.player_name)}")
        return 0

    if arguments.command == "add":
        player = select_player(arguments.player, arguments.settings_file)
        session = ShootingSession(
            parse_session_date(arguments.date) if arguments.date is not None else date.today(),
            player, *arguments.free_throws, *arguments.two_pointers, *arguments.three_pointers,
        )
        append_session(arguments.data_file, session)
        print(f"Saved session for {player} on {session.date.isoformat()}.")
        return 0

    player = None if arguments.all_players else select_player(arguments.player, arguments.settings_file)
    sessions = read_sessions(arguments.data_file)
    if player is not None:
        sessions = [session for session in sessions if session.player_name == player]
    print(f"{'History' if arguments.command == 'history' else 'Statistics'} for "
          f"{player if player is not None else 'all players (combined)'}")
    if not sessions:
        print("No sessions recorded.")
    elif arguments.command == "history":
        for session in sorted(sessions, key=lambda item: item.date, reverse=True):
            print(f"{session.date.isoformat()} | {session.player_name}")
            display_totals(session.shot_totals())
    else:
        print(f"Sessions: {len(sessions)}")
        display_totals(aggregate_sessions(sessions))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        return run_command(arguments)
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
