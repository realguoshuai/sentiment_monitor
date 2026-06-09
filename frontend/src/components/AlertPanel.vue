<template>
  <div class="fixed bottom-4 right-4 z-50">
    <!-- 告警按钮 -->
    <button
      @click="isOpen = !isOpen"
      class="relative w-12 h-12 bg-[#1e293b] hover:bg-slate-700 rounded-full shadow-lg border border-slate-700 flex items-center justify-center transition-all"
    >
      <svg class="w-5 h-5 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
      </svg>
      <!-- 未读红点 -->
      <span
        v-if="unreadCount > 0"
        class="absolute -top-1 -right-1 w-5 h-5 bg-rose-500 rounded-full text-[10px] text-white flex items-center justify-center font-bold"
      >
        {{ unreadCount > 9 ? '9+' : unreadCount }}
      </span>
    </button>

    <!-- 告警面板 -->
    <div
      v-if="isOpen"
      class="absolute bottom-16 right-0 w-80 bg-[#1e293b] rounded-xl shadow-2xl border border-slate-700 overflow-hidden"
    >
      <!-- 头部 -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-slate-700">
        <div class="flex items-center gap-2">
          <span class="text-sm font-bold text-white">告警通知</span>
          <span v-if="unreadCount > 0" class="px-1.5 py-0.5 bg-rose-500/20 text-rose-400 rounded text-[10px] font-bold">
            {{ unreadCount }} 未读
          </span>
        </div>
        <div class="flex items-center gap-2">
          <button
            v-if="unreadCount > 0"
            @click="handleMarkAllRead"
            class="text-[10px] text-cyan-400 hover:text-cyan-300"
          >
            全部已读
          </button>
          <button @click="isOpen = false" class="text-slate-400 hover:text-white">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- 告警列表 -->
      <div class="max-h-96 overflow-y-auto">
        <div v-if="logs.length === 0" class="p-8 text-center text-slate-500 text-sm">
          暂无告警
        </div>
        <div
          v-for="log in logs"
          :key="log.id"
          @click="handleMarkRead(log.id)"
          class="px-4 py-3 border-b border-slate-700/50 hover:bg-slate-700/30 cursor-pointer transition-colors"
          :class="{ 'bg-slate-700/20': !log.is_read }"
        >
          <div class="flex items-start justify-between mb-1">
            <div class="flex items-center gap-2">
              <span class="text-xs font-bold text-white">{{ log.stock_name }}</span>
              <span class="text-[10px] text-slate-400">{{ log.stock_symbol }}</span>
            </div>
            <span
              v-if="!log.is_read"
              class="w-2 h-2 bg-rose-500 rounded-full"
            />
          </div>
          <p class="text-xs text-slate-300 mb-1">{{ log.message }}</p>
          <div class="flex items-center justify-between">
            <span class="text-[10px] text-slate-500">{{ formatTime(log.triggered_at) }}</span>
            <span class="text-[10px] px-1.5 py-0.5 bg-slate-700 rounded text-slate-400">
              {{ log.rule_type_display }}
            </span>
          </div>
        </div>
      </div>

      <!-- 底部操作 -->
      <div class="px-4 py-2 border-t border-slate-700 flex items-center justify-between">
        <button
          @click="showRules = !showRules"
          class="text-[10px] text-slate-400 hover:text-white"
        >
          {{ showRules ? '隐藏规则' : '管理规则' }}
        </button>
        <button
          @click="handleCheckAlerts"
          :disabled="isChecking"
          class="text-[10px] text-cyan-400 hover:text-cyan-300 disabled:text-slate-500"
        >
          {{ isChecking ? '检查中...' : '立即检查' }}
        </button>
      </div>

      <!-- 规则管理 -->
      <div v-if="showRules" class="border-t border-slate-700 max-h-80 overflow-y-auto">
        <div class="px-4 py-2">
          <div class="flex items-center justify-between mb-2">
            <span class="text-[10px] font-bold text-slate-400">告警规则</span>
            <button
              @click="toggleCreateForm"
              class="text-[10px] px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30"
            >
              {{ showCreateForm ? '取消' : '+ 添加规则' }}
            </button>
          </div>

          <!-- 创建表单 -->
          <div v-if="showCreateForm" class="mb-3 p-3 rounded-lg bg-slate-800/80 border border-slate-600/50">
            <div class="mb-2">
              <label class="text-[10px] text-slate-400 mb-1 block">股票</label>
              <select
                v-model="formStock"
                class="w-full bg-slate-700 text-white text-xs rounded px-2 py-1.5 border border-slate-600 focus:border-cyan-500 outline-none"
              >
                <option value="" disabled>选择股票</option>
                <option v-for="s in stocks" :key="s.symbol" :value="s.symbol">
                  {{ s.name }} ({{ s.symbol }})
                </option>
              </select>
            </div>
            <div class="mb-2">
              <label class="text-[10px] text-slate-400 mb-1 block">规则类型</label>
              <select
                v-model="formRuleType"
                @change="onRuleTypeChange"
                class="w-full bg-slate-700 text-white text-xs rounded px-2 py-1.5 border border-slate-600 focus:border-cyan-500 outline-none"
              >
                <option v-for="opt in ruleTypeOptions" :key="opt.key" :value="opt.key">
                  {{ opt.label }}
                </option>
              </select>
            </div>
            <div class="mb-2">
              <label class="text-[10px] text-slate-400 mb-1 block">
                阈值
                <span v-if="currentRuleDesc" class="text-slate-500">（{{ currentRuleDesc }}）</span>
              </label>
              <div class="flex items-center gap-2">
                <input
                  v-model.number="formThreshold"
                  type="number"
                  step="any"
                  class="flex-1 bg-slate-700 text-white text-xs rounded px-2 py-1.5 border border-slate-600 focus:border-cyan-500 outline-none"
                />
                <span v-if="RULE_TYPE_CONFIG[formRuleType]?.unit" class="text-[10px] text-slate-500">
                  {{ RULE_TYPE_CONFIG[formRuleType].unit }}
                </span>
              </div>
            </div>
            <button
              @click="handleCreateRule"
              :disabled="creating || !formStock"
              class="w-full text-xs py-1.5 rounded bg-cyan-600 text-white hover:bg-cyan-500 disabled:bg-slate-600 disabled:text-slate-400 transition-colors"
            >
              {{ creating ? '创建中...' : '确认创建' }}
            </button>
          </div>

          <!-- 规则列表 -->
          <div
            v-for="rule in rules"
            :key="rule.id"
            class="flex items-center justify-between py-2 border-b border-slate-700/50"
          >
            <div>
              <div class="text-xs text-white">{{ rule.stock_name }}</div>
              <div class="text-[10px] text-slate-400">
                {{ rule.rule_type_display }} · 阈值 {{ rule.threshold }}
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="handleToggleRule(rule.id)"
                class="text-[10px] px-2 py-0.5 rounded"
                :class="rule.is_active ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-700 text-slate-400'"
              >
                {{ rule.is_active ? '启用' : '禁用' }}
              </button>
              <button
                @click="handleDeleteRule(rule.id)"
                class="text-[10px] text-rose-400 hover:text-rose-300"
              >
                删除
              </button>
            </div>
          </div>
          <div v-if="rules.length === 0 && !showCreateForm" class="text-[10px] text-slate-500 py-2">
            暂无规则，点击上方"+ 添加规则"创建
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { alertApi, stockApi } from '@/api'

