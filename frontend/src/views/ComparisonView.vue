<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <!-- Header -->
    <header class="bg-white/80 backdrop-blur-xl border-b border-slate-200 sticky top-0 z-50 shadow-sm">
      <div class="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <router-link to="/" class="p-2 hover:bg-slate-100 rounded-lg transition group">
            <svg class="w-6 h-6 text-slate-500 group-hover:text-slate-800" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
            </svg>
          </router-link>
          <div>
            <h1 class="text-xl font-bold text-gradient from-indigo-600 to-cyan-600">价差对冲分析终端</h1>
            <p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Expert Hedging Terminal</p>
          </div>
        </div>

        <!-- Time Horizon Selector -->
        <div class="flex flex-col md:flex-row items-center gap-4">
          <div class="flex bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button 
              v-for="scale in timeScales"
              :key="scale.value"
              @click="currentTimeScale = scale.value"
              :class="[
                'px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all whitespace-nowrap',
                currentTimeScale === scale.value ? 'bg-indigo-500 text-white shadow-md' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
              ]"
            >
              {{ scale.label }}
            </button>
          </div>
          
          <div class="flex bg-emerald-50 p-1 rounded-xl border border-emerald-100">
            <button 
              v-for="mode in metricModes"
              :key="mode.value"
              @click="currentMetricMode = mode.value"
              :class="[
                'px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all whitespace-nowrap',
                currentMetricMode === mode.value ? 'bg-emerald-600 text-white shadow-md' : 'text-emerald-700/60 hover:text-emerald-700 hover:bg-emerald-100/50'
              ]"
            >
              {{ mode.label }}
            </button>
          </div>
          
          <div class="flex bg-rose-50 p-1 rounded-xl border border-rose-100">
            <button 
              v-for="mode in calcModes"
              :key="mode.value"
              @click="currentCalcMode = mode.value"
              :class="[
                'px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all whitespace-nowrap',
                currentCalcMode === mode.value ? 'bg-rose-600 text-white shadow-md' : 'text-rose-700/60 hover:text-rose-700 hover:bg-rose-100/50'
              ]"
            >
              {{ mode.label }}
            </button>
          </div>
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-6 py-8">
      <!-- Selection Sector -->
      <div class="bg-white rounded-2xl shadow-sm p-6 mb-8 border border-slate-200">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold flex items-center gap-2 text-slate-800">
            <svg class="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
            </svg>
            对比标的录入 (选择2只)
          </h2>
          <div class="text-[10px] text-zinc-400 mt-1 uppercase tracking-tighter">Investment Return (ROI)</div>
        </div>
        <div class="flex flex-wrap gap-3">
          <button
            v-for="stock in store.dashboardStocks"
            :key="stock.stock_symbol"
            @click="toggleStock(stock.stock_symbol)"
            :class="[
              'px-4 py-2 rounded-xl border transition-all flex items-center gap-2 font-bold',
              selectedSymbols.includes(normalizeSymbol(stock.stock_symbol))
                ? 'bg-indigo-50 border-indigo-200 text-indigo-700 shadow-sm'
                : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50'
            ]"
          >
            <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: getStockColor(stock.stock_symbol) }"></span>
            <span>{{ stock.stock_name }}</span>
            <span class="text-[10px] opacity-50 font-mono">{{ stock.stock_symbol }}</span>
          </button>
          <!-- 搜索添加任意股票 -->
          <div class="relative">
            <input
              v-model="searchQuery"
              @input="onSearchInput"
              @focus="searchFocused = true"
              @blur="onSearchBlur"
              placeholder="搜索股票代码/名称..."
              class="px-3 py-2 rounded-xl border border-dashed border-slate-300 text-xs text-slate-600 bg-slate-50 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-200 w-44"
            />
            <div v-if="searchFocused && searchResults.length" class="absolute z-50 top-full left-0 mt-1 w-64 bg-white border border-slate-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
              <button
                v-for="r in searchResults"
                :key="r.symbol"
                @mousedown.prevent="addFromSearch(r)"
                class="w-full text-left px-4 py-2 text-xs hover:bg-indigo-50 flex items-center justify-between"
              >
                <span class="font-bold text-slate-700">{{ r.name }}</span>
                <span class="text-slate-400 font-mono">{{ r.symbol }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Spread Analysis Dashboard -->
      <div v-if="selectedSymbols.length === 2" class="space-y-6">
        <!-- Summary Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative overflow-hidden group">
             <div class="absolute top-0 right-0 p-3 opacity-5 group-hover:opacity-10 transition-opacity pointer-events-none">
                <svg class="w-12 h-12 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
             </div>
             <div class="flex items-center justify-between mb-3">
               <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">当前对冲价差 (Spread)</h4>
               <button
                 v-if="!editingExpected"
                 @click="startEditExpected"
                 class="p-1 rounded-md hover:bg-slate-100 transition text-slate-400 hover:text-indigo-500"
                 title="设置预期比值"
               >
                 <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
               </button>
             </div>
             <div class="flex items-baseline gap-2 relative z-10">
                <span class="text-4xl font-black font-mono tracking-tighter" :class="priceDiffColor">
                  {{ currentDiff > 0 ? '+' : '' }}{{ currentDiff.toFixed(2) }}
                </span>
                <span class="text-xs text-slate-500 font-bold uppercase">{{ currentCalcMode === 'ratio' ? 'x' : 'CNY' }}</span>
             </div>
             <!-- 预期比值区域 -->
             <div v-if="editingExpected" class="mt-3 flex items-center gap-2 relative z-10">
                <span class="text-[10px] font-bold text-amber-500 uppercase">预期:</span>
                <input
                  v-model="expectedInput"
                  @keyup.enter="saveExpectedRatio"
                  @keyup.escape="editingExpected = false"
                  type="number"
                  step="any"
                  class="w-24 h-7 px-2 rounded-md border border-amber-200 bg-amber-50 text-sm font-mono font-bold text-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-300"
                  :placeholder="currentDiff.toFixed(2)"
                  autofocus
                />
                <button @click="saveExpectedRatio" class="p-1 rounded-md bg-amber-100 hover:bg-amber-200 text-amber-600 transition" title="确认">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                </button>
                <button @click="clearExpectedRatio" class="p-1 rounded-md bg-rose-50 hover:bg-rose-100 text-rose-400 transition" title="清除预期值">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                </button>
             </div>
             <div v-else-if="expectedRatio !== null" class="mt-3 flex items-center gap-3 relative z-10">
                <div class="flex items-center gap-1.5">
                  <span class="text-[10px] font-bold text-amber-500 uppercase">预期:</span>
                  <span class="text-sm font-mono font-bold text-amber-600">{{ expectedRatio.toFixed(2) }}</span>
                </div>
                <span class="text-[10px] px-1.5 py-0.5 rounded font-bold"
                  :class="expectedDeviation !== null && expectedDeviation > 0 ? 'bg-rose-50 text-rose-500' : (expectedDeviation !== null && expectedDeviation < 0 ? 'bg-emerald-50 text-emerald-500' : 'bg-slate-50 text-slate-400')">
                  {{ expectedDeviation !== null ? (expectedDeviation > 0 ? '+' : '') + expectedDeviation.toFixed(1) + '%' : '--' }}
                </span>
             </div>
          </div>
          <div v-for="(sym, idx) in selectedSymbols" :key="sym" class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
             <div class="flex justify-between items-center mb-3">
                <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  {{ getStockName(sym) }} (Stock {{ idx + 1 }})
                </h4>
                <span class="text-[10px] font-mono text-slate-400">{{ sym }}</span>
             </div>
             <div class="flex items-baseline gap-2">
                <span class="text-3xl font-bold font-mono text-slate-800">{{ rtPrices[sym]?.price?.toFixed(2) || '--.--' }}</span>
                <span class="text-xs text-slate-500 font-bold uppercase">CNY</span>
                <span v-if="rtPrices[sym]" :class="rtPrices[sym].change_percent > 0 ? 'text-rose-600' : 'text-emerald-600'" class="text-[10px] font-bold ml-auto bg-slate-50 px-2 py-1 rounded">
                  {{ rtPrices[sym].change_percent > 0 ? '+' : '' }}{{ (rtPrices[sym].change_percent ?? 0).toFixed(2) }}%
                </span>
             </div>
          </div>
          
          <!-- ROE-PB Quality Score Card -->
          <div v-for="(sym, idx) in selectedSymbols" :key="'roe-'+sym" class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative overflow-hidden group">
             <div class="flex justify-between items-center mb-4">
                <div class="bg-indigo-500/10 text-indigo-600 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest">
                  Stock {{ idx + 1 }}
                </div>
                <div class="flex items-center gap-1 text-[10px] font-bold text-slate-400">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  ROI: {{ getRoiValue(sym).toFixed(2) }}%
                </div>
             </div>
             
             <h4 class="text-sm font-bold text-slate-800 mb-2" :title="'ROI = ROE/PB + 股息率'">{{ getStockName(sym) }}</h4>
             
             <div class="grid grid-cols-2 gap-4 mt-4">
               <div class="p-3 bg-indigo-50/50 rounded-xl border border-indigo-100/50">
                 <div class="text-[9px] font-bold text-indigo-400 uppercase tracking-tighter mb-1">ROE (推定)</div>
                 <div class="text-xs font-bold text-indigo-700">
                   {{ rtPrices[sym] && rtPrices[sym].pe > 0 ? ((rtPrices[sym].pb / rtPrices[sym].pe) * 100).toFixed(1) + '%' : '--' }}
                 </div>
               </div>
               <div class="p-3 bg-emerald-50/50 rounded-xl border border-emerald-100/50">
                 <div class="text-[9px] font-bold text-emerald-400 uppercase tracking-tighter mb-1">回报 (ROI)</div>
                 <div class="text-xs font-bold text-emerald-700">
                   {{ getRoiValue(sym).toFixed(2) }}%
                 </div>
               </div>
             </div>
             
             <div class="mt-4 pt-4 border-t border-slate-50 flex justify-end">
               <router-link 
                 :to="`/analysis/${sym}`"
                 class="text-[10px] font-black text-indigo-600 hover:text-indigo-800 transition-colors flex items-center gap-1"
               >
                 深度矩阵分析 →
               </router-link>
             </div>
          </div>

          <!-- Percentile Gauge Card -->
          <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative overflow-hidden group">
             <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">历史分位 (Percentile)</h4>
             <div class="flex items-end justify-between gap-4">
                <div class="flex flex-col">
                   <span class="text-3xl font-black font-mono text-indigo-600">{{ spreadStats.percentile.toFixed(1) }}%</span>
                   <div class="text-[10px] font-bold text-slate-400 mt-1">Relative to History</div>
                </div>
                <div class="flex-1 h-12 bg-slate-100 rounded-lg relative overflow-hidden self-center border border-slate-200/50">
                   <div 
                     class="absolute bottom-0 left-0 right-0 bg-indigo-500/20 transition-all duration-700" 
                     :style="{ height: spreadStats.percentile + '%' }"
                   ></div>
                   <div 
                     class="absolute left-0 right-0 h-1 bg-indigo-600 shadow-[0_0_10px_rgba(79,70,229,0.5)] transition-all duration-700 z-10" 
                     :style="{ bottom: spreadStats.percentile + '%' }"
                   ></div>
                </div>
             </div>
             <p class="text-[9px] font-bold text-slate-500 mt-4 uppercase">
               {{ spreadStats.percentile > 80 ? '⚠️ High Extremum' : (spreadStats.percentile < 20 ? '✅ Low Extremum' : 'Neutral Range') }}
             </p>
          </div>
        </div>

        <!-- Main Spread Chart -->
        <div class="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm relative min-h-[550px]">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-10">
            <div>
              <h3 class="text-lg font-bold flex items-center gap-3 text-slate-800">
                <div class="w-1.5 h-6 bg-indigo-500 rounded-full"></div>
                {{ getTimeScaleLabel(currentTimeScale) }} {{ getMetricLabel(currentMetricMode) }} {{ currentCalcMode === 'ratio' ? '比值' : '差值' }} 对冲走势
              </h3>
              <p class="text-[10px] text-slate-500 font-bold uppercase mt-1 tracking-widest">{{ currentTimeScale === 'minute' ? 'Intraday Hedge Pulse' : 'Historical Valuation Dynamics' }}</p>
            </div>
            
            <div class="flex flex-wrap items-center justify-end gap-3">
              <button
                @click="refreshComparisonData"
                :disabled="loadingPrice || selectedSymbols.length !== 2"
                class="inline-flex h-9 items-center gap-2 rounded-xl border border-indigo-100 bg-white px-3 text-[11px] font-black uppercase tracking-widest text-indigo-600 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-50"
                title="刷新当前对比数据"
              >
                <svg
                  class="h-4 w-4"
                  :class="{ 'animate-spin': loadingPrice }"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v6h6M20 20v-6h-6M5 19A9 9 0 0019 5M19 5h-4M5 19h4" />
                </svg>
                刷新
              </button>
              <div class="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-xl border border-slate-200">
                 <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Status:</span>
                 <div class="flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.3)] animate-pulse"></span>
                    <span class="text-[11px] font-mono font-bold text-emerald-700 uppercase tracking-tighter">Live ISO-GRID</span>
                 </div>
              </div>
            </div>
          </div>

          <div ref="priceSpreadRef" class="w-full h-[450px]"></div>

          <!-- 简化版联动性图例 (已挪至相关性图表下方) -->
          <div class="mt-2 px-1 flex items-center justify-between">
            <div class="flex items-center gap-4">
              <div class="flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span class="text-[9px] font-black text-slate-400 uppercase">1.0 股价走势同步 (Synced)</span>
              </div>
              <div class="flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-slate-300"></span>
                <span class="text-[9px] font-black text-slate-400 uppercase">0 股价走势无关 (Irrelevant)</span>
              </div>
              <div class="flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                <span class="text-[9px] font-black text-slate-400 uppercase">-1.0 股价走势反向 (Inverse)</span>
              </div>
            </div>
            <div class="text-[9px] font-black text-amber-500 uppercase tracking-tighter bg-amber-50 px-2 py-0.5 rounded border border-amber-100">
              ⚠️ < 0.5 关系破裂 (Breakdown)
            </div>
          </div>

          <!-- Spread Drawdown Chart -->
          <div class="mt-8 border-t border-slate-100 pt-8">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-sm font-bold flex items-center gap-2 text-slate-800 shrink-0">
                <svg class="w-4 h-4 text-rose-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"/></svg>
                价差回撤分析 (Spread Drawdown)
              </h3>
              <div class="text-[11px] text-slate-500 flex items-center gap-1.5 bg-rose-50/50 border border-rose-100 px-2.5 py-1 rounded-md w-fit max-w-[60%]">
                <svg class="w-3.5 h-3.5 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                <span class="truncate"><strong class="font-bold text-rose-700">回归动能：</strong>回撤坑越深，历史偏离后强行闭合的拉扯力量就越强</span>
              </div>
            </div>
            <div ref="drawdownRef" class="w-full h-[180px]"></div>
          </div>

          <div
            v-if="dataNotice"
            class="mt-3 rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-[11px] font-bold text-amber-700"
          >
            {{ dataNotice }}
          </div>
          
          <!-- Spread Intelligence Insight -->
          <div v-if="comparisonData.length > 0" class="mt-8 pt-8 border-t border-slate-100">
            <div class="bg-indigo-50/50 rounded-2xl p-6 border border-indigo-100">
               <div class="flex items-center gap-2 mb-4">
                  <div class="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></div>
                  <h4 class="text-xs font-black text-indigo-900 uppercase tracking-widest">量化对冲洞察 (AI Insight)</h4>
               </div>
               <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div class="space-y-4">
                     <p class="text-sm leading-relaxed text-slate-700">
                        在 <span class="font-bold text-slate-900">{{ spreadStats.range }}</span> 观测周期内，
                        {{ getStockName(selectedSymbols[0]) }} 与 {{ getStockName(selectedSymbols[1]) }} 的 <strong>{{ getMetricLabel(currentMetricMode) }} 差值</strong> 呈现明显波动。
                        <strong>最大偏离</strong> 出现在 <span class="text-rose-600 font-bold underline underline-offset-4">{{ spreadStats.maxDate }}</span>，
                        数值达 <span class="font-mono font-bold text-rose-600">{{ spreadStats.maxVal.toFixed(2) }}</span>；
                        <strong>最小偏离</strong> 位于 <span class="text-emerald-600 font-bold underline underline-offset-4">{{ spreadStats.minDate }}</span>，
                        数值为 <span class="font-mono font-bold text-emerald-600">{{ spreadStats.minVal.toFixed(2) }}</span>。
                     </p>
                     <div class="flex items-center gap-4 text-[10px] font-bold uppercase tracking-tighter text-slate-400">
                        <span>Sample Size: {{ comparisonData.length }} pts</span>
                        <span class="w-1 h-1 rounded-full bg-slate-300"></span>
                        <span>Confidence: 99% ISO-GRID</span>
                     </div>
                  </div>
                  <div class="grid grid-cols-2 gap-4">
                     <div class="bg-white p-3 rounded-xl border border-indigo-50 shadow-sm">
                        <div class="text-[9px] font-bold text-slate-400 uppercase mb-1">平均价差 (HEC Avg)</div>
                        <div class="text-base font-black font-mono text-indigo-600">{{ spreadStats.avg.toFixed(2) }}</div>
                     </div>
                     <div class="bg-white p-3 rounded-xl border border-indigo-50 shadow-sm">
                        <div class="text-[9px] font-bold text-slate-400 uppercase mb-1">当前 Z-Score</div>
                        <div class="text-base font-black font-mono" :class="Math.abs(spreadStats.zScore) > 2 ? 'text-amber-500' : 'text-slate-700'">
                           {{ spreadStats.zScore > 0 ? '+' : '' }}{{ spreadStats.zScore.toFixed(2) }}σ
                        </div>
                     </div>
                     <div class="bg-white p-3 rounded-xl border border-rose-50 shadow-sm">
                        <div class="text-[9px] font-bold text-slate-400 uppercase mb-1">最大回撤 (Max DD)</div>
                        <div class="text-base font-black font-mono text-rose-600">{{ drawdownStats.maxDrawdown.toFixed(2) }}</div>
                     </div>
                     <div class="bg-white p-3 rounded-xl border border-rose-50 shadow-sm">
                        <div class="text-[9px] font-bold text-slate-400 uppercase mb-1">当前回撤 (Cur DD)</div>
                        <div class="text-base font-black font-mono text-rose-500">{{ drawdownStats.currentDrawdown.toFixed(2) }}</div>
                     </div>
                  </div>
                  <!-- 预期偏离度 -->
                  <div v-if="expectedRatio !== null" class="mt-4 grid grid-cols-1">
                     <div class="bg-white p-3 rounded-xl border border-amber-100 shadow-sm">
                        <div class="flex items-center justify-between">
                          <div class="text-[9px] font-bold text-amber-400 uppercase mb-1">预期偏离度 (Expected Dev.)</div>
                          <button @click="clearExpectedRatio" class="text-amber-300 hover:text-rose-400 transition p-0.5" title="清除预期值">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                          </button>
                        </div>
                        <div class="flex items-baseline gap-3">
                          <span class="text-base font-black font-mono" :class="expectedDeviation !== null && Math.abs(expectedDeviation) > 10 ? 'text-amber-600' : 'text-slate-700'">
                            {{ expectedDeviation !== null ? (expectedDeviation > 0 ? '+' : '') + expectedDeviation.toFixed(2) + '%' : '--' }}
                          </span>
                          <span class="text-[10px] text-slate-400 font-mono">预期: {{ expectedRatio.toFixed(2) }} → 现值: {{ currentDiff.toFixed(2) }}</span>
                        </div>
                     </div>
                  </div>
               </div>
            </div>
          </div>

          <div v-if="loadingPrice" class="absolute inset-0 bg-white/70 backdrop-blur-[2px] flex items-center justify-center rounded-2xl z-20">
             <div class="flex flex-col items-center gap-4 bg-white px-8 py-6 rounded-2xl shadow-xl border border-slate-100">
                <div class="w-10 h-10 border-4 border-indigo-100 border-t-indigo-500 rounded-full animate-spin"></div>
                <div class="text-center">
                   <p class="text-sm font-bold text-slate-800 uppercase tracking-widest">Loading Analytics</p>
                   <p class="text-[10px] text-slate-500 mt-1 font-mono uppercase">Synchronizing Time-Series Data...</p>
                </div>
            </div>
          </div>
        </div>

        <!-- DuPont Decomposition -->
        <div v-if="Object.keys(dupontData).length === 2" class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
          <div class="flex items-center justify-between mb-5">
            <div class="flex items-center gap-3">
              <div class="w-1.5 h-6 bg-amber-500 rounded-full"></div>
              <h3 class="text-sm font-bold text-slate-800">杜邦拆解 (DuPont Analysis)</h3>
            </div>
            <div class="text-[10px] text-slate-400 font-bold uppercase tracking-widest">
              ROE = 净利率 × 资产周转率 × 权益乘数
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div v-for="factor in dupontFactors" :key="factor.key" class="bg-slate-50 rounded-xl p-4 border border-slate-100">
              <div class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">{{ factor.label }}</div>
              <div class="space-y-3">
                <div v-for="(sym, idx) in selectedSymbols" :key="sym" class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <div :class="['w-2 h-2 rounded-full', idx === 0 ? 'bg-indigo-500' : 'bg-cyan-500']"></div>
                    <span class="text-xs font-bold text-slate-600 truncate max-w-[100px]">{{ getStockName(sym) }}</span>
                  </div>
                  <span class="text-sm font-black font-mono text-slate-800">
                    {{ getDupontLatest(sym, factor.key) != null ? getDupontLatest(sym, factor.key)!.toFixed(factor.precision) + factor.unit : '--' }}
                  </span>
                </div>
                <!-- 对比条 -->
                <div class="h-2 bg-slate-200 rounded-full overflow-hidden flex">
                  <div
                    class="h-full bg-indigo-500 rounded-l-full transition-all duration-500"
                    :style="{ width: getDupontBarWidth(selectedSymbols[0], factor.key) + '%' }"
                  ></div>
                  <div
                    class="h-full bg-cyan-500 rounded-r-full transition-all duration-500"
                    :style="{ width: getDupontBarWidth(selectedSymbols[1], factor.key) + '%' }"
                  ></div>
                </div>
              </div>
            </div>
          </div>

          <!-- ROE 还原 -->
          <div class="mt-5 pt-4 border-t border-slate-100 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div v-for="(sym, idx) in selectedSymbols" :key="'roe-'+sym" class="flex items-center justify-between bg-slate-50 rounded-xl px-4 py-3 border border-slate-100">
              <div class="flex items-center gap-2">
                <div :class="['w-2 h-2 rounded-full', idx === 0 ? 'bg-indigo-500' : 'bg-cyan-500']"></div>
                <span class="text-xs font-bold text-slate-600">{{ getStockName(sym) }}</span>
              </div>
              <div class="text-xs font-mono text-slate-500">
                ROE = <span class="font-bold text-slate-800">{{ getDupontRoe(sym) != null ? getDupontRoe(sym)!.toFixed(1) + '%' : '--' }}</span>
                <span class="text-slate-400 ml-1">
                  {{ getDupontLatest(sym, 'net_margin') != null ? '= ' + getDupontLatest(sym, 'net_margin')!.toFixed(1) + '%' : '' }}
                  {{ getDupontLatest(sym, 'asset_turnover') != null ? ' × ' + getDupontLatest(sym, 'asset_turnover')!.toFixed(2) + 'x' : '' }}
                  {{ getDupontLatest(sym, 'equity_multiplier') != null ? ' × ' + getDupontLatest(sym, 'equity_multiplier')!.toFixed(2) + 'x' : '' }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div v-else-if="dupontLoading" class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex items-center gap-3">
          <div class="w-5 h-5 border-2 border-amber-200 border-t-amber-500 rounded-full animate-spin"></div>
          <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">加载杜邦数据...</span>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-32 bg-white rounded-[2rem] shadow-sm border border-dashed border-slate-300">
        <div class="w-24 h-24 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-8">
          <svg class="w-12 h-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/>
          </svg>
        </div>
        <h3 class="text-2xl font-black text-slate-800 uppercase tracking-tight">终端未就绪</h3>
        <p class="text-slate-500 mt-3 max-w-sm mx-auto text-sm leading-relaxed">
          请在上方监控列表中精确选择 <span class="text-indigo-600 font-bold underline underline-offset-4">2 只股票</span> 以启动基准对冲分析。系统将自动对齐时间轴并计算实时溢价。
        </p>
      </div>
    </main>

    <footer class="max-w-7xl mx-auto px-6 py-8 border-t border-slate-200 flex flex-col md:flex-row justify-between items-center gap-4">
       <div class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">© 2026 Sentiment Monitor Hedging Terminal</div>
       <div class="flex items-center gap-6">
          <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest hover:text-indigo-500 cursor-help transition-colors">Tencent Finance API Integrated</span>
          <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest hover:text-indigo-500 cursor-help transition-colors">ISO-GRID Date-Key Join Mode</span>
       </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'
import { stockApi, type RealtimePrice } from '@/api'
import { echarts, type ECharts } from '@/lib/echarts'

const store = useSentimentStore()

const timeScales = [
  { label: '1D 分时', value: 'minute' },
  { label: '30D 日线', value: '30d' },
  { label: '1Y 周线', value: '1y_week' },
  { label: '5Y 月线', value: '5y' },
  { label: '10Y 月线', value: '10y' },
]

const metricModes = [
  { label: '价格 (Price)', value: 'price' },
  { label: '市盈率 (PE)', value: 'pe' },
  { label: '市净率 (PB)', value: 'pb' },
  { label: '股息率 (DY)', value: 'dividend_yield' },
  { label: '回报率 (ROI)', value: 'roi' },
]

const calcModes = [
  { label: '差值 (A-B)', value: 'diff' },
  { label: '比值 (A/B)', value: 'ratio' },
]

const currentTimeScale = ref<string>('minute')
const currentMetricMode = ref<string>('price')
const currentCalcMode = ref<string>('diff')
const selectedSymbols = ref<string[]>([])
const loadingPrice = ref(false)

// 预期比值
const expectedRatio = ref<number | null>(null)
const editingExpected = ref(false)
const expectedInput = ref('')

const expectedStorageKey = computed(() => {
  if (selectedSymbols.value.length < 2) return ''
  const [a, b] = selectedSymbols.value
  return `expectedRatio_${a}_${b}_${currentMetricMode.value}_${currentCalcMode.value}`
})

function loadExpectedRatio() {
  const key = expectedStorageKey.value
  if (!key) { expectedRatio.value = null; return }
  const stored = localStorage.getItem(key)
  expectedRatio.value = stored !== null ? parseFloat(stored) : null
}

function saveExpectedRatio() {
  const val = parseFloat(expectedInput.value)
  if (isNaN(val)) return
  expectedRatio.value = val
  const key = expectedStorageKey.value
  if (key) localStorage.setItem(key, String(val))
  editingExpected.value = false
}

function clearExpectedRatio() {
  expectedRatio.value = null
  editingExpected.value = false
  const key = expectedStorageKey.value
  if (key) localStorage.removeItem(key)
}

function startEditExpected() {
  expectedInput.value = expectedRatio.value !== null ? String(expectedRatio.value) : ''
  editingExpected.value = true
}

const expectedDeviation = computed(() => {
  if (expectedRatio.value === null || expectedRatio.value === 0) return null
  return ((currentDiff.value - expectedRatio.value) / Math.abs(expectedRatio.value)) * 100
})

// 杜邦拆解
const dupontData = ref<Record<string, any>>({})
const dupontLoading = ref(false)

interface DupontFactor {
  label: string
  key: string
  unit: string
  precision: number
}
const dupontFactors: DupontFactor[] = [
  { label: '净利率', key: 'net_margin', unit: '%', precision: 1 },
  { label: '资产周转率', key: 'asset_turnover', unit: 'x', precision: 2 },
  { label: '权益乘数', key: 'equity_multiplier', unit: 'x', precision: 2 },
]

function getDupontLatest(symbol: string, key: string): number | null {
  const history = dupontData.value[symbol]?.quality_history
  if (!history || history.length === 0) return null
  const val = history[history.length - 1]?.[key]
  return val != null && !isNaN(val) ? val : null
}

function getDupontRoe(symbol: string): number | null {
  return getDupontLatest(symbol, 'roe')
}

function getDupontBarWidth(symbol: string, key: string): number {
  const a = getDupontLatest(selectedSymbols.value[0], key)
  const b = getDupontLatest(selectedSymbols.value[1], key)
  if (a == null || b == null) return 50
  const total = Math.abs(a) + Math.abs(b)
  if (total === 0) return 50
  const val = getDupontLatest(symbol, key)
  if (val == null) return 50
  return (Math.abs(val) / total) * 100
}

let _dupontSeq = 0
async function fetchDupontData() {
  if (selectedSymbols.value.length !== 2) { dupontData.value = {}; return }
  const seq = ++_dupontSeq
  dupontLoading.value = true
  try {
    const [a, b] = selectedSymbols.value
    const [resA, resB] = await Promise.all([
      stockApi.getQualityAnalysis(a, false),
      stockApi.getQualityAnalysis(b, false),
    ])
    if (seq !== _dupontSeq) return
    dupontData.value = { [a]: resA.data, [b]: resB.data }
  } catch {
    if (seq !== _dupontSeq) return
    dupontData.value = {}
  } finally {
    if (seq === _dupontSeq) dupontLoading.value = false
  }
}

// 搜索添加股票
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const searchFocused = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; return }
  searchTimer = setTimeout(async () => {
    try {
      const resp = await stockApi.searchStocks(q)
      searchResults.value = (resp.data || []).slice(0, 8)
    } catch { searchResults.value = [] }
  }, 300)
}

