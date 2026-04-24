# Sentiment Monitor

面向 A 股研究场景的本地分析工作台，聚合了实时行情、舆情采集、条件选股、深度估值、历史回测和财务溯源能力。项目当前已经从最初的“舆情看板”扩展成一套可直接用于个股研究的前后端应用。

## 项目展示

| 首页看板 | 对比分析 | 深度分析 |
| --- | --- | --- |
| ![首页看板](docs/screenshots/QQ图片20260327161155.png) | ![对比分析](docs/screenshots/QQ图片20260327161107.png) | ![深度分析](docs/screenshots/QQ图片20260327161212.png) |

## 当前能力

### 首页看板
- 监控股票池增删改查
- 新增标的后自动触发单股舆情采集
- 新标的在采集完成前会以“待采集”状态先展示在首页
- 实时价格、PE、PB、股息率、市值快照
- 最新新闻、研报、公告与情绪标签

### 个股详情
- 单只股票舆情明细
- 公告、研报、新闻分组展示
- 从首页直接跳转研究链路

### 对比分析
- 多标的实时价格对比
- 历史价格与估值序列对比
- 支持最新价与分时视角

### 条件选股
- 基于 SQLite 本地快照做全市场筛选
- 支持 `PB / PE / ROE / ROI / 股息率 / 总市值` 组合过滤
- 结果支持排序、快速加入监控和跳转分析
- 页面改造成浅色“研究工作台”布局，强化候选池可读性
- 默认可剔除异常估值样本，也可手动纳入

### 深度分析
- 10 年历史分位矩阵：`PE / PB / ROI / 股息率`
- `F-Score` 财务安全性排雷
- 估值结论层：合理价值区间、折价/溢价、安全边际、预期年化回报
- 多模型估值：`ROE-PB` 锚点、盈利能力估值、股东自由现金流估值
- 同行与行业横向对比
- Investment Thesis：买入理由、关键假设、风险清单、复核触发器
- 新增“上次缓存结果优先返回，后台再刷新”机制，减少深度分析页等待时间

### 财务溯源
- 股价与股东人数对比图置顶展示
- 现金流质量矩阵：`CFO / FCF / CFO转净利 / FCF转净利 / Capex / FCF收益率`
- 资本配置分析：再投资率、留存率、股本变动、BVPS 增长等
- 经营稳定性分析：收入、利润率、ROE/ROIC 代理波动与周期标签
- 杜邦 ROE 拆解、盈利护城河追踪、股东回报矩阵

### 历史回测
- 个股历史估值回放
- 收益拆解
- 信号相关性分析

### 监控配置
- 支持为监控标的维护行业和同行代码
- 深度分析页会优先使用行业与同行配置做横向估值对照

## 最近更新

- 新增股票后，后端会自动补采该股票的舆情数据
- 首页支持展示“待采集”标的，不再只显示已有舆情快照的股票
- 监控配置页支持行业与同行代码维护，供深度分析横向对比复用
- 深度分析接口改为“优先返回上次缓存结果，后台异步刷新最新结果”
- 选股页完成“研究工作台”重做，候选池和结果区优先展示
- 前端 API 基地址统一为相对路径 `/api`
- `start.bat` 调整为轻量启动：只启动前后端和浏览器，不再自动执行数据同步脚本
- 项目展示图片已统一整理到 `docs/screenshots/`

## 路线图

- 价值分析后续规划见 [docs/plans/2026-04-16-value-analysis-roadmap.md](docs/plans/2026-04-16-value-analysis-roadmap.md)

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Django 4.x, Django REST Framework, SQLite |
| 前端 | Vue 3, TypeScript, Vite, Pinia, Vue Router, ECharts |
| 数据源 | 腾讯财经、东方财富、AkShare、新浪财经兜底 |
| 缓存 | Django FileBasedCache + 文件快照缓存 |

## 项目结构

```text
sentiment_monitor/
├── backend/
│   ├── api/                        # 核心业务服务、REST API、缓存、测试、管理命令
│   ├── analyzer/                   # 分析辅助模块
│   ├── collector/                  # 舆情与行情采集逻辑
│   ├── scripts/                    # 诊断、修复、验证等工具脚本
│   ├── scratch/                    # 临时调试脚本与输出
│   │   └── debug_outputs/
│   ├── cache_data/                 # Django 文件缓存目录
│   ├── sentiment_monitor/          # Django 配置
│   ├── manage.py
│   ├── requirements.txt
│   └── db.sqlite3
├── docs/
│   ├── plans/                      # 开发路线图与规划文档
│   └── screenshots/                # README 展示图片
├── frontend/
│   ├── src/
│   │   ├── api/                    # Axios 封装
│   │   ├── components/             # 通用组件
│   │   ├── composables/            # 组合式逻辑
│   │   ├── lib/                    # ECharts 等基础封装
│   │   ├── router/                 # 前端路由
│   │   ├── stores/                 # Pinia 状态
│   │   └── views/                  # Dashboard / Detail / Compare / Screener / Analysis / History / Quality
│   ├── dist/                       # 前端构建产物
│   ├── package.json
│   └── vite.config.ts
├── legacy/                         # 历史文件或旧实现
├── start.bat                       # Windows 一键启动脚本
└── README.md
```

## 页面与路由