const isOpen = ref(false)
const showRules = ref(false)
const isChecking = ref(false)
const unreadCount = ref(0)
const logs = ref<any[]>([])
const rules = ref<any[]>([])
const stocks = ref<any[]>([])
const showCreateForm = ref(false)
const creating = ref(false)
const formStock = ref('')
const formRuleType = ref('pe_low')
const formThreshold = ref(10)

let pollTimer: any = null

const RULE_TYPE_CONFIG: Record<string, { label: string; desc: string; default: number; unit: string }> = {
  sentiment_low:    { label: '情感分数低于阈值', desc: '情感分数范围 0~1', default: 0.3, unit: '' },
  sentiment_high:   { label: '情感分数高于阈值', desc: '情感分数范围 0~1', default: 0.8, unit: '' },
  pe_low:           { label: 'PE 低于阈值', desc: '低于此值时提醒买入机会', default: 10, unit: '倍' },
  pe_high:          { label: 'PE 高于阈值', desc: '高于此值时提醒估值偏高', default: 30, unit: '倍' },
  pb_low:           { label: 'PB 低于阈值', desc: '低于此值时提醒', default: 1.0, unit: '倍' },
  pb_high:          { label: 'PB 高于阈值', desc: '高于此值时提醒', default: 3.0, unit: '倍' },
  dividend_yield_high: { label: '股息率高于阈值', desc: '高于此值时提醒', default: 5, unit: '%' },
  hot_spike:        { label: '热度飙升', desc: '热度超过均值的倍数', default: 2, unit: '倍' },
  margin_decline:   { label: '毛利率连续下滑', desc: '连续下滑的季度数', default: 3, unit: '期' },
  receivable_surge: { label: '应收增速超营收', desc: '应收+预付占收入比例阈值', default: 30, unit: '%' },
  cfo_negative:     { label: '经营现金流转负', desc: '触发阈值（填0即可）', default: 0, unit: '' },
  price_target:     { label: '价格到达目标价', desc: '低于目标价时提醒买入机会', default: 0, unit: '元' },
  pe_percentile:    { label: 'PE 进入低分位', desc: 'PE 分位低于此值时提醒（历史低位）', default: 10, unit: '%' },
  volume_anomaly:   { label: '成交量异常放大', desc: '当日成交量超过 MA20 均量的倍数', default: 3, unit: '倍' },
}