function onSearchBlur() {
  // 延迟关闭，让 mousedown 事件先触发
  setTimeout(() => { searchFocused.value = false }, 200)
}

function addFromSearch(stock: any) {
  const sym = normalizeSymbol(stock.symbol || stock.stock_symbol)
  toggleStock(sym)
  searchQuery.value = ''
  searchResults.value = []
}
const rtPrices = ref<Record<string, RealtimePrice>>({})
const comparisonData = ref<any[]>([])
const lastGoodComparisonData = ref<any[]>([])
const lastGoodCacheKey = ref('')
const dataNotice = ref('')
const historicalCache = ref<Record<string, any>>({})

const colors = ['#6366f1', '#14b8a6', '#f43f5e', '#f59e0b', '#8b5cf6', '#22c55e']
const defaultComparisonSymbols = ['SZ000423', 'SZ002304']

// Chart refs
const priceSpreadRef = ref<HTMLElement>()
let priceChart: ECharts | null = null

const drawdownRef = ref<HTMLElement>()
let drawdownChart: ECharts | null = null

function normalizeSymbol(symbol: string) {
  const raw = String(symbol || '').trim().toUpperCase()
  if (/^(SH|SZ|BJ)\d{6}$/.test(raw)) return raw
  const match = raw.match(/\d{6}/)
  if (!match) return raw
  const code = match[0]
  if (raw.includes('BJ') || code.startsWith('92') || code.startsWith('4') || code.startsWith('8')) return `BJ${code}`
  if (raw.includes('SH') || code.startsWith('6') || code.startsWith('9')) return `SH${code}`
  return `SZ${code}`
}

