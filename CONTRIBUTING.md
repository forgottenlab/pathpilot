# Contributing to PathPilot

PathPilot is developed and tested on Windows 11 with Python 3.12 or 3.13.

## Development setup

Use a dedicated virtual environment or Conda environment. Do not install test
tools into an unrelated runtime or base environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pip install -e ".[gui]"
```

For core-only work, `python -m pip install -e ".[dev]"` deliberately does not
install PySide6. Use `.[all]` when both GUI and development dependencies are
needed.

## Safety rules

- Never commit or execute a real installer fixture. Use inert `.exe`/`.msi`
  files and mocks.
- Never commit real user configuration, paths, tokens, keys, or logs.
- Set a temporary `PATHPILOT_HOME` for every test or manual smoke check.
- GUI tests must set `QT_QPA_PLATFORM=offscreen`.
- Do not describe `launched` as installed, completed, or successful.

## Branches and commits

Use focused branches such as `fix/...`, `feat/...`, `test/...`, or `chore/...`.
Use Conventional Commit-style messages, for example `fix: reject unsafe root`.

## Required checks before a pull request

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:PATHPILOT_HOME = Join-Path $env:TEMP "pathpilot-contributor-test"
python -m pytest -q -p no:cacheprovider
python -m compileall -q app tests
pathpilot --help
pathpilot doctor
pathpilot test
.\scripts\full_check.ps1
python -m build
git diff --check
```

The full check uses temporary roots and inert fixtures. Review the wheel and
sdist contents before proposing a release.
