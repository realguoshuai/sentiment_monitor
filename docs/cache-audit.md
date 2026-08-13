# 缓存层体检与改造记录

> 适用代码：`backend/api/cache_manager.py` + 各 service/view 的缓存用法
> 状态：P0（失效层）+ macro/earnings 刷新入口 + 前端错误态区分 均已交付并提交（commit `12a990b`）

---

## 1. 背景：两套共存的缓存键约定

本项目缓存后端是 Django `FileBasedCache`（磁盘 `backend/cache_data`，单目录）。

历史演进中形成了**两套键约定**，这是所有缓存 bug 的根源：

| 约定 | 写入方式 | 真实键形态 | 涉及模块 |
|------|----------|-----------|----------|
| **A 类（规范）** | `CacheManager.get_or_fetch()` | `key_v2`，并带 `_stale` / `_lock` / `_refreshing` 后缀 | fundamental / analysis / history_backtest |
| **B 类（裸键）** | 直接用 `cache.set / get / delete` | `key` 本身（无 `_v2` 后缀） | market.py / price_service / screener_service / macro_service / earnings_calendar_service / utils.py |

`CACHE_VERSION = "v2"`（`cache_manager.py:28`），A 类键的真实形态是 `get_or_fetch` 在传入 key 后自动追加 `_v2`。

> ⚠️ **FileBasedCache 的坑**：磁盘文件名是 `make_key(key)` 的 md5，**文件内容只存 `[过期时间, 值]`，不含 key**。因此**不能靠扫目录按 key 名 grep 删**，只能 `cache.delete(精确键)`。`_cull` 仅在文件数 > `MAX_ENTRIES`(50000) 时触发（当前约 3160 文件，远未触发，无写放大）。

---

## 2. 体检发现的问题

### P0 — 失效层大面积失效（版本/键名对不上）
- 原 `invalidate()` 只删 `key_v2` 形式，但 B 类裸键（如 `dividend_calendar_v1`、`price_history_raw_qfq_*`）**根本不带 `_v2`** → 失效调用全成空操作。
- `CACHE_REGISTRY` 里 price 域键名写错：`price_history_raw_{symbol}_day`（还带了一个不存在的 `_raw` 后缀），而 `price_service` 真实裸键是 `price_history_raw_qfq_{symbol}_{period}`（period ∈ day/week/month）→ `invalidate_by_symbol(..., ['price'])` 删不到真键，`market.py` 的 `force_deep` 刷新价格实际无效。
- `dividend_calendar_v1` 是裸键却登记在 registry，原 `invalidate_domain('market_diary')` 去删 `dividend_calendar_v1_v2`（不存在的键）→ 分红日历只能等 6h TTL 自然过期，无任何生效的主动刷新入口。

### P1 — macro / earnings 游离在 registry 外
- `macro_service` 键 `macro:risk_free_rate_10y`（TTL 12h）、`earnings_calendar_service` 动态键 `earnings_calendar_v1_{days}_{recent}`（TTL 6h）**从未登记进 registry**，无主动失效/刷新入口，只能等 TTL 自然过期。

### P2 — 前端把"抓取失败"静默成"暂无数据"
- 后端 `get_or_fetch` 把异常缓存为 `ERROR_MARKER`（`error_ttl` 5 分钟），并在 `payload.cache_status` 写明 `'error'`。
- 但 `QualityView` / `AnalysisDetailView` / `HistoryBacktestView` 只判断 `cache_status === 'stale'`，**完全没判断 `'error'` / `'empty'`** → 后端返回 `200 + cache_status='error'` 时，前端渲染成"暂无数据"，用户以为真没数据（要等 5 分钟 error 缓存过期才重试）。

### 已纠正的误判（避免后人被带偏）
- **"O(n) 写放大"误判**：`MAX_ENTRIES=50000`，`16667` 是**被删数量**不是阈值，当前 3160 文件无写放大。
- **"分布式锁防击穿"夸大**：实为 `FileBasedCache` 内部 `threading.Lock`（进程内锁），单进程部署有效；仅多 worker 跨进程失效，本项目不涉及。