function getSeriesForSymbol(data: Record<string, any[]>, symbol: string) {
  const fixed = normalizeSymbol(symbol)
  return data?.[symbol] || data?.[fixed] || data?.[symbol.toUpperCase()] || []
}

function getCurrentCacheKey() {
  const symbols = selectedSymbols.value.map(normalizeSymbol)
  return `${[...symbols].sort().join(',')}_${currentTimeScale.value}`
}

function restoreLastGoodData(message: string) {
  if (lastGoodComparisonData.value.length && lastGoodCacheKey.value === getCurrentCacheKey()) {
    comparisonData.value = [...lastGoodComparisonData.value]
    dataNotice.value = message
    updatePriceChart()
    return true
  }
  dataNotice.value = message
  comparisonData.value = []
  updatePriceChart()
  return false
}

function buildRealtimeFallbackSeries(symbols: string[]) {
  const rt1 = rtPrices.value[symbols[0]]
  const rt2 = rtPrices.value[symbols[1]]
  if (!rt1?.price || !rt2?.price) return []

  const now = new Date()
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  const metrics1 = calculateIntradayMetrics({ time, price: rt1.price }, rt1, symbols[0])
  const metrics2 = calculateIntradayMetrics({ time, price: rt2.price }, rt2, symbols[1])
  const m = currentMetricMode.value
  const val1 = (metrics1 as any)[m] || 0
  const val2 = (metrics2 as any)[m] || 0

  return [{
    time,
    p1: val1,
    p2: val2,
    diff: currentCalcMode.value === 'ratio' ? (val2 > 0 ? val1 / val2 : 0) : val1 - val2,
    m1: metrics1,
    m2: metrics2,
  }]
}

