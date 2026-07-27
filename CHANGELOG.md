# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.2] - 2026-07-26

### Added

- Shared path-safety policy for roots, sources, installer containment, and Apps targets.
- Atomic JSON state persistence with process locks and corrupt-file retention.
- Windows CI for Python 3.12 and 3.13.
- Isolated queue, watcher, doctor, CLI, and packaging behavior tests.

### Changed

- Installer launch state now uses structured executable and argument lists.
- Every installer rule defaults to `suggest` mode.
- `doctor` is read-only and `test` runs isolated behavior checks.
- `PATHPILOT_HOME` is resolved dynamically and isolates runtime state.
- CLI and GUI share the same persistence and path-safety boundaries.
- PySide6 is provided through the optional `gui` extra instead of the core CLI install.

### Fixed

- Removed shell-command installer execution.
- Blocked legacy command-only records from execution.
- Prevented concurrent JSON writers from overwriting each other.
- Prevented corrupt configuration from being silently replaced by defaults.
- Prevented watcher and full-check tests from modifying real user state.

### Security

- Installer files must be contained by `_IncomingInstallers`.
- Installation targets must be proper children of the active `Apps` root.
- `--force` cannot bypass containment or structured-record validation.

### Limitations

- No Authenticode trust decision is implemented.
- A `launched` record does not indicate installation completion or success.

## [0.2.1]

- Initial Windows prototype with CLI, GUI prototype, watcher, file
  classification, and install suggestion queue.

[Unreleased]: https://github.com/forgottenlab/pathpilot/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/forgottenlab/pathpilot/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/forgottenlab/pathpilot/releases/tag/v0.2.1
