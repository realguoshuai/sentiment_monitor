# Changelog

## v0.1.3 (2026-06-01)

### Bug Fixes
- **ROIC 失真**：当财报缺少现金/负债字段时，`invested_capital` 全为 0 导致 ROIC 全部显示为 0。现在自动用归母净资产兜底（`calculator.py`）
- **时区不一致**：`views.py`、`price_service.py`、`fundamental_service.py` 中的 `datetime.now()` 统一改为 `timezone.now()`，避免 `USE_TZ=True` 下的日期偏差
- **裸 except**：`models.py`、`utils.py` 中的 `except:` 改为精确异常类型，不再吞掉 `KeyboardInterrupt`
- **分红解析崩溃**：`_build_plan` 中未保护的 `float()` 转换改为 `pd.to_numeric(errors='coerce')`
- **前端 toFixed 崩溃**：`ComparisonView.vue` 中 `.toFixed()` 前增加 optional chaining

### Performance
- **N+1 查询**：`overall_trend` 接口从 63 次逐条查询优化为 3 次批量查询

### Code Quality
- 合并 `fundamental_service.py` 中重复的缓存方法（`_cache_get`/`_cache_get_value`）
- 修复 `analysis_service.py` 中的可变默认参数 `dict={}`
- `fundamental_service.py` 中位置参数改为关键字参数
- `print()` 统一替换为 `logger.info()`/`logger.error()`

### New Features
- **Baostock 数据源**：免费、无 API Key、无频率限制，作为历史 K 线的兜底源
- **Tushare Pro 数据源**：需配置 `TUSHARE_TOKEN` 环境变量，覆盖财务报表、分红、北向持仓、融资融券
- Provider 模式：新数据源在现有源失败时自动介入，对上层零侵入

### Dependencies
- 新增 `baostock>=0.8.8`、`tushare>=1.4.0`

---

## v0.1.2 (2026-05-22)

### Bug Fixes
- 代码审查修复：0 值分位 bug、并行 fetch 隔离、tooltip 滚动错位、DRY safeNum
- 财务溯源页面图表横坐标和数值显示 undefined 问题

### Features
- 重构分析视图为独立图表组件，后端增加 stale cache
- 启用缓存预热，增加缓存容量
- 移动测试脚本到 tests/ 目录

---

## v0.1.0 (2026-04-28)

Initial release.