function getStockName(symbol: string) {
  const fixed = normalizeSymbol(symbol)
  return store.getStockBySymbol(fixed)?.stock_name || symbol
}

function getRoiValue(symbol: string) {
  const p = rtPrices.value[symbol]
  if (!p || p.pe <= 0 || p.pb <= 0) return 0
  return store.calculateROI(symbol, p.pe, p.pb)
}

function getTimeScaleLabel(val: string) {
  return timeScales.find(s => s.value === val)?.label || ''
}

function getMetricLabel(val: string) {
  return metricModes.find(m => m.value === val)?.label || ''
}

function getStockColor(symbol: string) {
  const fixed = normalizeSymbol(symbol)
  const index = store.dashboardStocks.findIndex(s => normalizeSymbol(s.stock_symbol) === fixed)
  return colors[((index % colors.length) + colors.length) % colors.length]
}

function toggleStock(symbol: string) {
  const fixed = normalizeSymbol(symbol)
  if (selectedSymbols.value.includes(fixed)) {
    selectedSymbols.value = selectedSymbols.value.filter(s => s !== fixed)
  } else {
    if (selectedSymbols.value.length >= 2) {
      selectedSymbols.value = [selectedSymbols.value[1], fixed]
    } else {
      selectedSymbols.value = [...selectedSymbols.value, fixed]
    }
  }
}

