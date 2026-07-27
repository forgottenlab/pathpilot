# PathPilot for Windows

[English](README.md) | [简体中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-blue)](https://www.python.org/)
[![Windows CI](https://github.com/forgottenlab/pathpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/forgottenlab/pathpilot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

PathPilot is a Windows download organizer and safe installer-suggestion governance tool. It watches only the source directories you configure, moves stable files through a managed Incoming directory, and classifies documents, code, archives, media, and installers.

For `.exe` and `.msi` files, PathPilot creates conservative, reviewable suggestions. It does not trust an installer because of its file name, detected family, or command preview. Version 0.2.2 is an alpha/prototype intended for careful evaluation with inert fixtures before real-world use.

## 🎯 What PathPilot solves

Download folders quickly become a mixture of documents, source files, archives, media, and installers. PathPilot provides one observable flow for moving stable files into a managed tree while keeping installer launch behind an explicit security boundary.

PathPilot is most useful for Windows users who want:

- repeatable classification of newly downloaded files;
- an auditable pending queue for installer suggestions;
- the same safety checks in the CLI and optional GUI;
- isolated configuration and behavioral testing for development or CI.

| Capability | Current behavior |
|---|---|
| File organization | Stable files pass through Incoming before final classification |
| Installer handling | `.exe` and `.msi` files move to `_IncomingInstallers` and create suggestions |
| Execution | Structured argv with `shell=False`, after containment validation |
| State | Atomic JSON writes with finite-time process locks |
| Diagnostics | `doctor` is read-only; `test` uses fully isolated temporary state |

## 📋 Requirements

- Windows 11
- Python 3.12 or 3.13
- `pipx` for normal installation

PathPilot is Windows-first. Equivalent watcher behavior on Linux or macOS is not currently claimed.

## 📦 Installation

Install the CLI-only package when you do not need the Qt interface. This does not install PySide6:

```powershell
python -m pip install --user pipx
python -m pipx install git+https://github.com/forgottenlab/pathpilot.git
```

Install the GUI extra when you need `pathpilot ui`:

```powershell
python -m pipx install "pathpilot[gui] @ git+https://github.com/forgottenlab/pathpilot.git"
```

From a local checkout:

```powershell
python -m pipx install .
python -m pipx install ".[gui]"
```

The installation script installs the CLI and GUI by default. Use `-CliOnly` for the core CLI:

```powershell
.\scripts\install.ps1
.\scripts\install.ps1 -CliOnly
.\scripts\update.ps1
.\scripts\uninstall.ps1
```

Uninstall removes only the pipx application by default. It removes PathPilot user state only when `-RemoveUserConfig` is explicitly supplied and confirmed. It never deletes the managed Downloads or Apps trees.

## 🚀 First run

Start by checking status and learning the command surface:

```powershell
pathpilot status
pathpilot doctor
pathpilot test
pathpilot commands
```

- `doctor` performs read-only diagnostics. It does not create or rewrite configuration.
- `test` runs an isolated behavior check with a temporary `PATHPILOT_HOME` and managed root.
- `watch` continuously monitors configured sources until you stop it.
- `ui` starts the optional GUI. In a CLI-only installation it exits nonzero with a clear `pathpilot[gui]` hint and no Python traceback.

Before starting the watcher, review the active root and sources:

```powershell
pathpilot config show
pathpilot sources list
pathpilot watch
```

## 🧭 Command reference

| Command | Purpose |
|---|---|
| `pathpilot` | Show the command guide |
| `pathpilot guide` | Show the detailed command guide |
| `pathpilot commands` | Show the same maintained command guide |
| `pathpilot doctor` | Run read-only diagnostics |
| `pathpilot test` | Run an isolated behavior test |
| `pathpilot status` | Show current configuration and queue status |
| `pathpilot watch` | Continuously watch configured source directories |
| `pathpilot ui` | Start the optional GUI |
| `pathpilot version`, `pathpilot -v`, `pathpilot --version` | Show the version |
| `pathpilot config show` | Show configuration |
| `pathpilot config set-root <path>` | Set the managed root |
| `pathpilot config reset-root` | Restore automatic root selection |
| `pathpilot sources list` | List source directories |
| `pathpilot sources add <path>` | Add a source directory |
| `pathpilot sources remove <path>` | Remove a source directory |
| `pathpilot installs list [--all]` | List installer suggestions |
| `pathpilot installs detail <id>` | Show suggestion details |
| `pathpilot installs run <id> --force` | Explicitly confirm an eligible launch |
| `pathpilot installs skip <id>` | Skip a pending suggestion |
| `pathpilot installs open <id>` | Open the installer's containing directory |

Invalid input and safety rejection return nonzero exit codes. `--force` confirms launch intent only; it cannot bypass installer containment, Apps target containment, legacy-record rejection, or structured-argument validation.

## 🌐 CLI languages

Maintained CLI output supports `zh`, `en`, and Chinese-first bilingual `bi` modes:

```powershell
pathpilot --lang zh status
pathpilot --lang en doctor
pathpilot --lang bi installs list --all
```

Some framework-generated Typer help text may remain in English.

## 🗂 State and PATHPILOT_HOME

Default user state is stored under:

```text
~/.pathpilot/
├─ config/
│  ├─ settings.json
│  ├─ rules.json
│  └─ installer_rules.json
└─ data/
   ├─ pending_installs.json
   └─ logs/pathpilot.log
```

Set `PATHPILOT_HOME` to isolate configuration, data, logs, the pending queue, and default runtime paths. Paths are resolved dynamically rather than permanently cached when a module is imported.

Development and tests must use a temporary value:

```powershell
$env:PATHPILOT_HOME = Join-Path $env:TEMP "pathpilot-dev"
pathpilot doctor
```

## 🛡 Installer safety model

PathPilot treats classification as a suggestion, not a trust decision:

- every installer suggestion defaults to `mode=suggest` and `status=pending`;
- file names and installer-family detection influence recommendations only;
- `preview` is display-only and is never executed as a shell command;
- `legacy_unsafe` command-only records cannot be executed;
- the installer must remain under managed `_IncomingInstallers`;
- the target must remain under the managed `Apps` directory;
- `--force` cannot bypass any containment or record validation;
- PathPilot does not provide Authenticode publisher/signature trust decisions;
- PathPilot does not track installation completion.

| Status | Meaning |
|---|---|
| `pending` | Awaiting explicit user action |
| `skipped` | Skipped by the user |
| `blocked` | Rejected by a safety check |
| `launch_failed` | The process could not be started |
| `launched` | The process started only; this does not mean installed, completed, or successful |
| `legacy_unsafe` | Legacy command-only record; never executable |

See [SECURITY.md](SECURITY.md) for private vulnerability reporting and the complete current boundary.

## 🧪 Development, testing, and CI

Use a dedicated virtual environment or Conda environment. Install development and GUI dependencies through extras:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[all]"
$env:QT_QPA_PLATFORM = "offscreen"
$env:PATHPILOT_HOME = Join-Path $env:TEMP "pathpilot-dev"
python -m pytest -q -p no:cacheprovider
python -m build
.\scripts\full_check.ps1
```

Windows CI runs core tests on Python 3.12 and 3.13, checks PowerShell syntax, builds wheel and sdist artifacts, installs a fresh CLI-only wheel, and runs a separate GUI extra offscreen smoke. Tests use temporary state and inert fixtures; they never run real installers.

Release artifacts are checked to include both `README.md` and `README.zh-CN.md` while excluding `.ai`, tests, runtime data, logs, backups, and user configuration.

## 🗺 Roadmap

Future work may improve watcher retries, cross-volume behavior, and GUI interaction coverage. Authenticode evaluation and installation-completion tracking are deliberately outside the current 0.2.2 boundary and are not implemented claims.

## ⚠️ Prototype limitations

- Windows-first; Linux and macOS watcher parity is not claimed.
- Cross-volume moves and every interactive GUI path are not fully automated in tests.
- There is no Authenticode trust decision.
- There is no installation-completion tracking.
- Classification, suggestion, or `launched` status never proves that an installer is safe or successfully installed.

## 📚 Project policies

- [CONTRIBUTING.md](CONTRIBUTING.md) explains the development and pull-request gates.
- [SECURITY.md](SECURITY.md) explains private vulnerability reporting and security boundaries.
- [CHANGELOG.md](CHANGELOG.md) records release changes.

## 📄 License

PathPilot is released under the [MIT License](LICENSE).

Copyright (c) 2026 forgottenlab.
