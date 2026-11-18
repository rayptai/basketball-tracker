# Basketball Shooting Tracker

A Python 3.14 command-line application that records shooting sessions locally
and displays player history and aggregate shooting percentages. Application code
uses only the Python standard library; automated tests use pytest.

## Get started

From the repository directory, check that Python 3.14 is installed:

```powershell
python --version
python -m basketball_tracker --help
python -m basketball_tracker config set-player "Ray"
python -m basketball_tracker add -1 8 10 -2 12 20 -3 5 15
python -m basketball_tracker history
python -m basketball_tracker stats
```

Each shot option requires **makes followed by attempts**:

| Option | Shot type | Example |
| --- | --- | --- |
| `-1` | Free throws | `-1 8 10` |
| `-2` | Two-pointers | `-2 12 20` |
| `-3` | Three-pointers | `-3 5 15` |

Supply all three options. Use `0 0` for a shot type you did not practice. Counts
must be nonnegative integers, makes cannot exceed attempts, and each session
must contain at least one attempt.

The session date defaults to the local current date. To record an earlier session:

```powershell
python -m basketball_tracker add --date 2020-01-02 -1 8 10 -2 12 20 -3 0 0
```

Dates must use `YYYY-MM-DD`, be valid calendar dates, and not be in the future.
You can record multiple sessions for the same player on the same date.

## Players and settings

```powershell
python -m basketball_tracker config show
python -m basketball_tracker config set-player "Jordan Smith"
python -m basketball_tracker add --player "Ray" -1 8 10 -2 12 20 -3 5 15
python -m basketball_tracker history --player "Ray"
python -m basketball_tracker stats --player "Ray"
python -m basketball_tracker stats --all-players
```

`--player` overrides the saved default for that command. It does not change the
default, and changing the default never changes saved sessions. If no default is
configured, supply `--player` for `add`, and either `--player` or `--all-players`
for history and statistics. Player selection options are mutually exclusive.

Names are case-sensitive: `Ray` and `ray` identify different players. Surrounding
whitespace is trimmed; empty names and line breaks are rejected. Spaces, commas,
and Unicode are supported. Quote names with spaces in your shell.

The default player is saved in `data/settings.json`:

```json
{
  "default_player": "Ray"
}
```

## History and statistics

History displays newest dates first, including the player and all three shot
categories. Statistics display the number of selected sessions and each category's
total makes, total attempts, and percentage. For example:

```text
Statistics for Ray
Sessions: 1
  Free throws: 8/10 (80.0%)
  Two-pointers: 12/20 (60.0%)
  Three-pointers: 5/15 (33.3%)
```

Percentages are rounded to one decimal place for display. Zero attempts display
`N/A`. Aggregates divide total makes by total attempts, rather than averaging
session percentages. `--all-players` explicitly combines all players and labels
the output accordingly. An empty selection displays `No sessions recorded.`

## Local files

Sessions are stored in UTF-8 CSV at `data/sessions.csv`, with one row per session:

```csv
date,player_name,free_throw_makes,free_throw_attempts,two_point_makes,two_point_attempts,three_point_makes,three_point_attempts
2020-01-02,Ray,8,10,12,20,5,15
```

Default paths are relative to the **current working directory**. Run from the
same directory to use the same files, or supply explicit paths. Global path
options go before the subcommand:

```powershell
python -m basketball_tracker --settings-file "C:\TrackerData\settings.json" --data-file "C:\TrackerData\sessions.csv" stats
```

Missing settings mean no default is configured. Missing or empty CSV files mean
no sessions are recorded. Read-only commands and help do not create files.
Writes create parent directories when needed. Runtime files under `data/` are
ignored by Git; keep custom personal data paths out of version control too.

Malformed configuration or session files produce errors and are not overwritten
or silently repaired. Existing CSV data is checked before appending. Older CSV
schemas without player names need an explicit migration decision. Settings are
saved using a temporary file and replacement, preserving the original if writing
or replacement fails. Back up your data as appropriate; CSV appends are not
transactional. Use one writing process at a time.

## Help and exit statuses

Use `-h` or `--help` on any command, including nested configuration commands:

```powershell
python -m basketball_tracker add --help
python -m basketball_tracker history -h
python -m basketball_tracker config set-player --help
```

Successful commands and help exit with status zero. Input and filesystem failures
produce a clear error and a nonzero exit status without a traceback.

## Development and testing

Optionally create an isolated environment and install the package with its test
dependency. PowerShell commands:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

With pytest already installed, run `python -m pytest -q` from the repository.
Tests use temporary directories, not personal session files. Editable installation
also provides a `basketball-tracker` command in that environment; running via
`python -m basketball_tracker` from the repository requires no installation.

See [plan.md](plan.md) for the approved design and implementation sequence, and
[AGENTS.md](AGENTS.md) for contributor guidance. The first version does not support
editing/deleting sessions, date-range filtering, player renaming, automatic
migration, concurrent writers, or cloud synchronization.