function getAvailableComparisonSymbols() {
  const sourceStocks = store.stocks.length
    ? store.stocks.map(stock => stock.symbol)
    : store.dashboardStocks.map(stock => stock.stock_symbol)

  return [...new Set(sourceStocks.map(normalizeSymbol))]
}

function buildDefaultComparisonSelection(availableSymbols: string[], currentSymbols: string[] = []) {
  if (!availableSymbols.length) {
    return []
  }

  const availableSet = new Set(availableSymbols)
  const normalizedSelected = currentSymbols.map(normalizeSymbol)

  // 保留用户已选择的股票（不强制要求在 availableSet 中），只要格式合法即可
  const nextSelected = normalizedSelected.filter(s => /^\w{2}\d{6}$/.test(s))

  // 只在用户选择不足 2 只时，才用默认值填充
  for (const symbol of defaultComparisonSymbols) {
    if (nextSelected.length >= 2) break
    if (availableSet.has(symbol) && !nextSelected.includes(symbol)) {
      nextSelected.push(symbol)
    }
  }

  for (const symbol of availableSymbols) {
    if (nextSelected.length >= 2) break
    if (!nextSelected.includes(symbol)) {
      nextSelected.push(symbol)
    }
  }

  return nextSelected.slice(0, 2)
}

function reconcileSelectedSymbols() {
  const availableSymbols = getAvailableComparisonSymbols()
  const nextSelected = buildDefaultComparisonSelection(availableSymbols, selectedSymbols.value)

  if (nextSelected.length === selectedSymbols.value.length && nextSelected.every((symbol, index) => symbol === selectedSymbols.value[index])) {
    return
  }

  selectedSymbols.value = nextSelected.slice(0, 2)
}

const currentDiff = computed(() => {
  if (selectedSymbols.value.length < 2) return 0
  const p1 = rtPrices.value[selectedSymbols.value[0]]?.price || 0
  const p2 = rtPrices.value[selectedSymbols.value[1]]?.price || 0
  if (currentCalcMode.value === 'ratio') {
    return p2 > 0 ? p1 / p2 : 0
  }
  return p1 - p2
})

const priceDiffColor = computed(() => {
  if (currentDiff.value > 0) return 'text-rose-600'
  if (currentDiff.value < 0) return 'text-emerald-600'
  return 'text-slate-500'
})

const spreadStats = computed(() => {
  if (comparisonData.value.length === 0) return { maxVal: 0, maxDate: '--', minVal: 0, minDate: '--', avg: 0, std: 0, zScore: 0, range: '--', percentile: 0 }
  
  let maxVal = -Infinity, minVal = Infinity, sum = 0
  let maxDate = '', minDate = ''
  
  comparisonData.value.forEach(d => {
    if (d.diff > maxVal) { maxVal = d.diff; maxDate = d.time; }
    if (d.diff < minVal) { minVal = d.diff; minDate = d.time; }
    sum += d.diff
  })
  
  const avg = sum / (comparisonData.value.length || 1)
  
  let varianceSum = 0
  comparisonData.value.forEach(d => {
    varianceSum += Math.pow(d.diff - avg, 2)
  })
  const std = Math.sqrt(varianceSum / (comparisonData.value.length || 1))
  const zScore = std > 0 ? (currentDiff.value - avg) / std : 0
  
  let lessThanCurrent = 0
  comparisonData.value.forEach(d => {
     if (d.diff <= currentDiff.value) lessThanCurrent++
  })
  const percentile = (lessThanCurrent / (comparisonData.value.length || 1)) * 100
  const range = `${comparisonData.value[0].time} 至 ${comparisonData.value[comparisonData.value.length - 1].time}`
  
  return { maxVal, maxDate, minVal, minDate, avg, std, zScore, range, percentile }
})

const drawdownStats = computed(() => {
  if (comparisonData.value.length === 0) return { maxDrawdown: 0, currentDrawdown: 0, series: [] }
  
  let maxVal = -Infinity
  let maxDrawdown = 0
  let currentDrawdown = 0

  const series = comparisonData.value.map(d => {
    if (d.diff > maxVal) maxVal = d.diff
    const dd = maxVal - d.diff
    if (dd > maxDrawdown) maxDrawdown = dd
    return {
      time: d.time,
      drawdown: -dd,
      peak: maxVal
    }
  })

  currentDrawdown = -(series[series.length - 1].drawdown)

  return { maxDrawdown, currentDrawdown, series }
})

// 防重复请求标记
let _fetchSeq = 0