---

## 3. 已做的修复

### 3.1 `cache_manager.py` — invalidate 双约定 + registry 修正
- `invalidate(key)` 重写为**对每个 key 同时尝试删 `key` 与 `key_v2` 两个 base**，各带 `_stale/_lock/_refreshing/_building` 后缀。删不存在的键是 no-op，无副作用。
  → `invalidate` / `invalidate_by_symbol` / `invalidate_domain` 对 A 类（`_v2`）和 B 类（裸键）**都真正生效**。
- 修正 registry price 域键名：`price_history_raw_qfq_{symbol}_{day,week,month}`（去掉错误的 `_raw`）。
- registry 新增 `macro` 域（`macro:risk_free_rate_10y`）与 `earnings` 域（锚点键 `earnings_calendar_v1_120_7`）。

### 3.2 `views/market.py`
- `force_deep` 增加 `market_diary` 域 → 现在能真正刷新 K线/价格/盯盘日记（含 diary 内重复的 dividend 裸键）。
- `get_dividend_calendar` 新增 `?force=1` → `CacheManager.invalidate('dividend_calendar_v1')` 主动刷新全局日历。

### 3.3 `views/macro.py` / `views/earnings_calendar.py`
- `get_risk_free_rate` 读 `?force=1`，透传给 `MacroService.get_risk_free_rate(force=...)`（服务层本来就有 force 参数，之前只是接口没透传）。
- `get_earnings_calendar` 读 `?force=1`，调 `get_calendar` 前按实际 `days/recent` 参数 `CacheManager.invalidate("earnings_calendar_v1_{days}_{recent}")` 精确清动态键。

### 3.4 前端错误态区分（3 个 SFC）
- `QualityView.vue`：新增 `cacheError` ref + 红色 `.cache-error-banner` 提示条。
- `AnalysisDetailView.vue` / `HistoryBacktestView.vue`：cached/fresh 两条路径都置 `error` 态，模板放宽条件确保错误提示不被"有数据"掩盖。
- **规则**：只有 `cache_status === 'error'` 才弹"数据获取失败，请稍后重试"；`empty`/`stale`/`fresh`/`computed` 一律不误报。

### 3.5 `DashboardView.vue`
- 移除顶部"上次更新"时间戳块（用户反馈不需要且不好看），清理对应的 `lastUpdate` computed。

---

## 4. 测试结论（已验证）

| 层级 | 方式 | 结果 |
|------|------|------|
| 逻辑层 | `FakeCache` mock 覆盖 7 域 + 动态键 | ALL PASSED |
| 真实后端 | 真实 `FileBasedCache` 落盘 360 键（双约定 × 后缀），`invalidate_by_symbol` 后 `cache.get` 命中 0、磁盘文件清空到 0 | ALL PASSED |
| 前端 SFC | `@vue/compiler-sfc` parse + compileScript | 模板 0 错误 |
| **联网端到端** | Django test client + 真实 akshare | MACRO/EARNINGS 写入→invalidate→`?force` 重拉 全链路真实生效 |

> 联网验证顺带定位两处**非 bug** 数据层现象：
> 1. macro 偶发 `rate=None` 是网络抖动，`MacroService` 已正确降级返回 None 且**不缓存**（下次重试）。
> 2. earnings `yjbb NoneType` 是未来报告期（`20260930`/`20261231`）无数据，`_fetch_yjbb` 已优雅降级返回 `[]`，接口仍 200。

---

## 5. 已知边界（尚未处理，留待后续）

1. **桌面 exe 视图层不生效**：`views/market.py` / `macro.py` / `earnings_calendar.py` 被冻进 PyInstaller PYZ（不在松散文件里）。要让 exe 也拿到 `?force` 修复，需 `npm run build:backend` 重建。开发后端（源码）已立即生效。
   - `cache_manager.py` 是松散文件，已 `cp` 到 `dist/SentimentMonitor-runtime/_internal/api/cache_manager.py` 与源码一致；前端 SFC 同理需重建 exe。
