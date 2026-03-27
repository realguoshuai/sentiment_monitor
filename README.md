# 舆情监控系统 V2.4 — Professional Financial Terminal

> 实时股价行情 · 多维舆情分析 · 价差对冲终端 · 零滚动金融工作站

## 系统概述

本系统是一个面向 A 股市场的**全栈舆情监控与价差对冲分析平台**。系统集成了实时股价行情（腾讯财经 API）、多维度舆情情感分析、以及专业级的价差对冲图表终端，旨在为投资者提供"一屏纵览"的高密度信息仪表盘。

## 核心特性

| 模块 | 功能 | 状态 |
|------|------|------|
| 📊 **零滚动仪表盘** | 4 列资产卡片 + 双图表全屏布局（`h-screen` 锁定） | ✅ |
| 💰 **实时行情引擎** | 基于腾讯财经 API，10 秒自动刷新，批量拉取 | ✅ |
| 📈 **价差对冲终端** | 分时/日线价差分析，ISO-GRID 时间轴对齐，客户端缓存 | ✅ |
| 🧠 **舆情情感分析** | 新闻、研报、公告的多维度情感评分与趋势可视化 | ✅ |
| 🔗 **深度外链集成** | 一键跳转雪球、东财股吧、融资融券、全网资讯 | ✅ |
| 🎨 **专业 UI 主题** | 首页 Premium Dark Mode + 详情/对比页 Light Theme | ✅ |

## 技术栈

| 层次 | 技术 |
|------|------|
| **后端** | Django 4.x + Django REST Framework + SQLite |
| **前端** | Vue 3 + TypeScript + Tailwind CSS + Pinia + Vue Router + ECharts |
| **行情数据** | 腾讯财经 API（实时行情 / 分时 / 日 K 线） |
| **舆情数据采集** | akshare（东方财富新闻 / 券商研报 / 巨潮公告） |

## 项目结构

```
sentiment_monitor/
├── backend/                    # Django 后端
│   ├── api/
│   │   ├── models.py           # Stock / SentimentData 数据模型
│   │   ├── views.py            # REST API 视图（含对比分析接口）
│   │   ├── price_service.py    # 腾讯财经行情引擎（实时/分时/K线）
│   │   ├── serializers.py      # DRF 序列化器
│   │   └── urls.py             # API 路由
│   ├── collector/              # 数据采集模块
│   │   ├── sources/
│   │   │   ├── eastmoney.py    # 东方财富数据源
│   │   │   └── cninfo.py       # 巨潮资讯数据源
│   │   └── collector.py        # 采集主程序
│   ├── sentiment_monitor/      # Django 项目配置
│   ├── db.sqlite3              # SQLite 数据库
│   └── requirements.txt
│
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── views/
│   │   │   ├── DashboardView.vue      # 零滚动仪表盘（Dark Theme）
│   │   │   ├── StockDetailView.vue    # 股票详情页（Light Theme）
│   │   │   └── ComparisonView.vue     # 价差对冲终端（Light Theme）
│   │   ├── components/
│   │   │   ├── StockCard.vue          # 资产行情卡片
│   │   │   ├── SentimentChart.vue     # 情感趋势图表
│   │   │   ├── HotScoreChart.vue      # 热度排行图表
│   │   │   ├── ContentTabs.vue        # 内容标签切换
│   │   │   └── NewsItem.vue           # 资讯列表项
│   │   ├── stores/             # Pinia 状态管理
│   │   ├── api/                # Axios API 封装
│   │   └── router/             # Vue Router 路由
│   └── package.json
│
├── start.bat                   # 一键启动脚本
└── README.md
```

## 环境要求

- Windows 10+
- Python 3.12
- Node.js 18+

## 快速开始

### 方式一：一键启动

```bash
# 双击或命令行运行
start.bat
```

### 方式二：手动部署

#### 1. 后端部署

```bash
cd backend

# 创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 数据库迁移
python manage.py migrate

# 启动后端服务
python manage.py runserver
```

后端服务：http://127.0.0.1:8000

#### 2. 初始化监控股票

