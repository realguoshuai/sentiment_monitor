"""盯盘日记、分红日历、估值温度计"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime as _dt

import time
from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import Stock
from ..price_service import PriceService
from ..fundamental_service import FundamentalService

logger = logging.getLogger(__name__)
_diary_timer = logging.getLogger('api.diary_timing')


@api_view(['GET'])
def get_market_diary(request):
    """盯盘日记接口：包含估值、股息率、成交量走势以及下次分红倒计时

    缓存策略：
      - 历史 K 线（不含今天）：长缓存 24h，不会变
      - 当日数据 + 实时指标：短缓存（盘中 30s / 收盘后 1h）
      - 分红倒计时：中缓存 6h
    """
    symbol = request.GET.get('symbol', '').strip().upper()
    if not symbol:
        return Response({'error': 'No symbol provided'}, status=400)

    fixed_symbol = PriceService._fix_symbol(symbol)
    _t0 = time.time()

    force = request.GET.get('force', '').lower() in ('true', '1', 'yes')
    force_deep = request.GET.get('deep', '').lower() in ('true', '1', 'yes')

    if force_deep:
        try:
            from ..cache_manager import CacheManager
            CacheManager.invalidate_by_symbol(fixed_symbol, domains=['fundamental', 'price'])
        except Exception:
            pass

    # ---- 统一缓存键 ----
    history_cache_key = f"market_diary_hist_v1_{fixed_symbol}"
    today_cache_key = f"market_diary_today_v1_{fixed_symbol}"
    div_cache_key = f"market_diary_div_v1_{fixed_symbol}"

    # ---- 先检查所有缓存（无网络开销） ----
    if force:
        for k in (history_cache_key, today_cache_key, div_cache_key):
            try:
                cache.delete(k)
            except Exception:
                pass
        history = today_data = next_dividend = None
    else:
        history = cache.get(history_cache_key)
        today_data = cache.get(today_cache_key)
        next_dividend = cache.get(div_cache_key)

    now = _dt.now()
    is_trading_hour = (now.weekday() < 5 and (
        _dt.strptime('09:30', '%H:%M').time() <= now.time() <= _dt.strptime('15:00', '%H:%M').time()
    ))
    today_cache_ttl = 30 if is_trading_hour else 3600

    # ---- 并行获取缺失数据（Wall-time ≈ max(slowest call)） ----
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}

        if history is None:
            futures['hist'] = pool.submit(
                PriceService.get_historical_data,
                [fixed_symbol], 250, 'day', False, force or force_deep,
            )

        if today_data is None:
            futures['today_kline'] = pool.submit(
                PriceService.get_historical_data,
                [fixed_symbol], 1, 'day', False, False,
            )
            futures['today_rt'] = pool.submit(
                PriceService.get_realtime_price,
                [fixed_symbol], False,
            )

        if next_dividend is None:
            futures['div'] = pool.submit(
                FundamentalService.get_next_dividend,
                fixed_symbol,
            )

        # 收集结果
        if 'hist' in futures:
            try:
                hist_res = futures['hist'].result()
                history = hist_res.get(fixed_symbol, [])
                if history:
                    from datetime import date as _date
                    today_str = _date.today().isoformat()
                    if history[-1].get('date', '')[:10] == today_str:
                        history = history[:-1]
                    cache.set(history_cache_key, history, 24 * 3600)
            except Exception as e:
                logger.error(f"Failed to fetch historical data for {fixed_symbol}: {e}")
                history = []
        if not history:
            history = []

        if 'today_kline' in futures:
            try:
                today_kline = futures['today_kline'].result().get(fixed_symbol, [])
                today_rt = futures['today_rt'].result().get(fixed_symbol, {})
                today_data = dict(today_kline[-1]) if today_kline else {}
                today_data['pe'] = today_rt.get('pe', 0.0)
                today_data['pb'] = today_rt.get('pb', 0.0)
                today_data['dividend_yield'] = today_rt.get('dividend_yield', 0.0)
                cache.set(today_cache_key, today_data, today_cache_ttl)
            except Exception as e:
                logger.warning(f"Failed to fetch today data for {fixed_symbol}: {e}")
                today_data = {}
        if not today_data:
            today_data = {}

        if 'div' in futures:
            try:
                next_dividend = futures['div'].result()
                cache.set(div_cache_key, next_dividend, 6 * 3600)
            except Exception as e:
                logger.warning(f"Failed to fetch next dividend for {fixed_symbol}: {e}")
                next_dividend = {}
        if not next_dividend:
            next_dividend = {}

    # ---- 4. 拼接历史 + 今天，计算 MA20 ----
    full_history = history + [today_data] if today_data and today_data.get('volume') else history

    volumes = [h.get('volume', 0.0) for h in full_history]
    history_with_ma = []
    for i, item in enumerate(full_history):
        start_idx = max(0, i - 19)
        sub_v = volumes[start_idx:i + 1]
        ma_val = sum(sub_v) / len(sub_v) if sub_v else 0.0
        entry = dict(item)
        entry['ma20_volume'] = round(ma_val, 2)
        history_with_ma.append(entry)

    latest_volume = full_history[-1].get('volume', 0.0) if full_history else 0.0
    latest_ma20 = history_with_ma[-1].get('ma20_volume', 0.0) if history_with_ma else 0.0
    volume_ratio = latest_volume / latest_ma20 if latest_ma20 > 0 else 1.0

    if volume_ratio <= 0.5:
        volume_status, volume_desc = '极度缩量', '筹码沉淀极高，属于典型的无流动性杀跌阶段，恐慌杀伤力极小，已进入高安全边际配置区。'
    elif volume_ratio <= 0.8:
        volume_status, volume_desc = '明显缩量', '成交清淡，市场观望情绪浓厚。'
    elif volume_ratio >= 1.5:
        volume_status, volume_desc = '显著放量', '交投活跃，可能存在多空分歧或突破动作。'
    else:
        volume_status, volume_desc = '成交平稳', '交投平稳，符合均值状态。'

    # ---- 5. 组装返回 ----
    result = {
        'symbol': fixed_symbol,
        'latest': {
            'price': today_data.get('price') or (full_history[-1].get('price', 0.0) if full_history else 0.0),
            'pe': today_data.get('pe', 0.0),
            'pb': today_data.get('pb', 0.0),
            'dividend_yield': today_data.get('dividend_yield', 0.0),
            'volume_ratio': round(volume_ratio, 4),
            'volume_status': volume_status,
            'volume_desc': volume_desc,
        },
        'next_dividend': next_dividend,
        'history': history_with_ma,
    }
    elapsed = time.time() - _t0
    if elapsed > 1:
        _diary_timer.warning("Slow market diary for %s: %.1fs", fixed_symbol, elapsed)
    return Response(result)


DIVIDEND_CALENDAR_KEY = "dividend_calendar_v1"
DIVIDEND_CALENDAR_STALE_KEY = "dividend_calendar_v1_stale"
DIVIDEND_CALENDAR_LOCK_KEY = "dividend_calendar_v1_building"


def _build_dividend_calendar():
    """构建分红日历数据（带锁防穿透，TTL 6h + stale 24h）"""
    # 1. 主缓存命中
    try:
        cached_data = cache.get(DIVIDEND_CALENDAR_KEY)
    except Exception:
        cache.delete(DIVIDEND_CALENDAR_KEY)
        cached_data = None
    if cached_data is not None:
        return cached_data

    # 2. 尝试 stale 兜底（如果主缓存过期但 stale 还在）
    try:
        stale = cache.get(DIVIDEND_CALENDAR_STALE_KEY)
    except Exception:
        stale = None

    # 3. 分布式锁：防止并发穿透
    if cache.add(DIVIDEND_CALENDAR_LOCK_KEY, True, 120):
        try:
            # 双检：等锁期间可能已有别的进程写好了
            try:
                cached_data = cache.get(DIVIDEND_CALENDAR_KEY)
            except Exception:
                cached_data = None
            if cached_data is not None:
                return cached_data

            stocks = list(Stock.objects.all().values('symbol', 'name'))
            if not stocks:
                cache.set(DIVIDEND_CALENDAR_KEY, [], 6 * 3600)
                cache.set(DIVIDEND_CALENDAR_STALE_KEY, [], 24 * 3600)
                return []

            results = []
            with ThreadPoolExecutor(max_workers=min(len(stocks), 8)) as executor:
                future_map = {}
                for s in stocks:
                    future = executor.submit(FundamentalService.get_next_dividend, s['symbol'])
                    future_map[future] = s

                try:
                    for future in as_completed(future_map, timeout=60):
                        stock_info = future_map[future]
                        try:
                            div_info = future.result(timeout=15)
                            if div_info.get('status') != 'none':
                                results.append({
                                    'symbol': stock_info['symbol'],
                                    'name': stock_info['name'],
                                    'date': div_info.get('date'),
                                    'days_left': div_info.get('days_left'),
                                    'plan': div_info.get('plan'),
                                    'status': div_info.get('status'),
                                    'status_desc': div_info.get('status_desc'),
                                })
                        except Exception as e:
                            logger.warning(f"Failed to get dividend for {stock_info['symbol']}: {e}")
                except TimeoutError:
                    logger.warning(f"Dividend calendar: {len(future_map) - len(results)} futures unfinished, returning partial results")

            results.sort(key=lambda x: x.get('days_left') if x.get('days_left') is not None else 9999)
            try:
                cache.set(DIVIDEND_CALENDAR_KEY, results, 6 * 3600)
                cache.set(DIVIDEND_CALENDAR_STALE_KEY, results, 24 * 3600)
            except Exception as e:
                logger.warning(f"Failed to cache dividend calendar: {e}")
            return results
        finally:
            cache.delete(DIVIDEND_CALENDAR_LOCK_KEY)
    else:
        # 没拿到锁：有 stale 就用 stale，没有就等一会儿重试
        if stale is not None:
            return stale
        time.sleep(2)
        try:
            cached_data = cache.get(DIVIDEND_CALENDAR_KEY)
        except Exception:
            cached_data = None
        return cached_data if cached_data is not None else []


@api_view(['GET'])
def get_dividend_calendar(request):
    """分红日历接口：返回所有监控股票的下一次分红信息"""
    try:
        return Response(_build_dividend_calendar())
    except Exception as e:
        logger.error(f"Error generating dividend calendar: {e}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_valuation_thermometer(request):
    """估值温度计：自选股 PB 十年水位"""
    try:
        stocks = list(Stock.objects.order_by('symbol').values('symbol', 'name'))
        if not stocks:
            return Response({'stocks': []})

        results = []
        with ThreadPoolExecutor(max_workers=min(len(stocks), 6)) as executor:
            future_map = {}
            for s in stocks:
                future = executor.submit(FundamentalService.get_pb_water_level, s['symbol'])
                future_map[future] = s

            try:
                for future in as_completed(future_map, timeout=60):
                    stock_info = future_map[future]
                    try:
                        result = future.result(timeout=15)
                        if result:
                            result['name'] = stock_info['name']
                            results.append(result)
                    except Exception:
                        pass
            except TimeoutError:
                logger.warning(f"Valuation thermometer: {len(future_map) - len(results)} futures unfinished, returning partial results")

        results.sort(key=lambda x: x.get('percentile', 50))
        return Response({'stocks': results})
    except Exception as e:
        logger.error(f"Error generating valuation thermometer: {e}")
        return Response({'error': str(e)}, status=500)
