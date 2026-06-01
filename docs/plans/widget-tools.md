# Implementation Plan: Draggable Widget Tools Panel

## Overview

Add a "工具箱" (Toolbox) button to the DashboardView header. Clicking it opens a widget picker. Users can open multiple floating, draggable widget panels on the dashboard. Each widget is a self-contained tool. Widget positions and visibility are persisted to localStorage.

## Architecture

```
DashboardView.vue
  └── WidgetDock.vue          ← "工具箱" button + widget picker dropdown
  └── WidgetContainer.vue      ← draggable/resizable wrapper (one per open widget)
       ├── PortfolioWidget.vue  ← 组合仓位 + 分红计算器
       ├── CompoundWidget.vue   ← 复利计算器
       ├── MarginWidget.vue     ← 安全边际计算器
       ├── PositionWidget.vue   ← 仓位管理器
       ├── DividendCalWidget.vue ← 分红日历看板
       └── HeatmapWidget.vue    ← 持仓集中度热力图
  └── widgetStore.ts           ← Pinia store for widget state
```

## Files to Create

| # | File | Purpose |
|---|------|---------|
| 1 | `frontend/src/stores/widget.ts` | Pinia store: widget visibility, positions, sizes, localStorage persistence |
| 2 | `frontend/src/components/WidgetContainer.vue` | Draggable wrapper: title bar drag, close button, resize handle |
| 3 | `frontend/src/components/WidgetDock.vue` | "工具箱" button with dropdown picker |
| 4 | `frontend/src/components/widgets/PortfolioWidget.vue` | 组合仓位 + 分红计算器 |
| 5 | `frontend/src/components/widgets/CompoundWidget.vue` | 复利/分红再投计算器 |
| 6 | `frontend/src/components/widgets/MarginWidget.vue` | 安全边际计算器 |
| 7 | `frontend/src/components/widgets/PositionWidget.vue` | 仓位管理器 |
| 8 | `frontend/src/components/widgets/DividendCalWidget.vue` | 分红日历看板 |
| 9 | `frontend/src/components/widgets/HeatmapWidget.vue` | 持仓集中度热力图 |

## Files to Modify

| File | Change |
|------|--------|
| `frontend/src/views/DashboardView.vue` | Add WidgetDock + render open WidgetContainers |

## Widget Store Design (`widget.ts`)

```ts
interface WidgetState {
  id: string              // 'portfolio' | 'compound' | 'margin' | 'position' | 'dividendCal' | 'heatmap'
  visible: boolean
  x: number               // position from left
  y: number               // position from top
  w: number               // width
  h: number               // height
}

// State: widgets: Record<string, WidgetState>
// Actions: toggleWidget(id), updatePosition(id, x, y), updateSize(id, w, h), closeWidget(id)
// Persistence: watch + localStorage on every change
```

## WidgetContainer Design

- `position: fixed`, `z-index: 50` (below modals at z-100)
- Title bar: drag handle (mousedown → mousemove → mouseup)
- Close button (×) in top-right
- Optional resize handle (bottom-right corner)
- Props: `widgetId`, `title`, `icon`, `width?`, `height?`
- Emits: `close`
- Slot: default content

## Widget Specifications

### 1. PortfolioWidget (组合仓位 + 分红)
- Input: total capital (number input)
- Stock list: from store.stocks, each with editable allocation %
- Drag to reorder priority
- Real-time calculation:
  - Weighted dividend yield = Σ(allocation% × stock.dividend_yield)
  - Annual dividend income = totalCapital × weightedDY / 100
  - Weighted PE/PB
- Bar chart showing allocation breakdown

### 2. CompoundWidget (复利计算器)
- Inputs: initial capital, annual return %, monthly contribution, years
- Toggle: reinvest dividends (yes/no)
- Output: year-by-year table + line chart (ECharts)
- Show: total invested, total value, total gain, dividend income in final year

### 3. MarginWidget (安全边际计算器)
- Inputs: intrinsic value (or auto-fill from analysis), current price
- Auto-calculate:
  - Discount/premium %
  - Margin of safety %
  - Suggested buy price (intrinsic × 0.7)
  - Risk/reward ratio
- Color coding: green (undervalued), amber (fair), red (overvalued)

### 4. PositionWidget (仓位管理器)
- Inputs: total capital, max risk per trade %, stop loss %
- Stock selector from monitored stocks
- Auto-calculate:
  - Max position size per stock
  - Number of shares to buy
  - Portfolio heat (total risk exposure)
- Show how many positions at this size fit in total capital

### 5. DividendCalWidget (分红日历看板)
- 12-month calendar grid (current year)
- Each month shows stocks paying dividends that month
- Data from store.dividendCalendar
- Color intensity based on dividend amount
- Click month to see details

### 6. HeatmapWidget (持仓集中度)
- Treemap chart (ECharts) showing portfolio allocation
- If no portfolio set, show equal weight across all monitored stocks
- Color: sector-based or concentration-based
- Show: top holdings %, HHI (Herfindahl index), sector breakdown

## Implementation Order

1. `widget.ts` (store)
2. `WidgetContainer.vue` (draggable wrapper)
3. `WidgetDock.vue` (picker button)
4. `DashboardView.vue` (integration)
5. `PortfolioWidget.vue` (most useful, validates the pattern)
6. Remaining 5 widgets in parallel

## UI Style

- Dark theme: `bg-[#1a2332] border border-slate-700/50`
- Header: `bg-slate-800/80` with drag cursor
- Widget picker dropdown: `glass-card` style
- Inputs: `bg-slate-900/50 border border-slate-600 rounded-lg text-slate-200`
- Numbers: `font-mono text-cyan-400`
- Charts: existing ECharts dark theme
