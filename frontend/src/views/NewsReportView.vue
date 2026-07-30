<template>
  <div class="h-screen bg-[#0f172a] text-slate-300 font-sans p-4 overflow-hidden flex flex-col">
    <!-- 头部：查询 -->
    <header class="flex items-center justify-between mb-3 shrink-0">
      <div class="flex items-center gap-2">
        <div class="bg-cyan-500 rounded-lg p-2 shadow-[0_0_10px_rgba(6,182,212,0.4)]">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10l4 4v10a2 2 0 01-2 2zM17 8h-4v4h4V8zm-8 0H7v1h2V8zm0 3H7v1h2v-1zm0 3H7v1h2v-1zm4-3h-1v1h1v-1zm0 3h-1v1h1v-1z"/></svg>
        </div>
        <div>
          <h1 class="text-lg font-black text-white tracking-wide">个股资讯报告</h1>
          <p class="text-[10px] text-slate-500 tracking-widest mt-0.5">多源聚合 · 按重要度排序 · 结构化 Markdown</p>
        </div>
      </div>
      <router-link to="/" class="flex items-center gap-1.5 px-3 py-1.5 bg-[#1e293b] hover:bg-slate-700 text-slate-300 rounded border border-slate-700 transition-colors text-[11px]">
        返回终端
      </router-link>
    </header>

    <!-- 查询栏 -->
    <div class="flex flex-wrap items-center gap-2 mb-3 shrink-0">
      <input
        v-model="query"
        @keyup.enter="generate"
        placeholder="输入公司名或代码，如 东阿阿胶 / 000423 / SZ000423"
        class="flex-1 min-w-[260px] px-3 py-2 bg-[#1e293b] border border-slate-700 rounded text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
      />
      <select v-model.number="days" class="px-3 py-2 bg-[#1e293b] border border-slate-700 rounded text-sm text-slate-200 focus:outline-none focus:border-cyan-500">
        <option :value="7">近 7 天</option>
        <option :value="15">近 15 天</option>
        <option :value="30">近 30 天</option>
      </select>
      <button
        @click="generate"
        :disabled="loading"
        class="flex items-center gap-1.5 px-4 py-2 bg-[#00df9a] hover:bg-[#00c98a] disabled:opacity-50 text-slate-900 font-bold rounded shadow-[0_0_10px_rgba(0,223,154,0.3)] transition-all text-sm"
      >
        <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
        <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        {{ loading ? '生成中…' : '生成报告' }}
      </button>
      <button
        v-if="result"
        @click="copyMarkdown"
        class="flex items-center gap-1.5 px-3 py-2 bg-[#1e293b] hover:bg-slate-700 text-slate-300 rounded border border-slate-700 transition-colors text-[11px]"
      >
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
        {{ copied ? '已复制' : '复制 Markdown' }}
      </button>
    </div>

    <!-- 错误 -->
    <div v-if="error" class="mb-3 px-4 py-3 bg-red-500/10 border border-red-500/30 text-red-300 rounded text-sm shrink-0">
      {{ error }}
    </div>

    <!-- 结果 -->
    <main v-if="result" class="flex-1 overflow-y-auto pr-1 space-y-4">
      <!-- 概览 -->
      <section class="bg-[#172033] border border-slate-700/60 rounded-xl p-4">
        <div class="flex items-center justify-between flex-wrap gap-2">
          <div class="flex items-center gap-3">
            <h2 class="text-xl font-black text-white">{{ result.name }}</h2>
            <span class="px-2 py-0.5 bg-indigo-500/15 text-indigo-300 rounded text-xs font-bold border border-indigo-500/30">{{ result.symbol }}</span>
            <span class="text-[11px] text-slate-500">解析方式: {{ result.resolved_by }}</span>
          </div>
          <div class="flex flex-wrap gap-2 text-[11px]">
            <span class="px-2 py-1 bg-slate-700/40 rounded">公告 {{ result.counts.announcement }}</span>
            <span class="px-2 py-1 bg-slate-700/40 rounded">新闻 {{ result.counts.news }}</span>
            <span class="px-2 py-1 bg-slate-700/40 rounded">研报 {{ result.counts.report }}</span>
            <span class="px-2 py-1 bg-slate-700/40 rounded">社区 {{ result.counts.community }}</span>
          </div>
        </div>
        <div v-if="overviewText" class="mt-2 text-sm text-slate-400">{{ overviewText }}</div>
        <div class="mt-1 text-[10px] text-slate-600">资讯范围：{{ result.range_start }} ~ {{ result.range_end }} ｜ 生成于 {{ result.generated_at }}</div>
      </section>

      <!-- 重要公告 -->
      <section v-if="result.items.announcement.length" class="bg-[#172033] border border-slate-700/60 rounded-xl p-4">
        <h3 class="text-sm font-bold text-amber-300 mb-2">📢 重要公告 ⭐⭐⭐</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-slate-500 text-left border-b border-slate-700">
                <th class="py-1 pr-3 font-medium">日期</th>
                <th class="py-1 pr-3 font-medium">标题</th>
                <th class="py-1 font-medium">来源</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(it, i) in result.items.announcement" :key="'a'+i" class="border-b border-slate-800/60">
                <td class="py-1.5 pr-3 text-slate-400 whitespace-nowrap">{{ it.pub_date || '—' }}</td>
                <td class="py-1.5 pr-3">
                  <a v-if="it.url" :href="it.url" target="_blank" rel="noopener" class="text-indigo-300 hover:text-indigo-200 hover:underline break-words">{{ it.title }}</a>
                  <span v-else class="text-slate-200 break-words">{{ it.title }}</span>
                </td>
                <td class="py-1.5 text-slate-400 whitespace-nowrap">{{ it.source || '巨潮/东财' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 重要新闻 -->
      <section v-if="result.items.news.length" class="bg-[#172033] border border-slate-700/60 rounded-xl p-4">
        <h3 class="text-sm font-bold text-cyan-300 mb-2">📰 重要新闻 ⭐⭐</h3>
        <div class="space-y-2">
          <div v-for="(it, i) in result.items.news" :key="'n'+i" class="flex items-start gap-2 text-sm">
            <span class="text-slate-600 mt-0.5">{{ i + 1 }}.</span>
            <div class="flex-1 min-w-0">
              <a v-if="it.url" :href="it.url" target="_blank" rel="noopener" class="text-indigo-300 hover:text-indigo-200 hover:underline font-medium break-words">{{ it.title }}</a>
              <span v-else class="text-slate-200 font-medium break-words">{{ it.title }}</span>
              <div class="text-[11px] text-slate-500 mt-0.5">{{ it.source }} · {{ it.pub_date || '—' }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 机构动态 -->
      <section v-if="result.items.report.length" class="bg-[#172033] border border-slate-700/60 rounded-xl p-4">
        <h3 class="text-sm font-bold text-emerald-300 mb-2">📈 机构动态（研报）</h3>
        <div class="space-y-2">
          <div v-for="(it, i) in result.items.report" :key="'r'+i" class="text-sm flex items-start gap-2">
            <span class="text-amber-400 font-bold whitespace-nowrap">{{ it.rating || '研报' }}</span>
            <div class="flex-1 min-w-0">
              <a v-if="it.url" :href="it.url" target="_blank" rel="noopener" class="text-slate-200 hover:text-indigo-200 hover:underline break-words">{{ it.title }}</a>
              <span v-else class="text-slate-200 break-words">{{ it.title }}</span>
              <div class="text-[11px] text-slate-500 mt-0.5">{{ it.org || '机构' }} · {{ it.pub_date || '—' }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 市场热议 -->
      <section v-if="result.items.community.length" class="bg-[#172033] border border-slate-700/60 rounded-xl p-4">
        <h3 class="text-sm font-bold text-fuchsia-300 mb-2">💬 市场热议（社区）</h3>
        <div class="space-y-2">
          <div v-for="(it, i) in result.items.community" :key="'c'+i" class="text-sm">
            <a v-if="it.url" :href="it.url" target="_blank" rel="noopener" class="text-slate-200 hover:text-indigo-200 hover:underline break-words">{{ it.title }}</a>
            <span v-else class="text-slate-200 break-words">{{ it.title }}</span>
            <div class="text-[11px] text-slate-500 mt-0.5">雪球 · {{ it.pub_date || '—' }}</div>
          </div>
        </div>
      </section>
    </main>

    <!-- 空态 -->
    <div v-else-if="!loading && !error" class="flex-1 flex flex-col items-center justify-center text-slate-600">
      <svg class="w-12 h-12 mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10l4 4v10a2 2 0 01-2 2zM17 8h-4v4h4V8z"/></svg>
      <p class="text-sm">输入股票名称或代码，生成多源资讯报告</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { newsReportApi } from '@/api'

const query = ref('东阿阿胶')
const days = ref(7)
const loading = ref(false)
const error = ref('')
const result = ref<any>(null)
const copied = ref(false)

const overviewText = computed(() => {
  const o = result.value?.overview
  if (!o) return ''
  const parts: string[] = []
  if (o.industry) parts.push(`行业：${o.industry}`)
  if (o.total_market_cap) parts.push(`总市值：${o.total_market_cap}`)
  return parts.join(' ｜ ')
})

async function generate() {
  if (!query.value.trim() || loading.value) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const res = await newsReportApi.getReport(query.value.trim(), days.value)
    result.value = res.data
  } catch (e: any) {
    error.value = e?.response?.data?.error || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

async function copyMarkdown() {
  if (!result.value?.markdown) return
  try {
    await navigator.clipboard.writeText(result.value.markdown)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    // 降级：忽略
  }
}
</script>
