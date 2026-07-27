# PathPilot for Windows

[English](README.md) | [简体中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-blue)](https://www.python.org/)
[![Windows CI](https://github.com/forgottenlab/pathpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/forgottenlab/pathpilot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

PathPilot 是一个面向 Windows 的下载整理与安全安装建议治理工具。它只监听用户明确配置的来源目录，将已稳定的文件先移入受管 Incoming 目录，再按文档、代码、压缩包、媒体和安装包进行分类。

遇到 `.exe` 或 `.msi` 时，PathPilot 只生成保守、可审查的安装建议。文件名、识别出的安装器家族和命令预览都不能建立信任。0.2.2 仍属于 alpha/prototype，建议先使用不可执行 fixture 验证规则，再评估实际使用方式。

## 🎯 PathPilot 解决什么问题

下载目录很容易混入文档、源码、压缩包、媒体和安装器。PathPilot 提供一条可观察的整理链路：稳定文件先经过 Incoming，再进入受管分类目录；安装器启动则始终受明确的安全边界约束。

它适合希望获得以下能力的 Windows 用户：

- 以一致规则整理新下载的文件；
- 通过可审计的 pending 队列管理安装建议；
- 在 CLI 和可选 GUI 中使用同一套安全检查；
- 在开发和 CI 中完整隔离配置与行为测试。

| 能力 | 当前行为 |
|---|---|
| 文件整理 | 稳定文件先进入 Incoming，再进行最终分类 |
| 安装器处理 | `.exe` 和 `.msi` 进入 `_IncomingInstallers` 并生成建议 |
| 命令执行 | 完成路径约束校验后，以结构化 argv 和 `shell=False` 启动 |
| 状态持久化 | JSON 原子写入，并使用有限超时的进程间锁 |
| 诊断与测试 | `doctor` 只读；`test` 使用完全隔离的临时状态 |

## 📋 环境要求

- Windows 11
- Python 3.12 或 3.13
- 普通安装推荐使用 `pipx`

PathPilot 当前以 Windows 为主，不承诺 Linux 或 macOS 上具有一致的 watcher 行为。

## 📦 安装

如果不需要 Qt 界面，请使用 CLI-only 安装；这种方式不会安装 PySide6：

```powershell
python -m pip install --user pipx
python -m pipx install git+https://github.com/forgottenlab/pathpilot.git
```

需要运行 `pathpilot ui` 时，请安装 GUI extra：

```powershell
python -m pipx install "pathpilot[gui] @ git+https://github.com/forgottenlab/pathpilot.git"
```

从本地 checkout 安装：

```powershell
python -m pipx install .
python -m pipx install ".[gui]"
```

安装脚本默认安装 CLI 与 GUI；使用 `-CliOnly` 可只安装核心 CLI：

```powershell
.\scripts\install.ps1
.\scripts\install.ps1 -CliOnly
.\scripts\update.ps1
.\scripts\uninstall.ps1
```

卸载脚本默认只移除 pipx 程序。只有显式传入 `-RemoveUserConfig` 并确认后，才会删除 PathPilot 用户状态；受管 Downloads 和 Apps 目录不会被卸载脚本删除。

## 🚀 首次运行

建议先查看状态并了解命令入口：

```powershell
pathpilot status
pathpilot doctor
pathpilot test
pathpilot commands
```

- `doctor` 执行只读诊断，不创建或重写配置。
- `test` 使用临时 `PATHPILOT_HOME` 和临时受管根目录执行隔离行为测试。
- `watch` 持续监听已配置的来源目录，直到用户主动停止。
- `ui` 启动可选 GUI。CLI-only 环境中会返回非零退出码，给出清晰的 `pathpilot[gui]` 提示，并且不显示 Python traceback。

启动 watcher 前，先确认当前根目录和来源目录：

```powershell
pathpilot config show
pathpilot sources list
pathpilot watch
```

## 🧭 命令参考

| 命令 | 作用 |
|---|---|
| `pathpilot` | 显示命令指引 |
| `pathpilot guide` | 显示详细命令指引 |
| `pathpilot commands` | 显示同一份受维护的命令指引 |
| `pathpilot doctor` | 执行只读诊断 |
| `pathpilot test` | 执行隔离行为测试 |
| `pathpilot status` | 显示当前配置和队列状态 |
| `pathpilot watch` | 持续监听已配置的来源目录 |
| `pathpilot ui` | 启动可选 GUI |
| `pathpilot version`、`pathpilot -v`、`pathpilot --version` | 显示版本 |
| `pathpilot config show` | 显示配置 |
| `pathpilot config set-root <path>` | 设置受管根目录 |
| `pathpilot config reset-root` | 恢复自动选择根目录 |
| `pathpilot sources list` | 列出来源目录 |
| `pathpilot sources add <path>` | 添加来源目录 |
| `pathpilot sources remove <path>` | 移除来源目录 |
| `pathpilot installs list [--all]` | 列出安装建议 |
| `pathpilot installs detail <id>` | 显示建议详情 |
| `pathpilot installs run <id> --force` | 明确确认启动符合条件的安装器 |
| `pathpilot installs skip <id>` | 跳过 pending 建议 |
| `pathpilot installs open <id>` | 打开安装器所在目录 |

非法输入和安全拒绝会返回非零退出码。`--force` 只确认启动意图，不能绕过 installer containment、Apps target containment、legacy 记录拒绝或结构化参数校验。

## 🌐 CLI 语言

PathPilot 自行维护的 CLI 输出支持中文 `zh`、英文 `en` 和先中文后英文的双语 `bi` 模式：

```powershell
pathpilot --lang zh status
pathpilot --lang en doctor
pathpilot --lang bi installs list --all
```

Typer 自动生成的部分框架 help 文本可能仍为英文。

## 🗂 状态目录与 PATHPILOT_HOME

默认用户状态位于：

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

设置 `PATHPILOT_HOME` 后，配置、数据、日志、pending 队列和默认运行时路径都会被隔离。相关路径在运行时动态解析，不会在模块 import 时永久缓存真实用户目录。

开发和测试必须使用临时值：

```powershell
$env:PATHPILOT_HOME = Join-Path $env:TEMP "pathpilot-dev"
pathpilot doctor
```

## 🛡 安装器安全模型

PathPilot 将分类结果视为建议，而不是信任判断：

- 所有安装建议默认都是 `mode=suggest`、`status=pending`；
- 文件名和 installer family 只影响推荐，不建立信任；
- `preview` 只用于展示，绝不会作为 shell 命令执行；
- 只有 command 字符串的 `legacy_unsafe` 旧记录不可执行；
- 安装器必须位于受管 `_IncomingInstallers` 内；
- 目标目录必须位于受管 `Apps` 内；
- `--force` 不能绕过任何路径约束或记录校验；
- PathPilot 当前不提供 Authenticode publisher/signature 信任判断；
- PathPilot 当前不跟踪安装是否完成。

| 状态 | 含义 |
|---|---|
| `pending` | 等待用户明确操作 |
| `skipped` | 用户已跳过 |
| `blocked` | 被安全检查拒绝 |
| `launch_failed` | 进程未能启动 |
| `launched` | 只表示进程已经启动，不表示 installed、completed 或 success |
| `legacy_unsafe` | 旧式 command-only 记录，始终不可执行 |

有关私下报告漏洞的方式和完整安全边界，请参阅 [SECURITY.md](SECURITY.md)。

## 🧪 开发、测试与 CI

请使用专用 venv 或 Conda 环境，并通过 extra 安装开发和 GUI 依赖：

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

Windows CI 在 Python 3.12 和 3.13 上运行核心测试，检查 PowerShell 语法，构建 wheel 与 sdist，验证全新的 CLI-only wheel，并单独执行一次 GUI extra offscreen smoke。所有测试都使用临时状态和不可执行 fixture，不会运行真实安装器。

发行物检查要求同时包含 `README.md` 和 `README.zh-CN.md`，并排除 `.ai`、tests、运行时 data、日志、备份和用户配置。

## 🗺 路线图

后续版本可以改进 watcher 重试、跨磁盘行为和 GUI 交互覆盖。Authenticode 判断与安装完成跟踪不属于当前 0.2.2 边界，也不能描述为已经实现。

## ⚠️ 原型限制

- 当前以 Windows 为主，不承诺 Linux 或 macOS watcher 行为一致。
- 跨磁盘移动和所有交互式 GUI 路径尚未实现完整自动化覆盖。
- 不提供 Authenticode 信任判断。
- 不提供安装完成状态跟踪。
- 文件被分类、生成建议或标记为 `launched`，都不能证明安装器安全或安装成功。

## 📚 项目规范

- [CONTRIBUTING.md](CONTRIBUTING.md) 说明开发流程和 PR 门禁。
- [SECURITY.md](SECURITY.md) 说明漏洞私下报告方式与安全边界。
- [CHANGELOG.md](CHANGELOG.md) 记录版本变化。

## 📄 许可证

PathPilot 采用 [MIT License](LICENSE)。

Copyright (c) 2026 forgottenlab.
