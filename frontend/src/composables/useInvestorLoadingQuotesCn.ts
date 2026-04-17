import { computed, onUnmounted, ref, watch, type Ref } from 'vue'

interface InvestorQuote {
  text: string
  author: string
}

const INVESTOR_QUOTES: InvestorQuote[] = [
  { text: '价格是你付出的，价值是你得到的。', author: '巴菲特' },
  { text: '市场短期像投票机，长期像称重机。', author: '巴菲特' },
  { text: '别人恐惧时我贪婪，别人贪婪时我谨慎。', author: '巴菲特' },
  { text: '反过来想，总是反过来想。', author: '查理·芒格' },
  { text: '好生意加合理价格，胜过便宜的普通生意。', author: '查理·芒格' },
]

export function useInvestorLoadingQuotes(active: Ref<boolean>, intervalMs = 3600) {
  const quoteIndex = ref(Math.floor(Math.random() * INVESTOR_QUOTES.length))
  let timerId: number | null = null

  const stop = () => {
    if (timerId !== null) {
      window.clearInterval(timerId)
      timerId = null
    }
  }

  const start = () => {
    if (timerId !== null || INVESTOR_QUOTES.length < 2) return
    timerId = window.setInterval(() => {
      quoteIndex.value = (quoteIndex.value + 1) % INVESTOR_QUOTES.length
    }, intervalMs)
  }

  watch(active, (enabled) => {
    if (enabled) {
      start()
      return
    }
    stop()
  }, { immediate: true })

  onUnmounted(stop)

  return {
    loadingQuote: computed(() => INVESTOR_QUOTES[quoteIndex.value]),
  }
}