```bash
python manage.py shell

from api.models import Stock
Stock.objects.create(name='东阿阿胶', symbol='SZ000423', keywords=['东阿阿胶', '阿胶', '滋补'])
Stock.objects.create(name='洋河股份', symbol='SZ002304', keywords=['洋河', '白酒', '蓝色经典'])
Stock.objects.create(name='五粮液', symbol='SZ000858', keywords=['五粮液', '白酒', '高端消费'])
Stock.objects.create(name='贵州茅台', symbol='SH600519', keywords=['茅台', '白酒', '高端消费'])
exit()
```

#### 3. 运行数据采集

```bash
python collector/collector.py
```

#### 4. 前端部署

```bash
cd frontend
npm install
npm run dev
```

前端地址：http://localhost:5173

## API 接口文档

### 舆情数据

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/sentiment/latest/` | GET | 获取最新舆情数据（含新闻/研报/公告） |
| `/api/sentiment/today/` | GET | 获取今日舆情数据 |
| `/api/sentiment/realtime_prices/` | GET | 获取所有监控股票实时价格 |

### 对比分析

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/sentiment/comparison_realtime/?symbols=SZ000423,SZ002304&type=last` | GET | 实时最新价对比 |
| `/api/sentiment/comparison_realtime/?symbols=SZ000423,SZ002304&type=minute` | GET | 当日分时数据对比 |
| `/api/sentiment/comparison_historical/?symbols=SZ000423,SZ002304&limit=30` | GET | 历史 K 线价差（默认 30 天） |

### 股票管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/stocks/` | GET | 获取监控股票列表 |
| `/api/stocks/` | POST | 新增监控股票 |
| `/api/collect/` | POST | 手动触发数据采集 |

## 数据源说明

### 行情数据（腾讯财经 API）

| 功能 | 接口 | 说明 |
|------|------|------|
| 实时行情 | `qt.gtimg.cn` | 批量获取最新价、涨跌幅 |
| 分时数据 | `ifzq.gtimg.cn/minute/query` | 当日逐分钟成交价格 |
| 历史 K 线 | `web.ifzq.gtimg.cn/fqkline` | 前复权日 K 线数据 |

### 舆情数据（akshare）

| 数据源 | akshare 接口 | 说明 |
|--------|-------------|------|
| 东方财富新闻 | `stock_news_em` | 个股相关新闻资讯 |
| 机构研报 | `stock_institute_recommend_detail` | 券商研报推荐 |
| 巨潮资讯公告 | `stock_zh_a_disclosure_report_cninfo` | 上市公司公告 |

## UI 设计说明

### 首页仪表盘（Dark Theme）
- **设计理念**：专业交易终端风格，高数据密度
- **布局**：`h-screen` 弹性布局，零滚动设计
- **配色**：`#0f172a` 基底 + `#1a2332` 卡片 + 高对比荧光数据色

### 详情页 & 对比终端（Light Theme）
- **设计理念**：清爽阅读体验，适合长时间数据分析
- **配色**：`bg-slate-50` 底色 + `bg-white` 卡片 + 深色文字确保可读性
- **图表**：ECharts 浅色主题配置，高对比坐标轴与数据标签

## 数据管理

- 系统自动保留最近 30 天数据
- 每次采集自动覆盖当日数据
- 数据存储于 `backend/db.sqlite3`
- 对比分析历史数据支持前端内存级缓存

## 版本历史

| 版本 | 主要变更 |
|------|---------|
| V1.0 | 纯 Python HTTP + 原生 HTML/CSS/JS + JSON 文件存储 |
| V2.0 | Django REST + Vue 3 + SQLite + akshare 真实数据源 |
| V2.4 | 腾讯行情引擎 + 零滚动仪表盘 + 价差对冲终端 + Light/Dark 双主题 |

## 常见问题

### Q: 如何添加新的监控股票？
```bash
python manage.py shell
from api.models import Stock
Stock.objects.create(name='股票名称', symbol='股票代码', keywords=['关键词'])
```

### Q: 数据采集失败？
- 检查网络连接
- akshare 接口可能因数据源限制暂时不可用
- 查看 `collector.py` 中的错误输出

### Q: 前端无法连接后端？
- 确保 Django 服务运行在 http://127.0.0.1:8000
- 检查是否有防火墙阻挡

### Q: 对比分析图表无数据？
- 确认后端服务已启动
- 检查腾讯财经 API 是否可访问（需要可访问外网）
- 非交易时间分时数据可能为空（历史数据不受影响）

---

*Built with ❤️ using Django + Vue 3 + ECharts*
