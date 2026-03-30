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
            
            # 字段映射 (常见列名: '公告日期', '派现') 
            # 这里的派现通常是 "每10股派X元"
            df = df.rename(columns={
                df.columns[0]: 'ann_date',
                df.columns[3]: 'cash_div_10'
            })
            
            df['ann_date'] = pd.to_datetime(df['ann_date'])
            df['cash_div'] = pd.to_numeric(df['cash_div_10'], errors='coerce').fillna(0) / 10.0
            
            # 过滤无效数据并按日期排序
            df = df[df['cash_div'] > 0].sort_values('ann_date')
            
            # 清洗重复的分红条目 (比如 EastMoney 经常把“预案”和“实施”算作两条不同记录)
            # 逻辑：如果相邻两此分红金额完全相等，且日期相差不足 90 天，则剔除较早的一条 (通常是预案)
            cleaned_indices = []
            prev_row = None
            for idx, row in df.iterrows():
                if prev_row is not None:
                    # 判断是否为同一个分红事件的重复公告
                    same_amount = abs(row['cash_div'] - prev_row['cash_div']) < 1e-5
                    close_date = (row['ann_date'] - prev_row['ann_date']).days <= 90
                    if same_amount and close_date:
                        # 发现重复，移除前面的预案，将其替换为新的实施记录
                        cleaned_indices.pop()
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
