# 三平台手动发布指南

本项目当前推荐使用“方案 1”进行桌面应用发布：

- Windows 机器打 Windows 安装包
- macOS 机器打 macOS 安装包
- Linux 机器打 Linux 安装包

这是当前最稳妥的方式。原因是项目不仅包含 Electron，还包含 Python 后端，后端会通过 `PyInstaller` 打成平台相关可执行文件，因此发布规则仍然是“在哪个平台打包，就产出哪个平台的安装包”。

## 适用场景

适合下面这类目标：

- 先把 Windows、macOS、Linux 的安装包稳定做出来
- 先验证三端能否正常安装和启动
- 暂时不引入 GitHub Actions、签名、公证等额外复杂度

## 机器准备

建议准备三台机器，或至少三个独立平台环境：

- Windows 10/11
- macOS
- Ubuntu Linux

每台机器都需要：

- Node.js 18 或 20
- npm
- Python 3.11
- 可正常访问项目源码

建议三台机器检出的代码版本一致，例如同一个 tag 或同一个 commit。

## 首次安装

在每台机器的项目根目录执行：

```bash
npm install
```

这一步会自动完成：

- 安装 `frontend` 的 npm 依赖
- 安装 `electron` 的 npm 依赖
- 创建后端 Python 虚拟环境
  - Windows: `backend/winvenv`
  - macOS/Linux: `backend/.venv`
- 安装 `backend/requirements.txt`

说明：

- 打包流程已经包含 Python 后端代码混淆
- 混淆工具为 `PyArmor`
- 后续再通过 `PyInstaller` 生成平台可执行文件

如果只想单独准备后端环境，可以执行：

```bash
npm run setup:backend
```

## 打包命令

在目标平台机器上，进入项目根目录执行：

```bash
npm run dist
```

它会自动完成：

- 构建前端生产包
- 混淆后端 Python 代码
- 使用 `PyInstaller` 打包后端可执行文件
- 使用 `electron-builder` 生成当前平台安装包

也可以显式指定平台命令：

```bash
npm run dist:win
npm run dist:mac
npm run dist:linux
```

通常手动发布时，推荐在对应平台只执行 `npm run dist`。

## 产物位置

打包完成后，安装包会出现在根目录：

```text
dist/
```

常见产物示例：

- Windows: `*.exe`
- macOS: `*.dmg`
- Linux: `*.AppImage`

Windows 实测产物示例：

- `dist/Hajimi Studio Setup 1.0.0.exe`
- `dist/Hajimi Studio Setup 1.0.0.exe.blockmap`
- `dist/win-unpacked/`

## Windows 实测记录

以下流程已经在 Windows 机器上实际跑通：

```bash
npm install
npm run dist
```

实测现象：

- `npm install` 可以自动完成前端、Electron、后端依赖准备
- 前端生产构建可以成功完成
- `PyArmor` 混淆可以成功执行
- `PyInstaller` 可以成功生成后端 `imem_studio.exe`
- `electron-builder` 可以成功生成 NSIS 安装包

实测成功标志：

- 出现 `Build complete! The results are available in: ...\\backend\\dist`
- 出现 `building target=nsis`
- 出现 `building block map`
- 命令行正常返回 PowerShell 提示符，没有红色报错

## Windows 打包耗时经验

第一次完整打包可能明显偏慢，尤其是后端依赖较重时。

实测经验：

- 前端 build：通常几分钟内完成
- `PyArmor`：通常较快
- `PyInstaller`：可能是最慢阶段，日志会持续刷很多 `INFO`
- `electron-builder`：通常在后段完成安装包和 blockmap

如果终端只是不断输出 `INFO:`，通常说明仍在正常执行，不必急着中断。

下面这些日志通常表示还在正常跑：

- `Processing standard module hook`
- `Processing pre-safe-import-module hook`
- `Building PYZ`
- `Building PKG`
- `Building EXE`
- `Building COLLECT`

下面这些日志通常表示已经接近成功：

- `Build complete!`
- `building target=nsis`
- `building block map`

## 当前遗留问题

这些问题目前不会阻塞 Windows 出包，但建议后续再处理：

### 1. 默认 Electron 图标仍在使用

当前日志会提示：

- `default Electron icon is used`

说明以下图标文件目前未正确提供，或路径下没有可用文件：

- `electron/assets/icon.ico`
- `electron/assets/icon.icns`
- `electron/assets/icon.png`

影响：

- 不阻塞打包
- 安装包和应用图标会退回默认 Electron 图标

### 2. 依赖安全告警暂未处理

执行 `npm install` 时会看到 `npm audit` 漏洞提示。

影响：

- 当前不阻塞打包
- 后续需要单独评估是否升级依赖

### 3. Node 版本不建议过新

当前项目前端使用 `react-scripts@5`，在过新的 Node 主版本上可能出现异常构建问题。

