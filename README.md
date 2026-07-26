# PathPilot for Windows

> Windows 下载整理与安全安装建议治理工具。<br>
> A Windows download organizer and safe installer-suggestion governance tool.

[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-blue)](https://www.python.org/)
[![Windows CI](https://github.com/forgottenlab/pathpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/forgottenlab/pathpilot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

PathPilot 监听用户明确配置的下载来源，把稳定文件收口到受管 Incoming
目录，再按文档、代码、压缩包、媒体或安装包分类。对于 `.exe`/`.msi`，它只生成
保守的安装建议，不会因为文件名或预览命令而自动信任安装器。

PathPilot watches explicitly configured download sources, moves stable files
through a managed Incoming directory, and classifies documents, code, archives,
media, and installers. For `.exe`/`.msi`, it creates conservative suggestions;
file names and command previews never establish trust.

PathPilot 0.2.2 仍是 Windows alpha/prototype。请先使用不可执行 fixture 验证你的规则。
PathPilot 0.2.2 remains a Windows alpha/prototype. Validate rules with inert fixtures first.

## Requirements / 环境要求

- Windows 11
- Python 3.12 or 3.13
- `pipx` for normal installation

## Installation / 安装

CLI-only 安装不包含 PySide6：
CLI-only installation does not include PySide6:

```powershell
python -m pip install --user pipx
python -m pipx install git+https://github.com/forgottenlab/pathpilot.git
```

带 GUI 的完整安装：
Full installation with the optional GUI:

```powershell
python -m pipx install "pathpilot[gui] @ git+https://github.com/forgottenlab/pathpilot.git"
```

从本地 checkout 安装：
Install from a local checkout:

```powershell
python -m pipx install .
python -m pipx install ".[gui]"
```

安装脚本默认安装 CLI + GUI；`-CliOnly` 只安装核心 CLI：
The install script defaults to CLI + GUI; `-CliOnly` installs the core CLI only:

```powershell
.\scripts\install.ps1
.\scripts\install.ps1 -CliOnly
.\scripts\update.ps1
.\scripts\uninstall.ps1
```

卸载默认只删除 pipx 程序，不删除用户配置或受管文件。只有显式指定
`-RemoveUserConfig` 并确认时才删除 PathPilot 用户状态。

Uninstall removes only the pipx application by default. User state is removed
only with an explicit, confirmed `-RemoveUserConfig` option. Managed Downloads
and Apps trees are never removed by the uninstaller.

## First run / 首次运行

```powershell
pathpilot status
pathpilot doctor
pathpilot test
pathpilot commands
```

- `doctor`：只读诊断，不创建或重写配置。<br>
  `doctor`: read-only diagnostics; it does not create or rewrite state.
- `test`：在临时 `PATHPILOT_HOME` 和临时受管根目录中执行隔离行为测试。<br>
  `test`: isolated behavior checks using temporary state and managed roots.
- `watch`：持续监听配置的来源目录，直到用户停止。<br>
  `watch`: continuously watches configured sources until stopped.

CLI-only 环境运行 `pathpilot ui` 会返回非零退出码和清晰的 `pathpilot[gui]`
安装提示，不输出 Python traceback。

In a CLI-only environment, `pathpilot ui` exits nonzero with a clear
`pathpilot[gui]` installation hint and no Python traceback.

## Commands / 命令

| Command | 中文说明 / English description |
|---|---|
| `pathpilot` | 显示完整指引 / Show the command guide |
| `pathpilot guide`, `pathpilot commands` | 命令指引 / Command guide |
| `pathpilot doctor` | 只读诊断 / Read-only diagnostics |
| `pathpilot test` | 隔离行为测试 / Isolated behavior test |
| `pathpilot status` | 当前状态 / Current status |
| `pathpilot watch` | 持续监听 / Continuous watcher |
| `pathpilot ui` | 可选 GUI / Optional GUI |
| `pathpilot version`, `-v`, `--version` | 版本 / Version |
| `pathpilot config show` | 显示配置 / Show configuration |
| `pathpilot config set-root <path>` | 设置根目录 / Set root |
| `pathpilot config reset-root` | 恢复自动选择 / Restore auto-selection |
| `pathpilot sources list` | 来源列表 / List sources |
| `pathpilot sources add <path>` | 添加来源 / Add source |
| `pathpilot sources remove <path>` | 移除来源 / Remove source |
| `pathpilot installs list [--all]` | 建议列表 / List suggestions |
| `pathpilot installs detail <id>` | 建议详情 / Suggestion details |
| `pathpilot installs run <id> --force` | 显式确认启动 / Explicitly confirm launch |
| `pathpilot installs skip <id>` | 跳过建议 / Skip suggestion |
| `pathpilot installs open <id>` | 打开安装包目录 / Open installer directory |

`--force` 只确认启动，不能绕过 installer containment、Apps target containment、
legacy record 或结构化参数检查。

`--force` confirms launch only. It cannot bypass installer containment, Apps
target containment, legacy-record rejection, or structured-argument checks.

## Language / 语言

PathPilot 自维护的 CLI 文本支持中文、英文和先中文后英文的双语模式：
Maintained CLI output supports Chinese, English, and Chinese-first bilingual output:

```powershell
pathpilot --lang zh status
pathpilot --lang en doctor
pathpilot --lang bi installs list --all
```

Typer 自动生成的部分框架 help 文本可能保持英文。
Some framework-generated Typer help text may remain English.

## State and PATHPILOT_HOME / 状态与隔离

默认用户状态位于：
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

测试和开发必须设置临时 `PATHPILOT_HOME`。该变量动态隔离配置、数据、日志、
pending queue 和默认 runtime paths，不会在 import 时缓存真实用户目录。

Tests and development must set a temporary `PATHPILOT_HOME`. It dynamically
isolates configuration, data, logs, the pending queue, and default runtime paths.

## Installer safety and states / 安装器安全与状态

- 所有建议默认 `mode=suggest`；文件名和 installer family 只影响推荐。
- `preview` 仅展示，绝不作为 shell 字符串执行。
- `legacy_unsafe` command-only 记录不可执行。
- installer 必须位于受管 `_IncomingInstallers`，target 必须是 `Apps` 的子目录。
- PathPilot 当前不提供 Authenticode publisher/signature 信任判断。

- Every suggestion defaults to `mode=suggest`; names and families affect recommendations only.
- `preview` is display-only and is never executed as a shell string.
- `legacy_unsafe` command-only records cannot run.
- Installers must stay in `_IncomingInstallers`; targets must be children of `Apps`.
- PathPilot does not currently provide Authenticode publisher/signature trust decisions.

| Status | Meaning |
|---|---|
| `pending` | 等待明确操作 / Awaiting explicit action |
| `skipped` | 用户跳过 / Skipped by the user |
| `blocked` | 安全检查拒绝 / Rejected by safety checks |
| `launch_failed` | 进程未能启动 / Process failed to start |
| `launched` | 仅表示进程启动，不表示 installed/completed/success / Process started only; not installation success |
| `legacy_unsafe` | 旧 command-only 记录，不可执行 / Legacy command-only record; not executable |

See [SECURITY.md](SECURITY.md) for private vulnerability reporting and the full boundary.

## Development and CI / 开发与 CI

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

Windows CI runs the core test matrix on Python 3.12 and 3.13, builds wheel and
sdist artifacts, tests a CLI-only wheel, and runs one separate GUI offscreen smoke.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md).

## Prototype limitations / 原型限制

- Windows-first; Linux/macOS watcher parity is not claimed.
- Cross-volume moves and all interactive GUI paths are not fully automated.
- No Authenticode trust decision.
- No installation-completion tracking.
- No claim that an installer is safe merely because it was classified or launched.

## License / 许可证

PathPilot is licensed under the [MIT License](LICENSE).

Copyright (c) 2026 forgottenlab.