async function fetchComparisonData(force = false) {
  if (selectedSymbols.value.length !== 2) return
  const seq = ++_fetchSeq

  // 先修正 selectedSymbols，避免 watcher 重复触发（放在 loading 状态之前，防止闪烁）
  const symbols = selectedSymbols.value.map(normalizeSymbol)
  const needsFix = symbols.some((symbol, index) => symbol !== selectedSymbols.value[index])
  if (needsFix) {
    selectedSymbols.value = symbols
    // 修正后由 watcher 重新触发，此处直接返回避免重复请求
    return
  }

  const loadStart = Date.now()
  loadingPrice.value = true
  try {
    dataNotice.value = ''
    const rtLastPromise = stockApi.getComparisonRealtime(symbols, 'last', force)

    if (currentTimeScale.value === 'minute') {
      const [rtLastResp, rtMinResp] = await Promise.allSettled([
        rtLastPromise,
        stockApi.getComparisonRealtime(symbols, 'minute', force),
      ])
      // 检查是否已被更新的请求取代
      if (seq !== _fetchSeq) return
      if (rtLastResp.status === 'fulfilled') {
        rtPrices.value = rtLastResp.value.data as any
      } else {
        console.warn('[ComparisonView] realtime last failed:', rtLastResp.reason)
      }
      if (rtMinResp.status === 'fulfilled') {
        const minData = rtMinResp.value.data
        historicalCache.value[`${[...symbols].sort().join(',')}_minute`] = minData
        // 检查返回数据是否为空
        const hasData = symbols.some((sym: string) => {
          const series = minData?.[sym]
          return Array.isArray(series) && series.length > 0
        })
        if (!hasData) {
          dataNotice.value = '分时数据暂未返回，可能是非交易时段或数据源暂不可用。'
        }
      } else {
        console.warn('[ComparisonView] intraday minute failed:', rtMinResp.reason)
        dataNotice.value = '分时数据获取失败，请稍后重试。'
      }
    } else {
      const scale = currentTimeScale.value
      const cacheKey = `${[...symbols].sort().join(',')}_${scale}`
      let histPromise: Promise<any> | null = null
      if (!historicalCache.value[cacheKey]) {
        let limit = 30, period = 'day'
        if (scale === '30d') { limit = 30; period = 'day' }
        else if (scale === '1y_week') { limit = 52; period = '1y_week' }
        else if (scale === '5y') { limit = 60; period = 'month' }
        else if (scale === '10y') { limit = 120; period = 'month' }
        histPromise = stockApi.getComparisonHistorical([ ...symbols ], limit, period, force)
      }

      const [rtLastResp, histResp] = await Promise.allSettled([
        rtLastPromise,
        histPromise ?? Promise.resolve(null),
      ])
      // 检查是否已被更新的请求取代
      if (seq !== _fetchSeq) return
      if (rtLastResp.status === 'fulfilled') {
        rtPrices.value = rtLastResp.value.data as any
      } else {
        console.warn('[ComparisonView] realtime last failed:', rtLastResp.reason)
      }
      if (histResp.status === 'fulfilled' && histResp.value) {
        historicalCache.value[cacheKey] = histResp.value.data
      } else if (histResp.status === 'rejected') {
        console.warn('[ComparisonView] historical data failed:', histResp.reason)
        dataNotice.value = '历史数据获取失败，请稍后重试。'
      }
    }
    // 兜底：如果 rtPrices 为空，尝试从 store 全局实时价格获取
    if (!Object.keys(rtPrices.value).length) {
      const fallback: Record<string, any> = {}
      for (const sym of symbols) {
        const storePrice = store.realtimePrices[sym]
        if (storePrice?.price) {
          fallback[sym] = storePrice
        }
      }
      if (Object.keys(fallback).length) {
        console.info('[ComparisonView] using store realtimePrices fallback')
        rtPrices.value = fallback
      }
    }
    await nextTick()
    remapComparisonData()
  } catch (e) {
    console.error('[ComparisonView] Fetch Comparison Error', e)
    // catch 兜底：也尝试 store 数据
    const symbols = selectedSymbols.value
    const fallback: Record<string, any> = {}
    for (const sym of symbols) {
      const storePrice = store.realtimePrices[sym]
      if (storePrice?.price) fallback[sym] = storePrice
    }
    if (Object.keys(fallback).length) rtPrices.value = fallback
    restoreLastGoodData('本次刷新暂未拿到完整数据，已保留上一轮有效走势。')
  } finally {
    // 只有最新的请求才控制 loading 状态，防止旧请求的 finally 覆盖新请求的 loading
    if (seq === _fetchSeq) {
      // 确保 loading 动画至少显示 500ms，避免请求太快导致用户感知不到加载状态
      const elapsed = Date.now() - loadStart
      if (elapsed < 500) {
        await new Promise(r => setTimeout(r, 500 - elapsed))
      }
      loadingPrice.value = false
    }
  }
}

function calculatePearson(x: number[], y: number[]) {
  const n = x.length;
  if (n === 0) return 0;
  const sumX = x.reduce((a, b) => a + b, 0);
  const sumY = y.reduce((a, b) => a + b, 0);
  const sumX2 = x.reduce((a, b) => a + b * b, 0);
  const sumY2 = y.reduce((a, b) => a + b * b, 0);
  const sumXY = x.reduce((a, b, i) => a + b * y[i], 0);
  const numerator = n * sumXY - sumX * sumY;
  const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
  if (denominator === 0) return 0;
  return numerator / denominator;
}

function remapComparisonData() {
  const symbols = selectedSymbols.value
  const scale = currentTimeScale.value
  const m = currentMetricMode.value
  const cacheKey = getCurrentCacheKey()
  const data = historicalCache.value[cacheKey]
  if (!data) {
    restoreLastGoodData('当前组合暂未返回走势数据，已保留上一轮有效图表。')
    return
  }

  const s1 = getSeriesForSymbol(data, symbols[0])
  const s2 = getSeriesForSymbol(data, symbols[1])

  if (!s1.length || !s2.length) {
    const fallbackSeries = scale === 'minute' ? buildRealtimeFallbackSeries(symbols) : []
    if (fallbackSeries.length) {
      comparisonData.value = fallbackSeries
      lastGoodComparisonData.value = [...fallbackSeries]
      dataNotice.value = '分时接口暂未返回完整分钟线，已用实时价生成当前点位。'
      updatePriceChart()
      return
    }

    restoreLastGoodData('当前组合返回的数据不完整，已保留上一轮有效走势。')
    return
  }

  comparisonData.value = s1.map((item: any, idx: number) => {
    const item2 = s2[idx]
    if (!item || !item2) return null
    
    if (scale === 'minute') {
       const rt = rtPrices.value[symbols[0]], rt2 = rtPrices.value[symbols[1]]
       const metrics1 = calculateIntradayMetrics(item, rt, symbols[0])
       const metrics2 = calculateIntradayMetrics(item2, rt2, symbols[1])
       const val1 = (metrics1 as any)[m] || 0
       const val2 = (metrics2 as any)[m] || 0

       // 兼容 HHMM 和 HH:MM 两种时间格式
       const rawTime = item.time || ''
       const formattedTime = rawTime.includes(':') ? rawTime.slice(0, 5) : `${rawTime.slice(0, 2)}:${rawTime.slice(2, 4)}`
       return {
         time: formattedTime,
         p1: val1,
         p2: val2,
         diff: currentCalcMode.value === 'ratio' ? (val2 > 0 ? val1 / val2 : 0) : val1 - val2,
         m1: metrics1,
         m2: metrics2
       }
    } else {
        const p1 = (item as any)[m] || 0
        const p2 = (item2 ? (item2 as any)[m] : 0) || 0
        
        return { 
          time: item.date, 
          p1, 
          p2, 
          diff: currentCalcMode.value === 'ratio' ? (p2 > 0 ? p1 / p2 : 0) : p1 - p2,
          m1: { price: item.price, pe: item.pe, pb: item.pb, dividend_yield: item.dividend_yield, roi: item.roi },
          m2: item2 ? { price: item2.price, pe: item2.pe, pb: item2.pb, dividend_yield: item2.dividend_yield, roi: item2.roi } : {}
        }
    }
  }).filter(Boolean)

  if (!comparisonData.value.length) {
    restoreLastGoodData('当前指标没有可绘制的数据，已保留上一轮有效走势。')
    return
  }

  const windowSize = 30;
  for (let i = 0; i < comparisonData.value.length; i++) {
    if (i < windowSize - 1) {
      comparisonData.value[i].corr = null;
    } else {
      const slice = comparisonData.value.slice(i - windowSize + 1, i + 1);
      const px1 = slice.map(d => d.p1);
      const px2 = slice.map(d => d.p2);
      comparisonData.value[i].corr = calculatePearson(px1, px2);
    }
  }

  lastGoodComparisonData.value = [...comparisonData.value]
  lastGoodCacheKey.value = cacheKey
  dataNotice.value = ''
  updatePriceChart()
}

async function refreshComparisonData() {
  if (selectedSymbols.value.length !== 2) return
  const cacheKey = getCurrentCacheKey()
  delete historicalCache.value[cacheKey]
  await fetchComparisonData(true)
}

function calculateIntradayMetrics(item: any, rt: any, _sym: string) {
  if (!item || !item.price) return { price: 0, pe: 0, pb: 0, dividend_yield: 0, roi: 0 }
  if (!rt) return { price: item.price, pe: 0, pb: 0, dividend_yield: 0, roi: 0 }
  
  // Dynamic Intraday Projection
  const pe = item.price * ((rt.pe || 0) / (rt.price || 1))
  const pb = item.price * ((rt.pb || 0) / (rt.price || 1))
  const dy = (rt.dividend_yield || 0) * ((rt.price || 1) / (item.price || 1))
  
  // ROE = PB / PE * 100
  let roe = pe > 0 ? (pb / pe * 100) : 0
  const roi = pb > 0 ? (roe / pb) + dy : 0

  return {
    price: item.price,
    pe: pe,
    pb: pb,
    dividend_yield: dy,
    roi: roi
  }
}