const ruleTypeOptions = computed(() =>
  Object.entries(RULE_TYPE_CONFIG).map(([key, cfg]) => ({ key, ...cfg }))
)

const currentRuleDesc = computed(() => RULE_TYPE_CONFIG[formRuleType.value]?.desc || '')

// 加载数据
async function loadData() {
  try {
    const [countRes, logsRes, rulesRes] = await Promise.all([
      alertApi.getUnreadCount(),
      alertApi.getLogs(20),
      alertApi.getRules(),
    ])
    unreadCount.value = countRes.data.count
    logs.value = logsRes.data
    rules.value = rulesRes.data
  } catch (e) {
    console.error('加载告警数据失败', e)
  }
}

// 标记单条已读
async function handleMarkRead(alertId: number) {
  try {
    await alertApi.markRead(alertId)
    const log = logs.value.find(l => l.id === alertId)
    if (log) log.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch (e) {
    console.error('标记已读失败', e)
  }
}

// 标记全部已读
async function handleMarkAllRead() {
  try {
    await alertApi.markAllRead()
    logs.value.forEach(l => l.is_read = true)
    unreadCount.value = 0
  } catch (e) {
    console.error('标记全部已读失败', e)
  }
}

// 手动检查告警
async function handleCheckAlerts() {
  isChecking.value = true
  try {
    await alertApi.checkAlerts()
    await loadData()
  } catch (e) {
    console.error('检查告警失败', e)
  } finally {
    isChecking.value = false
  }
}

// 切换规则状态
async function handleToggleRule(ruleId: number) {
  try {
    await alertApi.toggleRule(ruleId)
    const rule = rules.value.find(r => r.id === ruleId)
    if (rule) rule.is_active = !rule.is_active
  } catch (e) {
    console.error('切换规则状态失败', e)
  }
}

// 删除规则
async function handleDeleteRule(ruleId: number) {
  try {
    await alertApi.deleteRule(ruleId)
    rules.value = rules.value.filter(r => r.id !== ruleId)
  } catch (e) {
    console.error('删除规则失败', e)
  }
}

// 切换创建表单
function toggleCreateForm() {
  showCreateForm.value = !showCreateForm.value
  if (showCreateForm.value && stocks.value.length === 0) {
    loadStocks()
  }
}

// 加载股票列表
async function loadStocks() {
  try {
    const { data } = await stockApi.getStocks()
    stocks.value = data
    if (data.length > 0 && !formStock.value) {
      formStock.value = data[0].symbol
    }
  } catch (e) {
    console.error('加载股票列表失败', e)
  }
}

// 规则类型切换时重置默认阈值
function onRuleTypeChange() {
  const cfg = RULE_TYPE_CONFIG[formRuleType.value]
  if (cfg) formThreshold.value = cfg.default
}

// 创建规则
async function handleCreateRule() {
  if (!formStock.value) return
  creating.value = true
  try {
    await alertApi.createRule({
      stock_symbol: formStock.value,
      rule_type: formRuleType.value,
      threshold: formThreshold.value,
    })
    showCreateForm.value = false
    await loadData()
  } catch (e) {
    console.error('创建规则失败', e)
  } finally {
    creating.value = false
  }
}

// 格式化时间
function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

onMounted(() => {
  loadData()
  // 每 5 分钟轮询一次未读数量
  pollTimer = setInterval(async () => {
    try {
      const { data } = await alertApi.getUnreadCount()
      unreadCount.value = data.count
    } catch (e) {
      // 静默失败
    }
  }, 300000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>