当前建议：

- 优先使用 Node 18 或 20

### 4. Windows 符号链接权限仍是敏感点

之前 Windows 打包曾在 `electron-builder` 阶段因为 `winCodeSign` 解压时创建 symbolic link 失败而卡住。

当前经验：

- 开启 Windows Developer Mode 后可正常完成打包
- 或使用管理员终端执行打包

## 推荐发布流程

每次发版建议按下面顺序执行：

1. 在三台机器上切到同一个 commit 或 tag
2. 分别执行 `npm install`
3. 分别执行 `npm run dist`
4. 在各自机器上先本地安装验证
5. 收集三个平台的安装包，再统一发布

## 本地验收清单

每个平台打包后，至少确认下面几项：

- 安装包可以正常打开
- 应用可以启动
- 前端页面能正常加载
- 后端服务能正常被 Electron 拉起
- 基础功能可用，例如登录、知识库、Agent 页面可访问
- 数据目录能正常创建

## 当前已知限制

### 1. 不是单机跨平台全量打包

当前方案支持：

- Windows 机器一键打 Windows 包
- macOS 机器一键打 macOS 包
- Linux 机器一键打 Linux 包

当前方案不支持：

- 在一台机器上同时产出 Windows、macOS、Linux 三个平台完整安装包

### 2. 签名和公证未接入

当前配置重点是“先稳定出包”，还没有接入正式分发常见的签名能力：

- Windows 代码签名证书
- macOS 签名与 notarization

因此发布给外部用户时，系统可能出现安全提示。这不影响内部测试，但会影响正式分发体验。

### 3. 后端对本机构建环境有要求

因为项目后端依赖 Python 生态、`PyInstaller`、`PyArmor`，不同平台上如果某些依赖缺失，可能需要补装系统层依赖后再打包。

## 常见问题

### `npm install` 很慢或失败

先确认：

- Node 版本是否是 18 或 20
- Python 是否是 3.11
- 网络是否能正常安装 npm 和 pip 依赖

不建议直接使用过新的 Node 主版本。当前项目前端基于 `react-scripts@5`，实测在较新的 Node 版本上可能出现异常构建问题。

### Windows 可以完成前后端构建，但卡在 Electron 安装包阶段

如果你已经看到下面这些现象，说明前端构建、Python 混淆、PyInstaller 后端打包其实已经完成了：

- `build-desktop folder is ready to be deployed`
- 出现 `pyarmor.exe gen`
- `Build complete! The results are available in: ...\\backend\\dist`

这时如果最后卡在 `electron-builder`，并且报错里包含下面这类信息：

- `Cannot create symbolic link`
- `winCodeSign`
- `客户端没有所需的特权`

通常不是项目代码问题，而是 Windows 本机没有创建符号链接的权限。

推荐按下面任一方式处理：

1. 开启 Windows Developer Mode
2. 用“管理员身份运行”PowerShell 或终端后再执行打包

建议优先开启 Developer Mode，这样以后普通终端也更容易完成打包。

### Windows Developer Mode 怎么开

在 Windows 10/11 中：

1. 打开“设置”
2. 搜索 `Developer Mode` 或“开发者设置”
3. 进入“面向开发者”
4. 开启“开发人员模式”
5. 开启后重新打开一个新的 PowerShell 窗口
6. 回到项目根目录重新执行 `npm run dist`

如果你不想改系统设置，也可以：

1. 关闭当前终端
2. 右键 PowerShell 或 Windows Terminal
3. 选择“以管理员身份运行”
4. 进入项目根目录
5. 执行 `npm run dist`

### Windows 打包前建议自查

在 Windows 机器上正式打包前，建议先确认：

- 使用的是 Node 18 或 20
- 使用的是 Python 3.11
- 终端有符号链接权限
- `electron/assets` 下的图标文件存在

当前配置里声明了这些图标路径：

- `electron/assets/icon.ico`
- `electron/assets/icon.icns`
- `electron/assets/icon.png`

如果这些文件缺失，`electron-builder` 会退回默认 Electron 图标，虽然不一定阻塞打包，但发布体验会变差。

### Linux 打包失败

优先检查：

- Python 原生依赖是否缺系统库
- `PyInstaller` 相关依赖是否完整
- 是否在图形桌面环境或完整构建环境下执行

### macOS 包能生成，但打开有安全提示

这通常不是打包失败，而是因为还没有做 Apple Developer 签名和公证。

### Windows 包能生成，但被 SmartScreen 提示

这通常是因为还没有配置正式的代码签名证书。

## 后续升级路线

如果这套手动发布流程跑通，下一步建议按这个顺序升级：

1. 先稳定三平台手动出包
2. 再引入 GitHub Actions 自动在三平台分别构建
3. 最后再补 Windows 签名、macOS 签名和公证
