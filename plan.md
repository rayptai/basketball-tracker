# Basketball Shooting Tracker plan and design

Status: first-version CLI and second-version dark-themed Streamlit web dashboard
implemented and verified on Python 3.14.10.

This document is the single source of truth for the approved application design
and implementation plan. It replaces `DESIGN.md` to avoid duplicate documents.

## Purpose and scope

Build a small Python 3.14 application for recording basketball shooting
sessions, reviewing history, and analyzing aggregate statistics through both a
command-line interface and a local dark-themed sports analytics web dashboard.
This is an independent application in an eight-week AI-assisted programming
curriculum. Keep the code easy for a developer with Java and Python experience
to review and modify.

The first version (implemented) records sessions by date and player via CLI,
tracks makes and attempts for free throws, two-pointers, and three-pointers,
saves sessions locally as CSV, and stores default settings as JSON. The planned
second version adds a local Streamlit web dashboard that preserves all existing
CLI commands, business logic, and data rules. Automated tests use pytest
(including Streamlit's headless `AppTest`).

## Architecture

Keep core domain logic, settings, storage, CLI, dashboard view-model helpers,
and SVG rendering in small, standard-library Python modules. Add `streamlit>=1.40`
as a standard runtime dependency in `pyproject.toml` for the local web dashboard
(loaded lazily only when launching the dashboard so CLI commands remain fast),
and `pytest` as a development dependency. Avoid databases, class hierarchies,
repository layers, and external CDN assets.

| Module | Responsibility |
| --- | --- |
| `cli.py` | Parse commands with `argparse` (including `web` launcher), select players, display CLI results, and translate errors into clear messages and exit statuses |
| `models.py` | Define the session dataclass, validate records, calculate/format percentages, and aggregate category and overall totals |
| `settings.py` | Load and save JSON configuration atomically |
| `storage.py` | Read and append validated CSV session records using `csv` and `pathlib` |
| `dashboard.py` | Pure-Python dashboard helpers: safe state loading, player discovery, scope resolution, inclusive date-range filtering, weighted daily trend aggregation, history formatting, and write wrappers |
| `court_svg.py` | Pure-Python dark-themed inline SVG half-court generator with stat badges anchored on the free-throw line, 2-point area, and 3-point arc |
| `web_app.py` | Thin dark-themed Streamlit dashboard UI (sidebar filters/settings, 5-card KPI row, court visual, add-session panel, dynamic trend chart, and history table) |
| `__main__.py` | Start the CLI |

Keep validation, calculations, filtering, trend aggregation, and SVG rendering
independent of command parsing, Streamlit widgets, and filesystem operations so
they can be tested directly.

## Directory structure

```text
basketball-tracker/
├── .streamlit/
│   └── config.toml
├── AGENTS.md
├── plan.md
├── pyproject.toml
├── README.md
├── basketball_tracker/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── court_svg.py
│   ├── dashboard.py
│   ├── models.py
│   ├── settings.py
│   ├── storage.py
│   └── web_app.py
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_settings.py
│   ├── test_storage.py
│   ├── test_cli.py
│   ├── test_dashboard.py
│   ├── test_court_svg.py
│   └── test_web_app.py
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
the makes/attempts order, and examples. Top-level help includes the complete
reference for all commands, including nested configuration commands; individual
command help remains focused on that command. Include usage tips for adding an
entry (default player, shot pairs, zero attempts, and date/player overrides) and
showing history (default player, specific player, all players, and date order).
Help exits successfully without modifying files.

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

## Implementation results

All seven implementation steps are complete. The application uses only standard
libraries at runtime, with pytest as the development test dependency. The README
documents setup, commands, paths, file formats, and limitations.

Validation: `python -m pytest -q` passed all 94 tests. A separate-process smoke
check using temporary data also exercised settings inspection and updates,
recording sessions with default and explicit players, chronological history,
per-player and combined statistics, and nested command help. No personal runtime
data was created in the repository.

## Web dashboard design (v2)

Launch the local dark-themed sports analytics dashboard via the CLI while
preserving all existing CLI commands, business logic, and data rules:

```text
python -m basketball_tracker web [--host 127.0.0.1] [--port 8501] [--no-browser]
python -m basketball_tracker --settings-file custom/settings.json --data-file custom/sessions.csv web
```

- Respects global `--settings-file` and `--data-file` placed before `web`
  (defaults remain `data/settings.json` and `data/sessions.csv`, relative to the
  current working directory).
- Binds to `127.0.0.1` by default (local-only, matching the single-writer
  assumption) and supports `-h`/`--help` without writing files or importing
  Streamlit.
- Launches `sys.executable -m streamlit run <web_app.py>` with `--server.address`,
  `--server.port`, `--browser.gatherUsageStats false`, dark `--theme.*` flags,
  optional `--server.headless true`, and `-- --settings-file <path> --data-file <path>`.
- If run from source in an environment without `streamlit` installed, prints a
  clear installation instruction (`python -m pip install -e .`) to `stderr` and
  exits nonzero without a traceback.

### Dependency justification

Add `streamlit>=1.40` to `[project]` `dependencies` in `pyproject.toml`. It
provides a Python-only reactive web UI, forms, tables, theming, local offline
charting (bundled Altair/Vega-Lite), and headless `AppTest` testing without a
JavaScript toolchain or separate frontend repo. Loading it lazily keeps CLI
commands fast.

### Visual theme and offline guarantee

- **Dark sports analytics palette** (configured in `.streamlit/config.toml` and
  CLI launcher flags):
  - App canvas: `#0B1120`
  - Card / panel surface: `#131C2E`
  - Elevated badge / input surface: `#1B263B`
  - Border / hairline: `#26344D`
  - Primary accent (basketball orange): `#F97316`
  - Category trend accents: `#38BDF8` (FT), `#34D399` (2PT), `#A78BFA` (3PT)
  - Primary text / tabular metrics: `#F8FAFC`; muted labels: `#94A3B8`
- **Fully offline**: Pure inline SVG half-court and Streamlit-bundled local
  charting (Vega-Lite/Altair); zero external CDNs, remote fonts, or image
  downloads.

### Full dashboard text mock-up

```text
+--------------------------------------------------------------------------------------------------------+
| [SIDEBAR]                  |  BASKETBALL SHOOTING TRACKER                         [Scope: Ray]         |
|                            |  Active view: Ray  |  Date range: 2026-10-21 to 2026-11-20  |  6 sessions |
| PLAYER SCOPE               +---------------------------------------------------------------------------+
|  (o) Default player (Ray)  |                                                                           |
|  ( ) Specific player       |  +------------+ +-------------+ +-------------+ +-----------+ +---------+ |
|  ( ) All players (combined)|  | SESSIONS   | | OVERALL     | | FREE THROWS | | 2-POINTERS| | 3-PNTRS | |
|                            |  |     6      | |   58.3%     | |    82.0%    | |   61.5%   | |  37.8%  | |
| DATE RANGE FILTER          |  | in range   | |  154 / 264  | |   41 / 50   | |  80 / 130 | | 33 / 84 | |
|  Preset: [Last 30 days v]  |  +------------+ +-------------+ +-------------+ +-----------+ +---------+ |
|  Start:  [2026-10-21    ]  |                                                                           |
|  End:    [2026-11-20    ]  |  +---------------------------------------+  +---------------------------+ |
|                            |  | COURT BREAKDOWN  (Dark SVG Half-Court)|  | RECORD SESSION            | |
| -------------------------- |  |                                       |  |                           | |
| DEFAULT PLAYER SETTINGS    |  |            [Backboard]                |  | Date:   [2026-11-20    ]  | |
|  Current: Ray              |  |                (O)                    |  | Player: [Ray           ]  | |
|  New default:              |  |      |    +-----------+    |          |  |  (edit for 1-off override)| |
|  [Ray                   ]  |  |      |    |   Paint   |    |          |  |                           | |
|  [ Save Default Player  ]  |  |      |  +-+[FT  82.0%]+-+  |          |  | Shot Type   Makes   Att   | |
|                            |  |      |  |    41 / 50    |  |          |  | Free Throws [ 0 ] [ 0 ]   | |
| -------------------------- |  |       \ | [2PT  61.5%]  | /           |  | 2-Pointers  [ 0 ] [ 0 ]   | |
| > Data Paths (read-only)   |  |        \     80 / 130    /            |  | 3-Pointers  [ 0 ] [ 0 ]   | |
|   data/settings.json       |  |         `._[3PT 37.8%]_.'             |  |                           | |
|   data/sessions.csv        |  |              33 / 84                  |  | [     Save Session      ] | |
|                            |  +---------------------------------------+  +---------------------------+ |
|                            |                                                                           |
|                            |  +---------------------------------------------------------------------+  |
|                            |  | SHOOTING PERCENTAGE TREND OVER TIME                                 |  |
|                            |  | Series: [x] Overall   [x] FT   [x] 2PT   [x] 3PT                    |  |
|                            |  |                                                                     |  |
|                            |  | 100% |                                                              |  |
|                            |  |  80% |   *-----------*-----------*---------*   (FT)                 |  |
|                            |  |  60% |     \     *---*-----*----/----*         (2PT / Overall)      |  |
|                            |  |  40% |   o--o---o-----------o---------o        (3PT)                |  |
|                            |  |  20% |                                                              |  |
|                            |  |   0% +----------------------------------------------------------    |  |
|                            |  |      Oct 24      Nov 01      Nov 08      Nov 15      Nov 20         |  |
|                            |  +---------------------------------------------------------------------+  |
|                            |                                                                           |
|                            |  +---------------------------------------------------------------------+  |
|                            |  | SESSION HISTORY (Newest First)                                      |  |
|                            |  | Date       | Player | Free Throws    | Two-Pointers   | Three-Ptrs  |  |
|                            |  | 2026-11-20 | Ray    | 9/10 (90.0%)   | 14/20 (70.0%)  | 6/15 (40.0%)|  |
|                            |  | 2026-11-17 | Ray    | 8/10 (80.0%)   | 12/20 (60.0%)  | 5/15 (33.3%)|  |
|                            |  | ...                                                                 |  |
|                            |  +---------------------------------------------------------------------+  |
+--------------------------------------------------------------------------------------------------------+
```

### Dashboard components and preserved rules

- **Player / scope selector (sidebar)**: Mirrors CLI precedence and mutual
  exclusion (`Default player`, `Specific player` with known-player list + custom
  case-sensitive input, and `All players (combined)`). Clearly prompts when no
  default is configured and labels combined views explicitly.
- **Interactive date-range filter (sidebar)**: Read-only view filter with
  presets (`All dates`, `Last 7 days`, `Last 30 days`, `Last 90 days`, and
  `Custom range` with inclusive start/end pickers). Invalid ranges
  (`start > end`) display a clear inline error. Dynamically updates KPI cards,
  court visual, trend chart, and history table simultaneously without modifying
  files.
- **5-card KPI row**: `Sessions`, `Overall` (weighted
  `100 * total_makes / total_attempts` across FT + 2PT + 3PT), `Free Throws`,
  `Two-Pointers`, and `Three-Pointers`. Zero attempts display `N/A`; all
  percentages round to one decimal place only when displayed.
- **Dark half-court visual (`court_svg.py`)**: Self-contained inline SVG
  half-court displaying Free Throw % at the free-throw line, Two-Point % in the
  2-point area, and Three-Point % along the 3-point arc, each with
  `makes / attempts`. Escapes all dynamic text with `html.escape()`.
- **Shooting percentage trend chart over time**: Dynamically reflects active
  player scope and date-range filter. Groups matching sessions by date in
  chronological order (oldest to newest), sums makes and attempts per date
  before calculating percentages (`Overall`, `Free Throws`, `Two-Pointers`,
  `Three-Pointers`), omits zero-attempt points rather than plotting `0.0%`,
  supports toggling series, and displays hover tooltips (date, category,
  percentage, makes/attempts, and session count).
- **Record session form & default player settings**: Validates all writes
  through `ShootingSession` and saves via `append_session()` /
  `set_default_player()`. Editing the player field on the Record Session form
  overrides the player for that single session without modifying
  `settings.json`. Read-only views never create files; corrupt JSON or CSV files
  display clear errors without tracebacks or silent overwrites.
- **Session history table**: Filtered by active player scope and date range,
  ordered newest date first, showing `makes/attempts (pct)` per shot category
  and `"No sessions recorded."` when empty.

## Web dashboard implementation sequence and validation (v2)

1. Update `AGENTS.md`, `pyproject.toml` (`dependencies = ["streamlit>=1.40"]`),
   and `.streamlit/config.toml`; verify `pip install -e ".[dev]"` on Python 3.14.
2. Add `format_percentage` and `overall_shot_totals` in `models.py` and build
   pure-Python dashboard helpers in `dashboard.py` with `tests/test_dashboard.py`
   (and tests in `tests/test_models.py`).
3. Build `court_svg.py` and `tests/test_court_svg.py` covering percentages,
   `N/A`, empty state, zone placement, and HTML escaping.
4. Add the `web` subcommand in `cli.py` and extend `tests/test_cli.py` (help
   without file writes, path & theme forwarding, missing-Streamlit handling).
5. Build `web_app.py` and headless integration tests in `tests/test_web_app.py`
   using `streamlit.testing.v1.AppTest` with pytest temporary directories.
6. Run the full `pytest` suite, update `README.md`, and smoke-test the live
   dashboard in a browser using temporary data files.

### v2 Implementation results

All six web dashboard implementation steps are complete. `streamlit>=1.40`
(installed as `streamlit 1.67.0` with bundled `altair 6.3.0`) is declared as a
standard runtime dependency and loaded lazily when launching `web` so CLI
commands remain fast.

Validation: `python -m pytest -v` passed all 117 tests (94 original CLI/core
tests + 23 new model, dashboard, court SVG, CLI `web`, and Streamlit `AppTest`
tests) with zero warnings. A live server smoke check launched
`python -m basketball_tracker web --port 8512 --no-browser` against temporary
files cleanly (no personal data under `data/` was created). Automated Chrome
visual inspection was unavailable because Chrome remote debugging was not
enabled locally; users can run `basketball-tracker web` to inspect the live
dashboard directly.

## Deferred features

Editing and deleting sessions, CLI date-range filtering, duplicate detection,
renaming players, automatic CSV migration, concurrent writers, and cloud
synchronization remain outside scope.
