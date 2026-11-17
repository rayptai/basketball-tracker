# Basketball Shooting Tracker plan and design

Status: plan approved. Application implementation is pending a separate request.

This document is the single source of truth for the approved application design
and implementation plan. It replaces `DESIGN.md` to avoid duplicate documents.

## Purpose and scope

Build a small Python 3.14 command-line application for recording basketball
shooting sessions, reviewing history, and calculating aggregate statistics. This
is a first independent application in an eight-week AI-assisted programming
curriculum. Keep the code easy for a developer with Java and Python experience
to review and modify.

The first version records sessions by date and player, tracks makes and attempts
for free throws, two-pointers, and three-pointers, saves sessions locally as CSV,
and stores default settings as JSON. Automated tests use pytest.

## Architecture

Use the standard library for application code and pytest as a development
dependency. Use descriptive names and type hints. Avoid frameworks, databases,
class hierarchies, repository layers, and unnecessary abstractions.

| Module | Responsibility |
| --- | --- |
| `cli.py` | Parse commands with `argparse`, select players, display results, and translate errors into clear messages and exit statuses |
| `models.py` | Define the session dataclass, validate records, calculate percentages, and aggregate sessions |
| `settings.py` | Load and save JSON configuration |
| `storage.py` | Read and append CSV session records using `csv` and `pathlib` |
| `__main__.py` | Start the CLI |

Keep validation and calculations independent of command parsing and filesystem
operations so they can be tested directly.

## Proposed directory structure

```text
basketball-tracker/
├── AGENTS.md
├── plan.md
├── pyproject.toml
├── README.md
├── basketball_tracker/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── models.py
│   ├── settings.py
│   └── storage.py
├── tests/
│   ├── test_models.py
│   ├── test_settings.py
│   ├── test_storage.py
│   └── test_cli.py
└── data/
    ├── settings.json
    └── sessions.csv
```

Only this plan and the agent guidance document are created at the planning stage.
Runtime data files are created when needed. Do not commit personal runtime data.

## Paths and settings

Default paths are `data/settings.json` and `data/sessions.csv`, relative to the
current working directory. Global `--settings-file PATH` and `--data-file PATH`
options override these paths. Place global options before the subcommand.

The initial settings schema contains one setting:

```json
{
  "default_player": "Ray"
}
```

An absent `default_player` means no default has been configured. A present value
must be a valid player name. Use the same name validation for settings and
session records.

```text
python -m basketball_tracker config set-player "Ray"
python -m basketball_tracker config show
python -m basketball_tracker --settings-file custom/settings.json config show
```

`config show` displays current configuration, including whether a default is
unset, without creating files. `config set-player` creates the parent directory
and settings file if necessary. Save through a temporary file in the destination
directory and replace the destination after a successful write. Invalid existing
configuration must be reported rather than silently overwritten.

## Session data model

Represent each session with a `ShootingSession` dataclass:

| Field | Python type |
| --- | --- |
| `date` | `datetime.date` |
| `player_name` | `str` |
| `free_throw_makes` | `int` |
| `free_throw_attempts` | `int` |
| `two_point_makes` | `int` |
| `two_point_attempts` | `int` |
| `three_point_makes` | `int` |
| `three_point_attempts` | `int` |

Rules:

- Dates use `YYYY-MM-DD`, must exist, and cannot be in the future relative to the
  local current date. An omitted CLI date uses the local current date.
- Counts are nonnegative integers, and makes cannot exceed attempts.
- A category with zero attempts must have zero makes.
- At least one category must have a positive attempt count.
- Trim surrounding whitespace from player names. Reject empty names and embedded
  line breaks. Preserve capitalization and support spaces, Unicode, and commas.
- Names identify players, with case-sensitive matching in the first version.
- Multiple sessions on the same date, including for the same player, are valid.
  Each `add` command appends one record; no session ID is needed initially.

## CSV schema and persistence

Store one session per row, with this header and column order:

```csv
date,player_name,free_throw_makes,free_throw_attempts,two_point_makes,two_point_attempts,three_point_makes,three_point_attempts
2026-11-17,Ray,8,10,12,20,5,15
```

Use UTF-8, the standard-library CSV reader/writer, and `newline=""` when opening
CSV files. Let the CSV library quote names containing commas correctly.
Percentages are derived and are not stored.

Validate input and the existing CSV before appending. Create the parent directory
and write the header when saving into a missing or empty file. An incompatible
header, malformed row, or invalid stored session is an error; include the file
and row number where possible. Never silently discard invalid records or append
to an invalid file. A CSV without the player column requires an explicit migration
decision before it can be used.