| 页面 | 路由 | 说明 |
| --- | --- | --- |
| 首页看板 | `/` | 股票池、实时价格、舆情总览 |
| 个股详情 | `/stock/:symbol` | 单股舆情明细 |
| 对比分析 | `/compare` | 多标的实时/历史对比 |
| 条件选股 | `/screener` | 基于 SQLite 快照的全市场筛选 |
| 深度分析 | `/analysis/:symbol` | 分位、F-Score、估值、同行、Thesis |
| 历史回测 | `/analysis/:symbol/history` | 历史回放与收益分析 |
| 财务溯源 | `/quality/:symbol` | 现金流、资本配置、稳定性、股东人数 |

## 核心接口

### 股票与采集
- `GET /api/stocks/`
- `POST /api/stocks/`
- `PATCH /api/stocks/{symbol}/`
- `DELETE /api/stocks/{symbol}/`
- `POST /api/collect/`

### 行情与舆情
- `GET /api/sentiment/latest/`
- `GET /api/sentiment/today/`
- `GET /api/sentiment/realtime_prices/`
- `GET /api/sentiment/search/?q=...`
- `GET /api/sentiment/comparison_realtime/?symbols=...&type=last|minute`
- `GET /api/sentiment/comparison_historical/?symbols=...&limit=30&period=day`

### 研究分析
- `GET /api/sentiment/analysis/?symbol=SZ000001`
- `GET /api/sentiment/history-backtest/?symbol=SZ000001`
- `GET /api/sentiment/screener/?pb_max=1.5&pe_max=15&roe_min=12&dividend_yield_min=4&sort_by=pb&sort_order=asc`
- `POST /api/sentiment/screener/refresh/`
- `GET /api/sentiment/quality/?symbol=SZ000001&include_shareholder=1`
- `GET /api/sentiment/quality/shareholder-structure/?symbol=SZ000001`
- `POST /api/sentiment/quality/refresh/`

## 启动方式

### 方式 1：Windows 一键启动

```powershell
start.bat
```

脚本会依次执行：

1. 启动 Uvicorn 后端，默认地址 `http://127.0.0.1:8000`
2. 启动 Vite 前端，默认地址 `http://localhost:5173`
3. 自动打开浏览器
4. 保留非阻塞缓存预热，不阻塞前端打开

### 方式 2：手动启动

#### 1. 后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
uvicorn sentiment_monitor.asgi:application --host 127.0.0.1 --port 8000
```

#### 2. 前端

```powershell
cd frontend
npm install
npm run dev
```

## 数据同步

### 一次性全量同步

```powershell
cd backend
.\venv\Scripts\activate
python manage.py sync_all_data
```

可选参数：

- `--skip-collector`：跳过监控池新闻/公告/研报采集
- `--skip-screener`：跳过全市场选股快照刷新
- `--skip-quality`：跳过财务质量缓存预热
- `--with-shareholder`：财务预热时一并拉取股东结构数据

### 只执行舆情采集

```powershell
cd backend
.\venv\Scripts\activate
python manage.py run_collector
```

## 前后端联调说明

前端 API 统一走相对路径 `/api`。

- 开发环境下，Vite 通过 [frontend/vite.config.ts](frontend/vite.config.ts) 将 `/api` 代理到 `http://127.0.0.1:8000`
- 部署环境下，建议由同域名反向代理将 `/api` 转发给 Django

这样前端不再需要手动拼接主机名或端口。

## 缓存与性能策略

项目当前针对慢路径做了几层拆分：

- 深度分析：`analysis_v6_*` 缓存 12 小时；如果新缓存失效但旧缓存仍在，会先返回旧结果，再后台刷新
- 选股页：全市场快照写入 SQLite，本地筛选只查询最新快照，不重复拉取全市场数据
- 财务溯源：核心财务数据和股东结构图分开缓存，减少整页阻塞
- 启动预热：应用启动后后台线程会预热常用历史数据、深度分析和历史回测缓存
- 文件缓存目录位于 `backend/cache_data/`

需要注意：

- 首次冷启动或缓存完全失效时，AkShare 与东方财富相关链路仍可能较慢
- Windows 下如果文件缓存出现偶发权限问题，接口通常会降级为“缓存写失败但继续返回结果”

## 数据源说明

### 腾讯财经
- 实时价格
- 分时数据
- 历史 K 线

### 东方财富 / AkShare / 新浪兜底
- A 股快照搜索
- 新闻、研报、公告
- 财务报表
- 分红数据
- 股东户数

## 测试与构建

后端测试：

```powershell
cd backend
python manage.py test api.tests api.tests_analysis_cache api.tests_sync_command
```

前端构建：

```powershell
cd frontend
npm run build
```

## 已知事项

- 财务溯源页首次打开某只股票时，外部数据源可能仍然较慢
- 当前前端构建仍可能出现 Vite 大 chunk 警告，但不影响运行
- `backend/scripts/` 与 `backend/scratch/` 中仍保留了较多调试脚本，后续可以继续分层整理

## 开发建议

- 功能主逻辑优先收敛到 `backend/api/` 和 `frontend/src/`
- 诊断、修复、验证脚本尽量放到 `backend/scripts/`
- 临时调试输出放到 `backend/scratch/debug_outputs/`
- 新增慢查询或慢抓取路径时，优先考虑缓存拆分，而不是继续放大单次页面请求

## 许可证

当前仓库未单独声明开源许可证；如果需要公开发布，建议补充 `LICENSE`。
