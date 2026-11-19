"""Command parsing and text presentation for the shooting tracker."""

import argparse
from collections.abc import Sequence
from datetime import date
from pathlib import Path
import sys

from basketball_tracker.models import (
    ShootingSession, ShotTotals, aggregate_sessions, parse_session_date, validate_player_name,
)
from basketball_tracker.settings import load_settings, set_default_player
from basketball_tracker.storage import append_session, read_sessions


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
    command_parsers.extend([config, show, set_player])
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
        percentage = "N/A" if shots.percentage is None else f"{shots.percentage:.1f}%"
        print(f"  {label}: {shots.makes}/{shots.attempts} ({percentage})")


def run_command(arguments: argparse.Namespace) -> None:
    if arguments.command == "config":
        if arguments.config_command == "show":
            settings = load_settings(arguments.settings_file)
            print(f"Settings file: {arguments.settings_file}")
            print(f"Default player: {settings.get('default_player', '(not configured)')}")
        else:
            set_default_player(arguments.settings_file, arguments.player_name)
            print(f"Default player saved: {validate_player_name(arguments.player_name)}")
        return

    if arguments.command == "add":
        player = select_player(arguments.player, arguments.settings_file)
        session = ShootingSession(
            parse_session_date(arguments.date) if arguments.date is not None else date.today(),
            player, *arguments.free_throws, *arguments.two_pointers, *arguments.three_pointers,
        )
        append_session(arguments.data_file, session)
        print(f"Saved session for {player} on {session.date.isoformat()}.")
        return

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


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        run_command(arguments)
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0