2. **`CacheMonitor.check_health()` 未调度**：仅挂在 `/cache/health/` HTTP 端点，`api/scheduler.py` 现有 3 个 interval 任务没挂它 → 属"写了没接入口的死代码"。
3. **前端 Analysis / History「刷新」按钮是假的（真实 active bug）**：`getAnalysis(symbol, true)` / `getBacktest(symbol, true)` 的 force 到 `api/index.ts` 被丢弃（getAnalysis/getBacktest 无 force 参数、不拼 `&force=1`）；后端 `views/analysis.py` 不读 `?force`；`get_or_fetch` 本身无 force 参数、service 也不调 `invalidate` → 点刷新只是重发普通 GET，仍返回旧缓存（7 天 TTL）。**「前端刷新按钮已能处理」是错误判断，已纠正。** 修复：后端接口 `?force=1` 时 `invalidate(对应 cache_key)` 再计算 + 前端 api 层补 force 拼 URL（`cache_key` 构造需抽成可复用方法）。
4. **analysis / history 键未进 registry**：analysis 键 `analysis_{v6}_{symbol}_{period}{cfg_tag}` 含 period/cfg_tag 动态参数，无法用 `{symbol}` 模板覆盖；history 键 `history_backtest_v2_{symbol}` 只含 symbol 却漏未登记 → `force_deep` 清不到。建议在 registry 补 history 域（模板 `history_backtest_v2_{symbol}`），analysis 因动态需在接口层按实际 period 精确 invalidate。
5. **price 日内 K 线游离键** `intraday_single_v1_{symbol}_{trade_date}`（price_service）：不在 registry，无主动失效入口，但 TTL 60s + 按交易日轮换，影响轻微。
6. **DataFrame 双序列化**：`set_df`（to_json→list）与 `get_or_fetch`（`{__df_cache__:...}`）并存，生产路径不交叉，暂未触发。
7. **监控股为空**：会让 earnings 日历 `items=0`（数据配置问题，非代码问题）。

---

## 6. 附录：当前 CACHE_REGISTRY 键清单（2026-08-10）

| 域 | per_symbol 模板 | global 模板 |
|----|----------------|-------------|
| fundamental | `fundamentals_v7_{symbol}` `cashflow_v7_{symbol}` `xq_yield_v1_{symbol}` `xq_quote_metrics_v2_{symbol}` `xq_f10_v1_{symbol}` `dividends_v4_{symbol}` `cashflow_yearly_v1_{symbol}` `northbound_history_v1_{symbol}` `quality_v12_{symbol}` `quality_core_v2_{symbol}` `shareholder_overlay_v3_{symbol}` `shareholder_history_v1_{symbol}` `margin_history_v1_{symbol}` `f_score_v8_{symbol}` `forward_metrics_v2_{symbol}` `next_dividend_v1_{symbol}` | — |
| price | `price_history_raw_qfq_{symbol}_day/week/month` | `realtime_prices_last_success_v1` `a_share_spot_snapshot_for_valuation` `a_share_spot_snapshot_stale` |
| market_diary | `market_diary_hist_v1_{symbol}` `market_diary_today_v1_{symbol}` `market_diary_div_v1_{symbol}` | `dividend_calendar_v1` |
| screener | — | `screener_latest_roe_map_v2` `screener_latest_roe_map_v2_stale` `screener_latest_dividend_yield_map_v3` `screener_latest_dividend_yield_map_v3_stale` |
| macro | — | `macro:risk_free_rate_10y` |
| earnings | — | `earnings_calendar_v1_120_7`（默认组合锚点；动态键 `earnings_calendar_v1_{days}_{recent}` 由接口 `?force` 精确清） |
| other | `valuation_config_{symbol}` | `stock_zh_a_snapshot_v2` `manual_collection_lock` `manual_collection_status` |

> 真实磁盘键 = 模板替换 `{symbol}` 后，A 类再追加 `_v2`，并可能带 `_stale` / `_lock` / `_refreshing` / `_building` 后缀。
