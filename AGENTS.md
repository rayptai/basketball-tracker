# Repository guidance

## Scope and authorization

- Read [plan.md](plan.md) before implementing changes. It contains the approved
  plan and design; this file provides working rules for contributors and agents.
- The current authorized work is documentation only. Do not create application
  code, project configuration, tests, or runtime data until the user authorizes
  implementation. Once implementation is authorized, follow the sequence in
  `plan.md` and the user's requested scope.
- Later explicit user instructions take precedence. Keep these documents aligned
  when requirements change. Do not silently expand the first-version scope.

## Development approach

- Target Python 3.14. Prefer standard-library application dependencies; use pytest
  for automated tests. Explain the clear value before adding another dependency.
- Keep the architecture small: CLI, session model/calculations, JSON settings,
  and CSV storage. Avoid unnecessary abstractions, frameworks, and databases.
- Use descriptive names and type hints. Keep calculation and validation logic
  independent of command parsing and filesystem operations.
- Favor small, reviewable changes suitable for a developer learning an
  AI-assisted workflow. Explain behavior, validation performed, and limitations.

## Application contracts

- Use `argparse`, with `-h` and `--help` on the application and every subcommand.
  Help must exit successfully and must not write files.
- Support `add`, `history`, `stats`, `config show`, and `config set-player`.
- Shot options are `-1`, `-2`, and `-3`, each taking makes followed by attempts.
  Require all three; use `0 0` for an unpracticed category.
- Store each session's date, player name, and makes/attempts for all categories
  in CSV. Use the exact schema in `plan.md`; derive percentages on demand.
- Store the default player in JSON settings. Explicit `--player` overrides the
  default for that command without changing settings or historical records.
- History and statistics select the default player unless `--player` or
  `--all-players` is supplied. These options are mutually exclusive. Require an
  explicit selection if no default exists; label combined results clearly.
- Default files are `data/settings.json` and `data/sessions.csv`, relative to the
  current working directory. Support global path overrides as documented.
- Validate dates, player names, and nonnegative integer counts. Makes cannot
  exceed attempts, future dates are invalid, and an entirely empty session is
  invalid. Multiple sessions per player per date are allowed.
- Trim player names, reject empty names and line breaks, preserve Unicode and
  capitalization, and match names case-sensitively.
- Display zero-attempt percentages as `N/A` and other percentages to one decimal
  place. Aggregate totals before calculating percentages.
- Display history newest date first. Report empty history clearly.

## Persistence and errors

- Use standard-library `csv`, UTF-8, and `newline=""` for session files.
- Treat a missing settings file as unconfigured and a missing/empty CSV as empty
  history. Read-only commands must not create runtime files.
- Validate existing CSV data before appending. Report corrupt data or incompatible
  schemas; do not skip records, overwrite corruption, or invent a migration.
- Write settings through a temporary file in the same directory, replacing the
  destination only after a successful write.
- Handle routine input and filesystem errors with useful messages and nonzero
  exit statuses, without tracebacks. Invalid input must not change saved data.
- Assume one writer at a time. Do not commit personal runtime data.

## Verification

- When implementation is authorized, test model behavior, storage, settings, and
  CLI behavior with pytest. Follow the validation sequence in `plan.md`.
- Use temporary directories and explicit paths in filesystem and CLI tests;
  never read or modify the user's real settings or sessions during tests.
- Cover weighted aggregation, zero attempts, player precedence/filtering, CSV
  quoting, malformed files, invalid inputs, and help without file writes.
- Keep date-dependent tests deterministic and verify numeric option parsing,
  including negative inputs.
- Run checks appropriate to the change and report the result. Documentation-only
  changes do not require application tests.
