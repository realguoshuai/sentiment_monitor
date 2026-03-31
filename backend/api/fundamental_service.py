import akshare as ak
import pandas as pd
import re
import logging
import time
from datetime import datetime

from django.core.cache import cache

logger = logging.getLogger(__name__)

class FundamentalService:
    @classmethod
    def get_ttm_fundamentals(cls, symbol):
        """获取 TTM 净利润和净资产序列 (含 24h 缓存)"""
        cache_key = f"fundamentals_{symbol}"
        cached_df = cache.get(cache_key)
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
            
            # 2. 资产负债表 (净资产)
            df_balance = ak.stock_balance_sheet_by_report_em(symbol=symbol)
            if 'TOTAL_PARENT_EQUITY' in df_balance.columns:
                df_balance = df_balance[['REPORT_DATE', 'TOTAL_PARENT_EQUITY']]
                df_balance['REPORT_DATE'] = pd.to_datetime(df_balance['REPORT_DATE'])
                df_balance['TOTAL_PARENT_EQUITY'] = pd.to_numeric(df_balance['TOTAL_PARENT_EQUITY'], errors='coerce').fillna(0)
            else:
                df_balance = pd.DataFrame(columns=['REPORT_DATE', 'TOTAL_PARENT_EQUITY'])
            
            # 确保 NOTICE_DATE 不为空 (补全逻辑：如果无公告日，则假设报表期后 30 天公告)
            df_profit['NOTICE_DATE'] = df_profit['NOTICE_DATE'].fillna(df_profit['REPORT_DATE'] + pd.Timedelta(days=30))
            # 确保 NOTICE_DATE 是有效的日期序列并去重
            df_profit = df_profit.dropna(subset=['NOTICE_DATE'])
            
            # 合并
            df_fund = pd.merge(df_profit[['REPORT_DATE', 'ttm_profit', 'NOTICE_DATE']], 
                              df_balance, on='REPORT_DATE', how='left')
            df_fund['TOTAL_PARENT_EQUITY'] = df_fund['TOTAL_PARENT_EQUITY'].ffill().bfill().fillna(0)
            
            # 最终清洗：确保 NOTICE_DATE 严格递增用于 merge_asof
            df_fund = df_fund.dropna(subset=['NOTICE_DATE'])
            df_fund = df_fund.sort_values('NOTICE_DATE').drop_duplicates('NOTICE_DATE', keep='last')
            
            # 缓存 24 小时
            cache.set(cache_key, df_fund, 24 * 3600)
            return df_fund
        except Exception as e:
            logger.error(f"FundamentalService Error for {symbol}: {e}")
            return pd.DataFrame()

    @classmethod
    def get_historical_dividends(cls, symbol):
        """获取历史分红记录 (含 24h 缓存)"""
        symbol = cls._fix_symbol(symbol)
        cache_key = f"dividends_{symbol}"
        cached_df = cache.get(cache_key)
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
            
            cache.set(cache_key, df, 24 * 3600)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch dividends for {symbol}: {e}")
            return pd.DataFrame()

    @classmethod
    def calculate_dividend_at_date(cls, df_divs, date_dt):
        """智能计算截至特定日期的滚动派息总额（根据派息频率自动适配）"""
        if df_divs.empty:
            return 0.0
            
        past_divs = df_divs[df_divs['ann_date'] <= date_dt]
        n = len(past_divs)
        
        if n == 0:
            return 0.0
        elif n == 1:
            return float(past_divs.iloc[-1]['cash_div'])
            
        # 寻找最近的派息规律，推断年度分红频率 (1次/2次/3次)
        latest_date = past_divs.iloc[-1]['ann_date']
        best_freq = 1
        min_diff = 999
        
        for i in range(1, min(n, 5)):
            prev_date = past_divs.iloc[-1 - i]['ann_date']
            diff_from_year = abs((latest_date - prev_date).days - 365)
            if diff_from_year < min_diff:
                min_diff = diff_from_year
                best_freq = i
                
        # 如果规律偏差太大(超过150天)，回退到严谨的 365天 窗口加总
        if min_diff > 150:
            one_year_ago = date_dt - pd.Timedelta(days=365)
            return float(past_divs[past_divs['ann_date'] > one_year_ago]['cash_div'].sum())
            
        # 取判定频率内的最近 N 次分红总额
        return float(past_divs.tail(best_freq)['cash_div'].sum())

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
        cache_key = f"f_score_{symbol}"
        cached = cache.get(cache_key)
        if cached: return cached
        
        try:
            # 简化版 F-Score 逻辑 (基于盈利能力、杠杆/流动性、营运效率)
            # 抓取财报指标 (EM 接口)
            # 备注：由于 AkShare 接口兼容性，如果 Indicator 接口失效，我们通过基础表计算
            df_fund = cls.get_ttm_fundamentals(symbol)
            if df_fund.empty: return {"score": 0, "details": []}
            
            latest = df_fund.iloc[-1]
            prev_year = df_fund[df_fund['REPORT_DATE'] <= (latest['REPORT_DATE'] - pd.Timedelta(days=330))].tail(1)
            
            score = 0
            details = []
            
            # 1. 盈利能力 (Profitability)
            # ROA > 0 (资产回报率)
            roa = (latest['ttm_profit'] / latest['TOTAL_PARENT_EQUITY']) if latest['TOTAL_PARENT_EQUITY'] > 0 else 0
            if roa > 0:
                score += 1
                details.append({"name": "ROA > 0", "passed": True, "val": f"{round(roa*100, 2)}%"})
            else:
                details.append({"name": "ROA > 0", "passed": False, "val": f"{round(roa*100, 2)}%"})
                
            # CFO (此处简化：如果没有现金流表，则判断利润是否为正)
            if latest['ttm_profit'] > 0:
                score += 1
                details.append({"name": "Net Income > 0", "passed": True, "val": "Positive"})
            else:
                details.append({"name": "Net Income > 0", "passed": False, "val": "Negative"})

            # ROA 提升 (对比去年)
            if not prev_year.empty:
                prev_roa = (prev_year.iloc[0]['ttm_profit'] / prev_year.iloc[0]['TOTAL_PARENT_EQUITY']) if prev_year.iloc[0]['TOTAL_PARENT_EQUITY'] > 0 else 0
                if roa > prev_roa:
                    score += 1
                    details.append({"name": "ROA Improving", "passed": True, "val": f"{round(roa*100, 2)}% vs {round(prev_roa*100, 2)}%"})
                else:
                    details.append({"name": "ROA Improving", "passed": False, "val": f"{round(roa*100, 2)}% vs {round(prev_roa*100, 2)}%"})
            
            # 2. 杠杆与流动性 (Leverage & Liquidity)
            # 此处可以扩展资产负债表字段，目前先返回核心
            
            # 计算综合评分 (映射到 0-10)
            final_score = round((score / 3.0) * 10, 1) if score > 0 else 0
            result = {"score": final_score, "details": details}
            cache.set(cache_key, result, 3600 * 12)
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
