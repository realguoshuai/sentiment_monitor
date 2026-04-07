import akshare as ak
import pandas as pd
import re
import logging
import time
from datetime import datetime

from django.core.cache import cache

logger = logging.getLogger(__name__)

class FundamentalService:
    @staticmethod
    def _cache_get(key):
        try:
            val = cache.get(key)
            if isinstance(val, list):
                # 如果是列表，说明是 Safe-Cache 存入的字典序列，恢复为 DataFrame
                df = pd.DataFrame(val)
                # 恢复关键日期列
                for col in ['REPORT_DATE', 'NOTICE_DATE', 'ann_date', 'date_dt']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])
                return df
            return val
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None

    @staticmethod
    def _cache_set(key, value, ttl):
        try:
            if isinstance(value, pd.DataFrame):
                # Safe-Cache: 将 DataFrame 转换为字典列表存储，彻底免疫 pickle/numpy 版本问题
                # 先转换日期为 iso 字符串
                temp_df = value.copy()
                for col in temp_df.select_dtypes(include=['datetime', 'datetimetz']).columns:
                    temp_df[col] = temp_df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                value = temp_df.to_dict(orient='records')
            cache.set(key, value, ttl)
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")

    @classmethod
    def get_ttm_fundamentals(cls, symbol):
        """获取 TTM 净利润和净资产序列 (含 24h 缓存)"""
        cache_key = f"fundamentals_v5_{symbol}"
        cached_df = cls._cache_get(cache_key)
        if cached_df is not None:
            return cached_df
        
        try:
            # 1. 利润表 (YTD -> Single Quarter -> TTM)
            df_profit = ak.stock_profit_sheet_by_quarterly_em(symbol=symbol)
            df_profit = df_profit[['REPORT_DATE', 'PARENT_NETPROFIT', 'NOTICE_DATE']]
            df_profit['REPORT_DATE'] = pd.to_datetime(df_profit['REPORT_DATE'])
            df_profit['NOTICE_DATE'] = pd.to_datetime(df_profit['NOTICE_DATE'])
            df_profit = df_profit.sort_values('REPORT_DATE')
            
            # 确保数值型
            df_profit['PARENT_NETPROFIT'] = pd.to_numeric(df_profit['PARENT_NETPROFIT'], errors='coerce').fillna(0)
            
            # 不需要 YTD 转换：AkShare EM 季报接口返回的已经是单季利润
            df_profit['q_profit'] = df_profit['PARENT_NETPROFIT']
            # 计算 TTM (滚动4季)
            df_profit['ttm_profit'] = df_profit['q_profit'].rolling(window=4).sum().bfill()
            
            # 2. 资产负债表 (净资产, 总资产)
            df_balance = ak.stock_balance_sheet_by_report_em(symbol=symbol)
            if 'TOTAL_PARENT_EQUITY' in df_balance.columns:
                cols = ['REPORT_DATE', 'TOTAL_PARENT_EQUITY']
                if 'TOTAL_ASSETS' in df_balance.columns:
                    cols.append('TOTAL_ASSETS')
                df_balance = df_balance[cols]
                df_balance['REPORT_DATE'] = pd.to_datetime(df_balance['REPORT_DATE'])
                df_balance['TOTAL_PARENT_EQUITY'] = pd.to_numeric(df_balance['TOTAL_PARENT_EQUITY'], errors='coerce').fillna(0)
                if 'TOTAL_ASSETS' in df_balance.columns:
                    df_balance['TOTAL_ASSETS'] = pd.to_numeric(df_balance['TOTAL_ASSETS'], errors='coerce').fillna(0)
            else:
                df_balance = pd.DataFrame(columns=['REPORT_DATE', 'TOTAL_PARENT_EQUITY', 'TOTAL_ASSETS'])
            
            # 确保 NOTICE_DATE 不为空 (补全逻辑：根据 A 股披露规则保守估计公告日)
            def get_fallback_notice_date(row):
                if pd.notnull(row['NOTICE_DATE']): return row['NOTICE_DATE']
                r_date = row['REPORT_DATE']
                # Q1: 4/30, Q2: 8/30, Q3: 10/31, Q4: 4/30 (next year)
                if r_date.month == 3: return datetime(r_date.year, 5, 1)
                if r_date.month == 6: return datetime(r_date.year, 9, 1)
                if r_date.month == 9: return datetime(r_date.year, 11, 1)
                if r_date.month == 12: return datetime(r_date.year + 1, 5, 1)
                return r_date + pd.Timedelta(days=90)
                
            df_profit['NOTICE_DATE'] = df_profit.apply(get_fallback_notice_date, axis=1)
            # 确保 NOTICE_DATE 是有效的日期序列并去重
            df_profit = df_profit.dropna(subset=['NOTICE_DATE'])
            
            # 合并
            df_fund = pd.merge(df_profit[['REPORT_DATE', 'ttm_profit', 'NOTICE_DATE']], 
                              df_balance, on='REPORT_DATE', how='left')
            
            # 强化填充：对净资产进行前向填充
            df_fund = df_fund.sort_values('REPORT_DATE')
            df_fund['TOTAL_PARENT_EQUITY'] = df_fund['TOTAL_PARENT_EQUITY'].replace(0, pd.NA).ffill().fillna(0)
            df_fund['ttm_profit'] = df_fund['ttm_profit'].replace(0, pd.NA).ffill().fillna(0)
            
            # 最终清洗：确保 NOTICE_DATE 严格递增且用于 merge_asof
            df_fund = df_fund.dropna(subset=['NOTICE_DATE'])
            df_fund = df_fund.sort_values('NOTICE_DATE').drop_duplicates('NOTICE_DATE', keep='last')
            
            # 缓存 24 小时
            cls._cache_set(cache_key, df_fund, 24 * 3600)
            
            # 持久化最新快照到数据库 (异步兜底)
            cls._save_snapshot(symbol, df_fund)
            
            return df_fund
        except Exception as e:
            logger.error(f"FundamentalService Error for {symbol}: {e}")
            # 降级：从本地数据库快照恢复
            fallback = cls._load_snapshot_as_df(symbol)
            if fallback is not None and not fallback.empty:
                logger.info(f"FundamentalService Fallback: loaded {len(fallback)} rows from DB for {symbol}")
                return fallback
            return pd.DataFrame()

    @classmethod
    def get_ttm_cashflow(cls, symbol):
        """获取 TTM 经营现金流 (含 24h 缓存)"""
        cache_key = f"cashflow_v5_{symbol}"
        cached_df = cls._cache_get(cache_key)
        if cached_df is not None:
            return cached_df
        
        try:
            df_cash = ak.stock_cash_flow_sheet_by_quarterly_em(symbol=symbol)
            df_cash = df_cash[['REPORT_DATE', 'NETCASH_OPERATE', 'NOTICE_DATE']]
            df_cash['REPORT_DATE'] = pd.to_datetime(df_cash['REPORT_DATE'])
            df_cash['NETCASH_OPERATE'] = pd.to_numeric(df_cash['NETCASH_OPERATE'], errors='coerce').fillna(0)
            # 计算 TTM
            df_cash = df_cash.sort_values('REPORT_DATE')
            df_cash['ttm_cfo'] = df_cash['NETCASH_OPERATE'].rolling(window=4).sum().bfill()
            
            cls._cache_set(cache_key, df_cash, 24 * 3600)
            return df_cash
        except Exception as e:
            logger.error(f"Cashflow fetch error for {symbol}: {e}")
            return pd.DataFrame()

    @classmethod
    def get_historical_dividends(cls, symbol):
        """获取历史分红记录 (含 24h 缓存)"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"dividends_v5_{symbol}"
        cached_df = cls._cache_get(cache_key)
        if cached_df is not None:
            return cached_df
            
        try:
            # 使用 ak.stock_history_dividend_detail
            # 注意：某些版本 akshare 接口名可能是 stock_history_dividend_detail
            # 如果报错，尝试 alternative
            df = ak.stock_history_dividend_detail(symbol=symbol[2:], indicator="分红")
            
            # 字段映射 (修正 AkShare 编码问题)
            # 通过索引获取：0: 公告日期, 3: 每10股派现
            df = df.rename(columns={
                df.columns[0]: 'ann_date',
                df.columns[3]: 'cash_div_10'
            })
            
            # 对列名可能出现的乱码进行二次清洗
            df['ann_date'] = pd.to_datetime(df['ann_date'], errors='coerce')
            df['cash_div'] = pd.to_numeric(df['cash_div_10'], errors='coerce').fillna(0) / 10.0
            
            # 过滤无效数据并按日期排序
            df = df.dropna(subset=['ann_date']).sort_values('ann_date')
            df = df[df['cash_div'] > 0]
            
            # 清洗重复的分红条目 (Logic: Same amount within 90 days = Duplicate)
            cleaned_indices = []
            prev_row = None
            for idx, row in df.iterrows():
                if prev_row is not None:
                    same_amount = abs(row['cash_div'] - prev_row['cash_div']) < 1e-5
                    close_date = (row['ann_date'] - prev_row['ann_date']).days <= 90
                    if same_amount and close_date:
                        # 发现重复，移除前面的记录
                        if cleaned_indices: cleaned_indices.pop()
                cleaned_indices.append(idx)
                prev_row = row
                
            df = df.loc[cleaned_indices]
            
            cls._cache_set(cache_key, df, 24 * 3600)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch dividends for {symbol}: {e}")
            return pd.DataFrame()

    @classmethod
    def calculate_dividend_at_date(cls, df_divs, date_dt):
        """
        智能推算截至特定日期的自然年派息总额 (Smart Natural Year)。
        逻辑：按自然年聚合分红，平滑派息周期的轻微漂移与一年多频次的派发。
        """
        if df_divs.empty:
            return 0.0
            
        date_dt = pd.to_datetime(date_dt)
        
        # 寻找该日期之前的所有分红
        past_divs = df_divs[df_divs['ann_date'] <= date_dt].copy()
        if past_divs.empty:
            return 0.0
            
        # 按自然年份聚合分红总额
        past_divs['year'] = past_divs['ann_date'].dt.year
        yearly_sum = past_divs.groupby('year')['cash_div'].sum().to_dict()
        
        current_year = date_dt.year
        last_year = current_year - 1
        
        current_sum = yearly_sum.get(current_year, 0.0)
        last_sum = yearly_sum.get(last_year, 0.0)
        
        # 自然年平滑策略 (应对 A 股财报季的规律)
        # 1. 如果当前的派息总额已经达到去年的 80%（说明大头已经派发），直接使用当年的分红总额
        if current_sum >= last_sum * 0.8:
            return float(current_sum)
            
        # 2. 如果仍在 9 月份之前（半年报与中期年报派发旺季未结束），大概率今年还没发完，沿用去年全年度的指引
        if date_dt.month < 9:
            return float(last_sum)
            
        # 3. 到了年底（>= 9月），当年发多少就是多少。如果完全停发，检查最近分红决定是否兜底 0
        last_div_date = past_divs.iloc[-1]['ann_date']
        return float(current_sum) if current_sum > 0 else (float(last_sum) if (date_dt - last_div_date).days <= 450 else 0.0)

    @classmethod
    def align_to_prices(cls, df_fund, df_prices, symbol):
        """将基本面数据对齐到价格序列 (使用 Notice Date 避免未来函数)"""
        if df_prices.empty:
            return df_prices
            
        # 确保日期格式
        df_prices['date_dt'] = pd.to_datetime(df_prices['date'])
        
        if df_fund.empty:
            logger.warning(f"No fundamental data found for {symbol}, using price defaults.")
            df_prices['ttm_profit'] = 0
            df_prices['TOTAL_PARENT_EQUITY'] = 0
            return df_prices
            
        # 对齐逻辑：对每个价格点，找“公告日 <= 当前日”的最晩一份财报
        # 使用 merge_asof，必须删除 Notice Date 为空的数据且排序
        df_fund = df_fund.dropna(subset=['NOTICE_DATE']).sort_values('NOTICE_DATE')
        df_prices = df_prices.sort_values('date_dt')
        
        df_merged = pd.merge_asof(
            df_prices, 
            df_fund, 
            left_on='date_dt', 
            right_on='NOTICE_DATE',
            direction='backward'
        )
        
        # 填充缺失的基本面数据（公告前的部分）
        df_merged['ttm_profit'] = df_merged['ttm_profit'].fillna(0)
        df_merged['TOTAL_PARENT_EQUITY'] = df_merged['TOTAL_PARENT_EQUITY'].fillna(0)
        
        return df_merged

    @classmethod
    def calculate_percentiles(cls, history, column='pe', period_years=10):
        """计算历史分位数值 (10/50/90)"""
        if not history:
            return {'p10': 0, 'p50': 0, 'p90': 0}
            
        df = pd.DataFrame(history)
        if column not in df.columns:
            return {'p10': 0, 'p50': 0, 'p90': 0}
            
        # 转换日期并过滤周期
        df['date_dt'] = pd.to_datetime(df['date'])
        start_date = datetime.now() - pd.Timedelta(days=period_years * 365)
        df = df[df['date_dt'] >= start_date]
        
        # 过滤无效值 (<=0)
        vals = df[df[column] > 0][column]
        if vals.empty:
            return {'p10': 0, 'p50': 0, 'p90': 0}
            
        return {
            'p10': round(vals.quantile(0.1), 2),
            'p50': round(vals.quantile(0.5), 2),
            'p90': round(vals.quantile(0.9), 2),
            'current': round(vals.iloc[-1] if not vals.empty else 0, 2)
        }

    @classmethod
    def get_f_score(cls, symbol):
        """计算 Piotroski F-Score (安全性评分)"""
        cache_key = f"f_score_v5_{symbol}"
        cached = cls._cache_get(cache_key)
        if cached: return cached
        
        try:
            # 强化版 F-Score 逻辑 (6 项指标)
            df_fund = cls.get_ttm_fundamentals(symbol)
            df_cash = cls.get_ttm_cashflow(symbol)
            
            if df_fund.empty: return {"score": 0, "details": []}
            
            latest = df_fund.iloc[-1]
            # 寻找约一年前的财报
            prev_year = df_fund[df_fund['REPORT_DATE'] <= (latest['REPORT_DATE'] - pd.Timedelta(days=330))].tail(1)
            
            # CFO 数据
            cfo_val = 0
            cfo_available = False
            if not df_cash.empty:
                latest_cash = df_cash[df_cash['REPORT_DATE'] <= latest['REPORT_DATE']].tail(1)
                if not latest_cash.empty:
                    cfo_val = latest_cash.iloc[0]['ttm_cfo']
                    cfo_available = True

            score = 0
            total_possible = 0
            details = []
            
            # 1. 盈利能力 (Profitability)
            # ROA > 0
            assets = latest.get('TOTAL_ASSETS', latest.get('TOTAL_PARENT_EQUITY', 0))
            roa = (latest['ttm_profit'] / assets) if pd.notnull(assets) and assets > 0 else 0
            passed = roa > 0
            total_possible += 1
            if passed: score += 1
            details.append({"name": "ROA > 0", "passed": passed, "val": f"{round(roa*100, 2)}%"})
            
            # Net Income > 0
            passed = latest['ttm_profit'] > 0
            total_possible += 1
            if passed: score += 1
            details.append({"name": "净利润 > 0", "passed": passed, "val": "Positive" if passed else "Negative"})

            if cfo_available:
                total_possible += 2

            # CFO > 0
            passed = cfo_val > 0
            if passed: score += 1
            details.append({"name": "经营性现金流 > 0", "passed": passed, "val": "Positive" if passed else "Negative"})

            # CFO > Net Income (盈余质量)
            passed = cfo_val > latest['ttm_profit']
            if passed: score += 1
            details.append({"name": "现金流 > 净利润", "passed": passed, "val": f"CFO/NI: {round(cfo_val/latest['ttm_profit'], 2) if latest['ttm_profit'] != 0 else 'N/A'}"})

            # 2. 增长与趋势
            # ROA 提升 (对比去年)
            if not prev_year.empty:
                prev_latest = prev_year.iloc[0]
                prev_assets = prev_latest.get('TOTAL_ASSETS', prev_latest['TOTAL_PARENT_EQUITY'])
                prev_roa = (prev_latest['ttm_profit'] / prev_assets) if prev_assets > 0 else 0
                passed = roa > prev_roa
                total_possible += 1
                if passed: score += 1
                details.append({"name": "ROA 同比提升", "passed": passed, "val": f"{round(roa*100, 2)}% vs {round(prev_roa*100, 2)}%"})
            else:
                details.append({"name": "ROA 同比提升", "passed": False, "val": "无历史数据"})

            # 计算总分 (满分按 5 项计算，如果有 CFO 数据则按 6 项)
            final_score = round((score / total_possible) * 10, 1) if total_possible else 0
            result = {"score": min(final_score, 10.0), "details": details}
            cls._cache_set(cache_key, result, 3600 * 12)
            return result
        except Exception as e:
            logger.error(f"F-Score calculation error for {symbol}: {e}")
            return {"score": 0, "details": []}

    @classmethod
    def get_forward_metrics(cls, symbol, history_df=None):
        """计算公允价值锚点与预测指标"""
        # 1. 获取过去 5 年的平均 ROE
        df_fund = cls.get_ttm_fundamentals(symbol)
        if df_fund.empty: return {"fair_price": 0, "expected_roe": 15}
        
        # 计算每期的 ROE (ttm_profit / equity)
        df_fund['roe'] = (df_fund['ttm_profit'] / df_fund['TOTAL_PARENT_EQUITY']) * 100
        avg_roe = df_fund.tail(20)['roe'].mean() # 过去 5 年 (20个季度)
        
        # 洋河保底逻辑同步到这里
        if '002304' in symbol and avg_roe < 20:
            avg_roe = 20
        
        # 2. 内在价值计算 (ROE / 目标回报率 * 每股净资产)
        # 获取最新每股净资产 (暂以 Equity / TotalShares 模拟)
        # 此处需要 PriceService 中的数据，建议在 API 层整合
        return {
            "expected_roe": round(avg_roe, 2),
            "avg_roe_5y": round(avg_roe, 2)
        }

    @staticmethod
    def _fix_symbol(symbol):
        """工具方法：补全市场前缀"""
        if re.match(r'^(SH|SZ|sh|sz)\d{6}$', symbol):
            return symbol.upper()
        if re.match(r'^\d{6}$', symbol):
            if symbol.startswith('6'):
                return f"SH{symbol}"
            return f"SZ{symbol}"
        return symbol

    @classmethod
    def _save_snapshot(cls, symbol, df_fund):
        """将最新财报数据持久化到数据库快照表"""
        try:
            from .models import FundamentalSnapshot
            if df_fund.empty:
                return
            latest = df_fund.iloc[-1]
            report_date = pd.to_datetime(latest['REPORT_DATE']).date()
            FundamentalSnapshot.objects.update_or_create(
                symbol=symbol.upper(),
                date=report_date,
                defaults={
                    'ttm_profit': float(latest.get('ttm_profit', 0) or 0),
                    'total_equity': float(latest.get('TOTAL_PARENT_EQUITY', 0) or 0),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to save snapshot for {symbol}: {e}")

    @classmethod
    def _load_snapshot_as_df(cls, symbol):
        """从数据库快照恢复为 DataFrame (降级兜底)"""
        try:
            from .models import FundamentalSnapshot
            snapshots = FundamentalSnapshot.objects.filter(
                symbol=symbol.upper()
            ).order_by('date')[:40]  # 最近 40 条 ≈ 10 年季报
            
            if not snapshots.exists():
                return None
            
            rows = []
            for s in snapshots:
                rows.append({
                    'REPORT_DATE': pd.Timestamp(s.date),
                    'NOTICE_DATE': pd.Timestamp(s.date) + pd.Timedelta(days=60),
                    'ttm_profit': s.ttm_profit,
                    'TOTAL_PARENT_EQUITY': s.total_equity,
                })
            return pd.DataFrame(rows)
        except Exception as e:
            logger.warning(f"Failed to load snapshot for {symbol}: {e}")
            return None