The first version assumes one writer at a time; concurrent-write protection is
outside its scope.

## Command-line interface

### Record sessions

```text
python -m basketball_tracker add -1 8 10 -2 12 20 -3 5 15
python -m basketball_tracker add --date 2026-11-17 --player "Jordan" -1 9 10 -2 14 20 -3 6 15
```

Each numbered option accepts exactly two integers in **makes attempts** order:

| Option | Category |
| --- | --- |
| `-1` | Free throws (one point) |
| `-2` | Two-pointers |
| `-3` | Three-pointers |

Require all three options initially. Use `0 0` for a category not practiced.
Ensure negative counts fail clearly even with numeric option names.

Resolve the player from an explicit `--player` value, then the configured
`default_player`. If neither is available, explain how to supply or configure
one. A per-command override does not change settings, and changing the default
never changes historical records.

### Display history and statistics

```text
python -m basketball_tracker history
python -m basketball_tracker history --player "Jordan"
python -m basketball_tracker stats
python -m basketball_tracker stats --all-players
```

Both commands use the default player unless `--player NAME` or `--all-players`
is supplied. These two options are mutually exclusive. Without a default, require
one of them. Display history newest date first and include player names. Clearly
label the selected player or the all-player scope, especially for combined
statistics. An unknown player has empty history.

For each category, display makes, attempts, and percentage. Calculate percentage
as `100 * makes / attempts`; display `N/A` for zero attempts. Round to one decimal
place only when displaying. Aggregate by summing makes and attempts before
calculating percentages; do not average session percentages. Combined totals
across all shot categories are optional.

### Help

Support `-h` and `--help` using `argparse` at the application level and on every
subcommand, including nested configuration commands.

```text
python -m basketball_tracker --help
python -m basketball_tracker add --help
python -m basketball_tracker config --help
python -m basketball_tracker config set-player --help
```

Help explains commands, paths, defaults, player overrides, numbered shot options,
the makes/attempts order, and examples. Help exits successfully without modifying
files.

## Errors and edge cases

| Condition | Behavior |
| --- | --- |
| Invalid counts, date, or player | Explain the error and save nothing |
| No default player and no explicit selection | Explain how to select or configure a player |
| Missing settings file | Treat as unconfigured; create only when setting a default |
| Empty or malformed JSON, or invalid setting value | Report an error; preserve the existing file |
| Missing or empty CSV | Treat as empty history; write a header on first save |
| No matching sessions | Display “No sessions recorded”; statistics are unavailable |
| Header-only CSV | Treat as empty history |
| Malformed CSV or incompatible schema | Report the problem; do not skip rows or append |
| Read/write failure | Explain the operation and path; return a nonzero exit status |
| Settings write failure | Preserve the existing file using temporary-file replacement |
| Sessions entered out of date order | Sort displayed history newest first |

Routine input and filesystem errors should not expose a traceback to the CLI
user. Successful commands and help return exit status zero; failures return a
nonzero status.

## Implementation sequence and validation

1. Set up the package, Python 3.14 requirement, pytest configuration, and CLI
   entry point.
2. Implement session validation, percentage calculations, and aggregation. Test
   boundaries, zero attempts, invalid names and dates, and differently sized
   sessions to verify weighted aggregation.
3. Implement settings loading/saving and configuration commands. Test missing,
   malformed, and invalid settings, round trips, and preservation on write failure.
4. Implement CSV storage. Test round trips, Unicode and quoted names, multiple
   sessions, empty files, invalid schemas, and malformed rows.
5. Implement `add`. Test player precedence, numbered shot options, omitted
   categories, negative counts, and invalid input leaving data unchanged.
6. Implement player-aware history and statistics. Test filtering, ordering,
   explicit combined scope, mutually exclusive options, and empty history.
7. Verify help at every command level, successful exits, and no file writes.
   Document workflows in the README, run the complete pytest suite, and manually
   exercise recording, history, settings, and statistics with sample data.

Use pytest temporary directories for filesystem tests, including CLI tests.
Avoid tests that depend on personal settings or session files. Keep local-date
tests deterministic. Test useful behavior and failure paths without mirroring
implementation details.

## Deferred features

Editing and deleting sessions, date-range filtering, duplicate detection,
renaming players, automatic CSV migration, concurrent writers, graphical
interfaces, and cloud synchronization are outside the first-version scope.
