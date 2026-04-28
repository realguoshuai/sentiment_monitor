# Desktop Prototype

`desktop/` 是 Sentiment Monitor 的 Electron 桌面壳目录。

目标：

- 保留现有 `start.bat` 开发方式
- 不改 Linux 部署链路
- 新增一个不依赖浏览器标签页的 Windows 桌面程序入口

## 当前能力

- 开发模式会同时拉起 Django、Vite 和 Electron 窗口
- 打包模式会自动构建前端，并自动重建后端 `SentimentMonitor.exe`
- 安装包内置后端二进制、前端静态资源和默认数据库
- 桌面模式会把数据库和缓存迁移到用户 `userData` 目录

## 使用方式

首次进入：

```powershell
cd desktop
npm install
```

生成桌面图标：

```powershell
npm run generate:icon
```

开发模式：

```powershell
npm run dev
```

只启动桌面壳：

```powershell
npm run app
```

## 打包 exe

执行：

```powershell
cd desktop
npm install
npm run generate:icon
npm run dist
```

输出目录：

- `desktop/release/`

默认生成：

- `SentimentMonitor-Setup-<version>-x64.exe`
- `SentimentMonitor-Portable-<version>-x64.exe`

## 说明

- 打包前会自动执行前端构建
- 打包前会自动调用 PyInstaller 重建 `backend/dist/SentimentMonitor.exe`
- 首次桌面启动时，如果用户目录里还没有数据库，会从安装包内的 `backend/db.sqlite3` 复制一份

## 当前限制

- 还没有接应用签名
- 图标是当前仓库内生成的默认品牌图标，后续可以替换
- 日志目录还没有单独拆分，目前重点先保证数据库和缓存不再写安装目录