function updatePriceChart() {
  // 确保 DOM 已更新（loading 结束后容器才可见），再渲染图表
  nextTick(() => {
    _doUpdatePriceChart()
  })
}

function _doUpdatePriceChart() {
  if (!priceSpreadRef.value) {
    nextTick(() => {
      if (priceSpreadRef.value) _doUpdatePriceChart()
    })
    return
  }
  // 每次强制重建图表实例，避免旧实例状态污染
  if (priceChart) { priceChart.dispose(); priceChart = null }
  priceChart = echarts.init(priceSpreadRef.value)
  if (!comparisonData.value.length) {
    priceChart.clear()
    return
  }

  const n1 = getStockName(selectedSymbols.value[0])
  const n2 = getStockName(selectedSymbols.value[1])
  const mLabel = getMetricLabel(currentMetricMode.value)
  const chartData = [...comparisonData.value]

  const option = {
    backgroundColor: 'transparent',
    title: {
      text: `${n1} ⇌ ${n2}`,
      left: 'center',
      top: '10',
      itemGap: 8,
      textStyle: {
        color: '#1e293b',
        fontSize: 14,
        fontWeight: '900',
        fontFamily: 'Inter, system-ui',
        letterSpacing: 1
      },
      subtext: `Quantitative Spread Analysis | ${mLabel}`,
      subtextStyle: {
        color: '#94a3b8',
        fontSize: 10,
        fontWeight: 'bold',
        textTransform: 'uppercase'
      }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: 'rgba(226, 232, 240, 1)',
      borderWidth: 1,
      padding: 0,
      textStyle: { color: '#1e293b' },
      extraCssText: 'box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1); border-radius: 12px; border: 1px solid #e2e8f0;',
      formatter: (params: any) => {
        const dataIndex = params[0].dataIndex
        const data = chartData[dataIndex]
        if (!data) return ''

        const m1 = data.m1 || {}
        const m2 = data.m2 || {}

        const row = (label: string, v1: any, v2: any, unit: string = '') => {
          const diff = (v1 || 0) - (v2 || 0)
          const diffColor = diff > 0 ? 'text-rose-600' : (diff < 0 ? 'text-emerald-600' : 'text-slate-400')
          const fmt = (v: any) => (v !== undefined && v !== null) ? v.toFixed(2) + unit : '--'
          
          return `
            <tr class="border-b border-slate-50 last:border-0">
              <td class="py-2 text-[10px] font-bold text-slate-400 uppercase tracking-tighter">${label}</td>
              <td class="py-2 px-3 text-xs font-mono font-bold text-indigo-600 text-right">${fmt(v1)}</td>
              <td class="py-2 px-3 text-xs font-mono font-bold text-emerald-600 text-right">${fmt(v2)}</td>
              <td class="py-2 pl-3 text-xs font-mono font-bold ${diffColor} text-right">${v1 !== undefined && v2 !== undefined ? (diff > 0 ? '+' : '') + diff.toFixed(2) + unit : '--'}</td>
            </tr>
          `
        }

        const unitMap: Record<string, string> = { 'minute': 'MIN', '30d': 'D', '1y': 'W', '5y': 'M', '10y': 'Y' }
        const corrLabel = `30${unitMap[currentTimeScale.value] || 'D'} Rolling Corr`

        return `
          <div class="p-4 min-w-[320px] bg-white rounded-xl shadow-2xl border border-slate-100">
            <div class="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
               <span class="text-[11px] font-black text-slate-800 uppercase tracking-wider">${data.time}</span>
               <span class="text-[9px] px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-full font-bold uppercase">Hedge Matrix</span>
            </div>
            
            <table class="w-full border-collapse">
              <thead>
                <tr class="text-[9px] text-slate-400 uppercase tracking-widest">
                  <th class="text-left font-normal pb-2">Metric</th>
                  <th class="text-right font-normal pb-2 px-3">${n1.slice(0, 4)}</th>
                  <th class="text-right font-normal pb-2 px-3">${n2.slice(0, 4)}</th>
                  <th class="text-right font-normal pb-2 pl-3">Spread</th>
                </tr>
              </thead>
              <tbody>
                ${row('Price', m1.price, m2.price)}
                ${row('PE (TTM)', m1.pe, m2.pe)}
                ${row('PB (MRQ)', m1.pb, m2.pb)}
                ${row('Yield', m1.dividend_yield, m2.dividend_yield, '%')}
              </tbody>
            </table>
            
            ${data.corr !== undefined && data.corr !== null ? `
            <div class="mt-3 pt-2 border-t border-slate-50 flex items-center justify-between">
               <span class="text-[9px] text-slate-400 font-bold uppercase">${corrLabel}</span>
               <span class="text-[11px] font-mono font-black ${data.corr > 0.5 ? 'text-emerald-600' : (data.corr > 0 ? 'text-amber-500' : 'text-rose-600')}">${data.corr.toFixed(2)}</span>
            </div>
            ` : ''}
            
            <div class="mt-3 pt-2 border-t border-slate-50 flex items-center justify-between">
               <span class="text-[9px] text-slate-400 font-bold uppercase font-mono italic">Primary Focus: ${mLabel}</span>
               <div class="flex items-center gap-1">
                  <span class="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse"></span>
                  <span class="text-[9px] text-indigo-600 font-black uppercase">Live ISO-Grid</span>
               </div>
            </div>
          </div>
        `
      }
    },
    visualMap: [
      {
        show: false,
        dimension: 1,
        seriesIndex: 0,
        pieces: [
          { gt: spreadStats.value.avg + 2 * spreadStats.value.std, color: '#f43f5e' },
          { lt: spreadStats.value.avg - 2 * spreadStats.value.std, color: '#10b981' },
        ],
        outOfRange: { color: '#6366f1' }
      },
      {
        show: false,
        dimension: 1,
        seriesIndex: 1,
        pieces: [
          { gt: 0.5, color: '#10b981' },  // 股价走势同步
          { lte: 0, color: '#f43f5e' }    // 股价走势反向
        ],
        outOfRange: { color: '#94a3b8' }  // 股价走势无关
      }
    ],
    grid: [
      { left: '1%', right: '1%', top: '10%', height: '60%', containLabel: true },
      { left: '1%', right: '1%', top: '75%', height: '20%', containLabel: true }
    ],
    xAxis: [
      {
        type: 'category',
        gridIndex: 0,
        data: comparisonData.value.map(d => {
          if (currentTimeScale.value === 'minute') return d.time;
          if (currentTimeScale.value === '5y' || currentTimeScale.value === '10y') return d.time.slice(0, 7);
          return d.time.length > 5 ? d.time.slice(5) : d.time;
        }), 
        axisLine: { lineStyle: { color: 'rgba(0,0,0,0.1)' } },
        axisLabel: { show: false },
        axisPointer: { show: true }
      },
      {
        type: 'category',
        gridIndex: 1,
        data: comparisonData.value.map(d => {
          if (currentTimeScale.value === 'minute') return d.time;
          if (currentTimeScale.value === '5y' || currentTimeScale.value === '10y') return d.time.slice(0, 7);
          return d.time.length > 5 ? d.time.slice(5) : d.time;
        }),
        axisLine: { lineStyle: { color: 'rgba(0,0,0,0.1)' } },
        axisLabel: {
          color: '#475569', fontSize: 10, fontWeight: '800', fontFamily: 'Monaco, Inter',
          interval: currentTimeScale.value === 'minute' ? 29 : 'auto',
        },
        axisPointer: { show: true }
      }
    ],
    yAxis: [
      {
        type: 'value',
        scale: true,
        gridIndex: 0,
        position: 'right',
        splitLine: { lineStyle: { color: 'rgba(0,0,0,0.05)' } },
        axisLabel: { color: '#475569', fontSize: 10, fontWeight: '800', fontFamily: 'Monaco, Inter' }
      },
      {
        type: 'value',
        gridIndex: 1,
        min: -1,
        max: 1,
        position: 'right',
        splitLine: { lineStyle: { color: 'rgba(0,0,0,0.05)', type: 'dashed' } },
        axisLabel: { color: '#475569', fontSize: 9, fontFamily: 'Monaco, Inter' }
      }
    ],
    series: [
      {
        name: 'Spread',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        showSymbol: false,
        smooth: true,
        data: comparisonData.value.map(d => d.diff),
        lineStyle: { width: 3, color: '#6366f1', shadowBlur: 10, shadowColor: 'rgba(99, 102, 241, 0.2)' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(99, 102, 241, 0.15)' },
            { offset: 1, color: 'rgba(99, 102, 241, 0)' }
          ])
        },
        markPoint: {
          symbol: 'circle',
          symbolSize: 5,
          data: [
            { 
              type: 'max', 
              name: 'Max', 
              itemStyle: { color: '#f43f5e' }, 
              label: { 
                show: true, 
                position: 'top', 
                fontWeight: '900', 
                fontSize: 10,
                color: '#f43f5e',
                formatter: (p: any) => parseFloat(p.value).toFixed(2)
              } 
            },
            { 
              type: 'min', 
              name: 'Min', 
              itemStyle: { color: '#10b981' }, 
              label: { 
                show: true, 
                position: 'bottom', 
                fontWeight: '900', 
                fontSize: 10,
                color: '#10b981',
                formatter: (p: any) => parseFloat(p.value).toFixed(2)
              } 
            },
            {
              name: 'Latest',
              coord: [comparisonData.value.length - 1, comparisonData.value[comparisonData.value.length - 1].diff],
              value: (comparisonData.value[comparisonData.value.length - 1].diff).toFixed(2),
              itemStyle: { color: '#6366f1' },
              label: { 
                show: true, 
                position: 'right', 
                fontWeight: '900', 
                fontSize: 11,
                backgroundColor: '#6366f1',
                color: '#fff',
                padding: [3, 6],
                borderRadius: 4,
                formatter: '{c}'
              },
              symbolSize: 8
            }
          ]
        },
        markLine: {
          symbol: 'none',
          data: [
            { yAxis: spreadStats.value.avg, lineStyle: { color: '#6366f1', type: 'dashed', width: 1.5 }, label: { show: true, position: 'insideEndTop', formatter: 'Mean', color: '#6366f1', fontSize: 9 } },
            { yAxis: spreadStats.value.avg + spreadStats.value.std, lineStyle: { color: 'rgba(99,102,241,0.3)', type: 'solid', width: 1 }, label: { show: true, position: 'insideEndTop', formatter: '+1σ', color: 'rgba(99,102,241,0.6)', fontSize: 9 } },
            { yAxis: spreadStats.value.avg - spreadStats.value.std, lineStyle: { color: 'rgba(99,102,241,0.3)', type: 'solid', width: 1 }, label: { show: true, position: 'insideEndBottom', formatter: '-1σ', color: 'rgba(99,102,241,0.6)', fontSize: 9 } },
            { yAxis: spreadStats.value.avg + 2 * spreadStats.value.std, lineStyle: { color: 'rgba(244,63,94,0.5)', type: 'dashed', width: 1 }, label: { show: true, position: 'insideEndTop', formatter: '+2σ', color: '#f43f5e', fontSize: 9 } },
            { yAxis: spreadStats.value.avg - 2 * spreadStats.value.std, lineStyle: { color: 'rgba(16,185,129,0.5)', type: 'dashed', width: 1 }, label: { show: true, position: 'insideEndBottom', formatter: '-2σ', color: '#10b981', fontSize: 9 } },
            { yAxis: currentCalcMode.value === 'ratio' ? 1 : 0, lineStyle: { color: 'rgba(0,0,0,0.15)', type: 'solid', width: 1.5 }, label: { show: false } },
            ...(expectedRatio.value !== null ? [{ yAxis: expectedRatio.value, lineStyle: { color: '#f59e0b', type: 'dashed', width: 2 }, label: { show: true, position: 'insideEndTop', formatter: '预期 ' + expectedRatio.value.toFixed(2), color: '#d97706', fontSize: 10, fontWeight: 'bold' } }] : [])
          ],
          label: { show: false }
        }
      },
      {
        name: 'Correlation',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: false,
        smooth: true,
        data: comparisonData.value.map(d => d.corr),
        lineStyle: { width: 1.5 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(148, 163, 184, 0.1)' },
            { offset: 1, color: 'rgba(148, 163, 184, 0)' }
          ])
        },
        markLine: {
          symbol: 'none',
          data: [
            { yAxis: 0, lineStyle: { color: 'rgba(0,0,0,0.1)', type: 'solid', width: 1 } },
            { yAxis: 0.5, lineStyle: { color: 'rgba(244,63,94,0.5)', type: 'dashed', width: 1 }, label: { show: true, position: 'insideStartTop', formatter: 'Breakdown (0.5)', fontSize: 9, color: '#f43f5e' } }
          ],
          label: { show: false }
        }
      }
    ]
  }
  priceChart.setOption(option, true)
  // 强制重新计算容器尺寸，防止容器刚显示时尺寸为 0
  setTimeout(() => { priceChart?.resize() }, 100)

  updateDrawdownChart()
}

