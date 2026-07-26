# 🧭 PathPilot for Windows

> Windows 下载与安装路径治理助手  
> A Windows download and installation path governance assistant.

![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4)
![CLI](https://img.shields.io/badge/CLI-Typer%20%2B%20Rich-green)
![GUI](https://img.shields.io/badge/GUI-PySide6-purple)
![Status](https://img.shields.io/badge/Status-Prototype-orange)

---

## ✨ 项目简介 / Overview

**PathPilot** 是一个面向 Windows 用户的下载与安装路径治理工具。

它可以监听浏览器、网盘、聊天软件等下载目录，将新文件统一收口、自动分类，并对安装包生成推荐安装路径，帮助用户减少 C 盘压力，让下载、归档和安装路径更加清晰可控。

**PathPilot** is a Windows-first utility for download and installation path governance.

It watches download folders, funnels new files into a managed workspace, classifies them by type, and creates install suggestions for installer packages, helping users avoid filling the system drive and keeping files organized.

---

## 🎯 为什么需要它 / Why PathPilot?

很多 Windows 软件默认会把文件下载到用户目录，或者默认安装到 C 盘。久而久之，用户会遇到：

- 🧱 C 盘越来越满
- 🧩 下载目录混乱
- 📦 安装包、压缩包、代码文件、图片、文档混在一起
- 🧭 想迁移软件却担心破坏运行环境
- 🧰 普通用户不清楚哪些文件能安全移动，哪些文件不应该移动

PathPilot 的目标不是粗暴移动已安装软件，而是优先在**下载和安装之前**建立秩序。

Many Windows applications download files into the user profile or install to the system drive by default. Over time, users may face:

- 🧱 A crowded C drive
- 🧩 A messy Downloads folder
- 📦 Installers, archives, code files, images, and documents mixed together
- 🧭 Concerns about breaking installed software when moving folders
- 🧰 Uncertainty about what can be safely moved

PathPilot focuses on creating order **before downloads and installations become a problem**.

---

## 🚀 当前能力 / Current Features

### 📥 下载目录监听 / Download Folder Watching

- 监听系统下载目录，例如 `C:/Users/<you>/Downloads`
- 支持添加额外来源目录，例如网盘、微信、浏览器下载目录
- 自动将新文件收口到 PathPilot 工作区

- Watches the system Downloads folder, such as `C:/Users/<you>/Downloads`
- Supports additional source folders, such as cloud-drive, chat-app, and browser download folders
- Funnels new files into the PathPilot workspace

---

### 🗂 自动分类 / File Classification

默认支持以下类型：

| 类型 / Type | 扩展名 / Extensions | 默认目录 / Default Target |
|---|---|---|
| 🧩 安装包 / Installers | `.exe`, `.msi` | `01-Software/_IncomingInstallers` |
| 🗜 压缩包 / Archives | `.zip`, `.7z`, `.rar` | `07-Archives/_IncomingArchives` |
| 🖼 图片 / Images | `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp` | `03-Media/Images` |
| 🎞 视频 / Videos | `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv` | `03-Media/Videos` |
| 📄 文档 / Documents | `.pdf`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx`, `.txt` | `05-Documents/Mixed` |
| 🐍 Python 代码 / Python Code | `.py`, `.ipynb` | `06-Code/Python` |
| ☕ Java 代码 / Java Code | `.java`, `.jar` | `06-Code/Java` |

---

### 🧭 自动选择根目录 / Smart Root Selection

如果用户没有手动设置根目录，PathPilot 会自动选择：

> 非系统盘中剩余空间最大的磁盘  
> The non-system drive with the largest free space

例如：

```text
G:/PathPilot
├─ Downloads
│  ├─ 00-Incoming
│  ├─ 01-Software
│  ├─ 03-Media
│  ├─ 05-Documents
│  ├─ 06-Code
│  └─ 07-Archives
└─ Apps
   ├─ General
   └─ Professional
```

---

### 📦 安装建议队列 / Install Suggestions

当检测到安装包后，PathPilot 会生成安装建议：

- 安装包路径
- 推荐安装目录
- 安装器类型
- 只读命令预览（不作为 shell 命令执行）
- 当前状态：`pending / skipped / blocked / launched / launch_failed / legacy_unsafe`
- 所有建议默认为 `suggest`，必须由用户明确确认
- 文件名匹配只用于推荐信息，不表示安装器可信

When an installer package is detected, PathPilot creates an install suggestion containing:

- Installer path
- Recommended target directory
- Installer family
- Read-only command preview (never executed as a shell command)
- Current status: `pending / skipped / blocked / launched / launch_failed / legacy_unsafe`
- Every suggestion defaults to `suggest` and requires explicit confirmation
- Filename matching affects recommendations only; it does not establish installer trust

> 安装执行仍属于 prototype。`launched` 只表示安装器进程已启动，不表示安装成功。
>
> Installer execution remains a prototype. `launched` means only that the installer process started; it does not mean installation succeeded.

示例 / Example:

```powershell
pathpilot installs list --all
pathpilot installs detail 1
```

---

### 🖥 CLI + GUI

PathPilot 同时提供：

- 🧪 命令行工具：适合开发者、测试和高级用户
- 🪟 PySide6 图形界面：适合普通用户后续使用

PathPilot provides both:

- 🧪 A CLI for developers, testing, and power users
- 🪟 A PySide6 GUI prototype for regular users

---

## 📦 安装 / Installation

> 首次安装前系统还不认识 `pathpilot` 命令，所以需要通过安装脚本或 pipx 安装。  
> Before the first installation, your system does not know the `pathpilot` command yet, so you need to install it through the install script or pipx.

### 方式一：从 GitHub 安装 / Install from GitHub

```powershell
python -m pip install --user pipx
python -m pipx ensurepath
python -m pipx install git+https://github.com/forgottenlab/pathpilot.git
```

安装后重新打开 PowerShell，然后测试：

```powershell
pathpilot -v
pathpilot doctor
```

---

### 方式二：本地开发安装 / Local Development Install

```powershell
git clone https://github.com/forgottenlab/pathpilot.git
cd pathpilot
python -m pipx install --force .
```

---

### 方式三：安装脚本 / Install Script

如果你已经克隆了仓库，可以运行：

```powershell
.\scripts\install.ps1
```

更新：

```powershell
.\scripts\update.ps1
```

卸载：

```powershell
.\scripts\uninstall.ps1
```

---

## 🧪 快速自检 / Quick Check

```powershell
pathpilot -v
pathpilot commands
pathpilot doctor
pathpilot test
pathpilot status
```

`pathpilot doctor` is read-only: it reports missing or corrupt JSON state but
does not create directories or rewrite configuration. `pathpilot test` runs an
isolated behavior check under temporary `PATHPILOT_HOME` and managed roots.

For development and automation, setting `PATHPILOT_HOME` isolates configuration,
data, logs, the pending installer queue, and default runtime paths from the real
user profile.

如果全部正常，可以启动监听：

```powershell
pathpilot watch
```

打开图形界面：

```powershell
pathpilot ui
```

---

## 🧾 常用命令 / Common Commands

| 命令 / Command | 说明 / Description |
|---|---|
| `pathpilot` | 显示基础指引 / Show quick guide |
| `pathpilot guide` | 显示基础使用指引 / Show quick guide |
| `pathpilot commands` | 查看常用命令 / Show common commands |
| `pathpilot doctor` | 检查配置、目录、规则和依赖 / Check config, directories, rules and dependencies |
| `pathpilot test` | 运行基础自检 / Run basic self-test |
| `pathpilot status` | 查看运行状态 / Show runtime status |
| `pathpilot watch` | 启动下载监听 / Start watching folders |
| `pathpilot ui` | 打开图形界面 / Open GUI |
| `pathpilot config show` | 查看配置 / Show config |
| `pathpilot config set-root <path>` | 设置根目录 / Set root directory |
| `pathpilot config reset-root` | 重置为自动选择根目录 / Reset root directory auto-selection |
| `pathpilot sources list` | 查看监听来源目录 / List source directories |
| `pathpilot sources add <path>` | 添加监听目录 / Add source directory |
| `pathpilot sources remove <path>` | 移除监听目录 / Remove source directory |
| `pathpilot installs list` | 查看待处理安装建议 / List pending install suggestions |
| `pathpilot installs list --all` | 查看全部安装建议 / List all install suggestions |
| `pathpilot installs detail <id>` | 查看安装建议详情 / Show install suggestion details |
| `pathpilot installs run <id>` | 执行安装建议 / Run install suggestion |
| `pathpilot installs run <id> --force` | 强制执行 suggest 建议 / Force-run a suggest-mode suggestion |
| `pathpilot installs skip <id>` | 跳过安装建议 / Skip install suggestion |
| `pathpilot --lang en guide` | 临时切换英文输出 / Temporarily switch to English |
| `pathpilot --lang bi doctor` | 临时切换双语输出 / Temporarily switch to bilingual output |

---

## 🌐 多语言输出 / Multilingual Output

PathPilot 的 CLI 支持三种输出语言：

| 参数 / Option | 说明 / Description |
|---|---|
| `--lang zh` | 中文输出 / Chinese output |
| `--lang en` | 英文输出 / English output |
| `--lang bi` | 双语输出 / Bilingual output |

示例 / Examples:

```powershell
pathpilot --lang en guide
pathpilot --lang bi doctor
```

---

## ⚙️ 配置目录 / Configuration

PathPilot 不把用户配置写进程序安装目录，而是使用用户级目录：

```text
C:/Users/<you>/.pathpilot
├─ config
│  ├─ settings.json
│  ├─ rules.json
│  └─ installer_rules.json
└─ data
   ├─ pending_installs.json
   └─ logs
```

这意味着：

- ✅ 程序升级不会覆盖用户配置
- ✅ pipx 安装后也能正常运行
- ✅ 后续打包成 exe 时仍然可以复用同一套配置结构

This means:

- ✅ Program upgrades do not overwrite user configuration
- ✅ pipx installation works without relying on source directories
- ✅ Future Windows executable packaging can reuse the same configuration structure

---

## 🛡 安全边界 / Safety Boundary

PathPilot 当前遵循保守策略：

- ✅ 优先处理“刚下载的文件”
- ✅ 优先处理“尚未安装的软件包”
- ✅ 对安装包生成建议，而不是盲目强制安装
- ✅ 不直接迁移 `Program Files` 中已安装软件
- ✅ 不上传用户文件、路径或安装包
- ✅ 不修改系统关键目录

PathPilot is designed to be conservative:

- ✅ It focuses on newly downloaded files
- ✅ It focuses on not-yet-installed installer packages
- ✅ It creates install suggestions instead of blindly forcing actions
- ✅ It does not directly migrate already installed software in `Program Files`
- ✅ It does not upload user files, local paths, or installer packages
- ✅ It does not modify critical system directories

---

## 🧱 项目结构 / Project Structure

```text
PathPilot/
├─ app/
│  ├─ core/           # 配置、路径、日志、控制台输出 / config, paths, logs, console output
│  ├─ files/          # 文件监听、分类、移动 / watcher, classifier, mover
│  ├─ installers/     # 安装器检测、安装建议、执行器 / detector, suggestions, runner
│  ├─ gui/            # PySide6 图形界面 / PySide6 GUI
│  ├─ cli.py          # Typer CLI 入口 / Typer CLI entry
│  ├─ diagnostics.py  # doctor / test 自检逻辑 / diagnostics and self-test
│  └─ guide.py        # 命令指引 / command guide
├─ scripts/
│  ├─ install.ps1
│  ├─ update.ps1
│  ├─ uninstall.ps1
│  └─ full_check.ps1
├─ pyproject.toml
├─ requirements.txt
└─ README.md
```

---

## 🧪 开发测试 / Development Test

完整验收测试：

```powershell
.\scripts\full_check.ps1
```

跳过 watcher 测试：

```powershell
.\scripts\full_check.ps1 -SkipWatcher
```

`full_check.ps1` always uses a unique temporary `PATHPILOT_HOME`, source, and
managed root. Its watcher fixture files are inert and the script never launches
an installer.

---

## 🗺 Roadmap

- [x] CLI 命令体系 / CLI command system
- [x] Rich 风格输出 / Rich-powered console output
- [x] 用户级默认配置 / User-level default configuration
- [x] 下载目录监听 / Download folder watching
- [x] 文件自动分类 / Automatic file classification
- [x] 安装建议队列 / Install suggestion queue
- [x] PySide6 GUI 原型 / PySide6 GUI prototype
- [x] `doctor / test / full_check` 自检 / diagnostics and full check
- [ ] 软件跟踪模板：Chrome / Edge / WeChat / BaiduNetdisk
- [ ] GUI 设置页完善 / Improve GUI settings page
- [ ] 托盘常驻 / System tray support
- [ ] 安装建议历史页 / Install suggestion history page
- [ ] Windows exe 打包 / Windows executable packaging
- [ ] 更完善的安装器识别策略 / Better installer detection strategies

---

## 📌 项目状态 / Status

PathPilot is currently a prototype-stage personal productivity tool.

当前项目仍处于原型阶段，核心链路已经可用，但仍建议谨慎处理真实安装器。

---

## 🪪 License

MIT License is recommended.

If this repository includes a `LICENSE` file, please refer to it for details.

---

## 🙌 Author

Built by [forgottenlab](https://github.com/forgottenlab).

Made for cleaner downloads, safer installs, and a less painful Windows C drive. ✨