function updateDrawdownChart() {
  if (!drawdownRef.value) {
    nextTick(() => {
      if (drawdownRef.value) updateDrawdownChart()
    })
    return
  }
  if (drawdownChart) { drawdownChart.dispose(); drawdownChart = null }
  drawdownChart = echarts.init(drawdownRef.value)
  if (!drawdownStats.value.series.length) {
    drawdownChart.clear()
    return
  }

  const chartData = drawdownStats.value.series
  
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const d = chartData[params[0].dataIndex]
        return `
          <div class="p-3 bg-white rounded-xl shadow-lg border border-slate-100 min-w-[150px]">
            <div class="font-bold text-slate-700 mb-2 border-b border-slate-100 pb-1">${d.time}</div>
            <div class="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">区间高点: <span class="text-indigo-600 font-mono">${d.peak.toFixed(2)}</span></div>
            <div class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">回撤深度: <span class="text-rose-600 font-mono">${Math.abs(d.drawdown).toFixed(2)}</span></div>
          </div>
        `
      }
    },
    grid: { left: '1%', right: '1%', bottom: '5%', top: '5%', containLabel: true },
    xAxis: {
      type: 'category',
      data: chartData.map((d: any) => d.time),
      show: false
    },
    yAxis: {
      type: 'value',
      position: 'right',
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.05)' } },
      axisLabel: { color: '#94a3b8', fontSize: 10, fontFamily: 'Monaco, Inter' }
    },
    series: [
      {
        name: 'Drawdown',
        type: 'line',
        step: 'end',
        showSymbol: false,
        data: chartData.map((d: any) => d.drawdown),
        lineStyle: { width: 1.5, color: '#f43f5e' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(244, 63, 94, 0.2)' },
            { offset: 1, color: 'rgba(244, 63, 94, 0)' }
          ])
        }
      }
    ]
  }
  drawdownChart.setOption(option, true)
  setTimeout(() => { drawdownChart?.resize() }, 100)
}

const handleResize = () => {
  priceChart?.resize()
  drawdownChart?.resize()
}

onMounted(async () => {
  // 并行加载 store 数据，不阻塞
  await Promise.all([
    store.stocks.length ? Promise.resolve() : store.fetchStocks(),
    store.sentimentData.length ? Promise.resolve() : store.fetchLatestSentiment(),
  ])
  // 实时价格不阻塞（兜底用，没有也不影响核心功能）
  if (!Object.keys(store.realtimePrices).length) {
    store.fetchRealtimePrices().catch(() => {})
  }

  selectedSymbols.value = buildDefaultComparisonSelection(getAvailableComparisonSymbols())

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  priceChart?.dispose()
  drawdownChart?.dispose()
})

watch([selectedSymbols, currentTimeScale], () => {
  fetchComparisonData()
}, { immediate: true })

watch([currentMetricMode, currentCalcMode], () => {
  remapComparisonData()
  loadExpectedRatio()
})

watch([selectedSymbols], () => {
  loadExpectedRatio()
  fetchDupontData()
}, { deep: true, immediate: true })

watch(() => store.dashboardStocks.map(stock => stock.stock_symbol), () => {
  reconcileSelectedSymbols()
})
</script>

<style scoped>
.text-gradient {
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-image: linear-gradient(to right, var(--tw-gradient-from), var(--tw-gradient-to));
}
</style>
