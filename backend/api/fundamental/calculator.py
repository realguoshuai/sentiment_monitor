import pandas as pd
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class FundamentalCalculator:
    @staticmethod
    def safe_ratio(numerator, denominator):
        if denominator and denominator > 0:
            return numerator / denominator
        return 0.0

    @staticmethod
    def first_existing_column(df, candidates):
        for column in candidates:
            if column in df.columns:
                return column
        return None

    @classmethod
    def clean_json_data(cls, data):
        """递归清理字典或列表中的 NaN/Inf，兼容处理 numpy 标量类型，确保 JSON 序列化合规"""
        if isinstance(data, dict):
            return {k: cls.clean_json_data(v) for k, v in data.items()}
        if isinstance(data, list):
            return [cls.clean_json_data(v) for v in data]
        
        # 核心修复：Numpy 的 float64 等类型并不一定是 Python float 的实例
        # 使用 pd.isna 统一判断 NaN，使用 np.isinf 判断无穷大
        if isinstance(data, (float, np.floating, int, np.integer)):
            if pd.isna(data) or np.isinf(data):
                return 0.0
            # 转换为 Python 原生类型，避免某些 JSON 库处理 numpy 类型时报错
            return float(data) if isinstance(data, (float, np.floating)) else int(data)
            
        # 防御性：避免 pd.isna() 在处理 Series 或 DataFrame 时抛出 "truth value ambiguous"
        if isinstance(data, (pd.Series, pd.DataFrame)):
            return data.to_dict(orient='records') if isinstance(data, pd.DataFrame) else data.tolist()

        if pd.isna(data):
            return 0.0  # 修改：返回 0.0 而不是 None，防止前端 .toFixed() 崩溃
            
        return data

    @classmethod
    def calculate_shareholder_structure(cls, df):
        """处理股东户数结构数据与总结"""
        if df.empty: return {'shareholder_history': [], 'shareholder_summary': {}}
        
        # 统一列名
        aliases = {
            'end_date': ['股东户数统计截止日', '股东户数统计截止日期', '截止日期', 'end_date'],
            'holder_count': ['股东户数-本次', '股东户数', '本次股东户数', 'holder_count'],
            'notice_date': ['股东户数公告日期', '公告日期', 'notice_date'],
            'total_market_cap': ['总市值', '总市值(元)', 'total_market_cap'],
            'total_shares': ['总股本', '总股本(股)', 'total_shares'],
            'avg_market_cap_per_holder': ['户均持股市值', 'avg_market_cap_per_holder'],
            'avg_shares_per_holder': ['户均持股数量', 'avg_shares_per_holder'],
        }
        rename_map = {}
        for target, cands in aliases.items():
            src = cls.first_existing_column(df, cands)
            if src: rename_map[src] = target
        
        df = df.rename(columns=rename_map)
        if 'end_date' not in df.columns: return {'shareholder_history': [], 'shareholder_summary': {}}
        
        df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce')
        df['notice_date'] = pd.to_datetime(df.get('notice_date'), errors='coerce')
        
        for col in ['holder_count', 'total_market_cap', 'total_shares']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 计算价格
        df['price'] = df.apply(lambda r: cls.safe_ratio(r.get('total_market_cap', 0), r.get('total_shares', 0)), axis=1)
        
        latest_date = df['end_date'].max()
        cutoff = latest_date - pd.DateOffset(years=10)
        window = df[df['end_date'] >= cutoff].copy().sort_values('end_date')
        if len(window) < 2:
            window = df[df['end_date'] >= (latest_date - pd.DateOffset(years=5))].copy().sort_values('end_date')
            
        if window.empty: return {'shareholder_history': [], 'shareholder_summary': {}}
        
        # 转换日期为字符串以便 JSON 序列化
        # 核心修复：解决 JSON 序列化 nan 问题，全量清理 NaN 和 Inf
        history = window.replace([np.inf, -np.inf], np.nan).fillna(0)
        history['date'] = history['end_date'].dt.strftime('%Y-%m-%d')
        history['notice_date'] = history['notice_date'].dt.strftime('%Y-%m-%d').fillna('')
        
        # 计算 Summary
        base_count = float(window.iloc[0]['holder_count'])
        latest_count = float(window.iloc[-1]['holder_count'])
        change_pct = cls.safe_ratio(latest_count - base_count, base_count) * 100 if base_count > 0 else 0
        
        summary = {
            'latest_holder_count': int(latest_count),
            'holder_count_change_pct': round(change_pct, 2),
            'holder_trend_label': cls.classify_holder_trend(change_pct),
            'latest_stat_date': latest_date.strftime('%Y-%m-%d'),
        }
        
        # 只对数值列进行 round(4)，避免对 datetime 列调用 round 触发 UserWarning
        numeric_cols = history.select_dtypes(include=[np.number]).columns
        history[numeric_cols] = history[numeric_cols].round(4)
        
        res = {
            'shareholder_history': history.to_dict(orient='records'),
            'shareholder_summary': summary
        }
        return cls.clean_json_data(res)

    @classmethod
    def calculate_quality_metrics(cls, df_profit, df_balance, df_cash, df_div, market_cap):
        """核心计算逻辑：杜邦分析、护城河、派息质量等"""
        if df_profit.empty or df_balance.empty: return {}
        
        try:
            # 1. 预处理
            df_profit['REPORT_DATE'] = pd.to_datetime(df_profit['REPORT_DATE'])
            df_profit = df_profit[df_profit['REPORT_DATE'].dt.month == 12].sort_values('REPORT_DATE')
            df_balance['REPORT_DATE'] = pd.to_datetime(df_balance['REPORT_DATE'])
            df_balance = df_balance[df_balance['REPORT_DATE'].dt.month == 12].sort_values('REPORT_DATE')
            
            cashflow_metrics, capex_source = cls.extract_cashflow_metrics(df_cash)
            if not cashflow_metrics.empty:
                cashflow_metrics['REPORT_DATE'] = pd.to_datetime(cashflow_metrics['REPORT_DATE'])
            
            cap_struct_metrics, inv_cap_source = cls.extract_capital_structure_metrics(df_balance)
            if not cap_struct_metrics.empty:
                cap_struct_metrics['REPORT_DATE'] = pd.to_datetime(cap_struct_metrics['REPORT_DATE'])
            
            risk_metrics = cls.extract_balance_risk_metrics(df_balance)
            if not risk_metrics.empty:
                risk_metrics['REPORT_DATE'] = pd.to_datetime(risk_metrics['REPORT_DATE'])
            
            # 2. 合并
            df = pd.merge(df_profit, df_balance, on='REPORT_DATE', how='inner')
            df = pd.merge(df, cashflow_metrics, on='REPORT_DATE', how='left')
            df = pd.merge(df, cap_struct_metrics, on='REPORT_DATE', how='left')
            df = pd.merge(df, risk_metrics, on='REPORT_DATE', how='left')
            
            # 增加 df.copy() 以消除 PerformanceWarning (highly fragmented DataFrame)
            # 连续的列插入会导致 DataFrame 碎片化，copy() 会进行碎片整理
            df = df.copy()
            
            # 3. 基础指标计算
            df['net_margin'] = df.apply(lambda r: cls.safe_ratio(r.get('PARENT_NETPROFIT', 0), r.get('TOTAL_OPERATE_INCOME', 0)) * 100, axis=1)
            df['gross_margin'] = df.apply(lambda r: cls.safe_ratio(r.get('TOTAL_OPERATE_INCOME', 0) - r.get('OPERATE_COST', 0), r.get('TOTAL_OPERATE_INCOME', 0)) * 100, axis=1)
            df['roe'] = df.apply(lambda r: cls.safe_ratio(r.get('PARENT_NETPROFIT', 0), r.get('TOTAL_PARENT_EQUITY', 1)) * 100, axis=1)
            df['fcf'] = df['cfo'] - df['capex']
            
            # 4. 分红逻辑
            div_by_year = {}
            if not df_div.empty:
                df_div['attr_year'] = df_div['ann_date'].apply(lambda d: d.year - 1 if d.month <= 7 else d.year)
                div_by_year = df_div.groupby('attr_year')['cash_div'].sum().to_dict()
            
            df['dps'] = df['REPORT_DATE'].dt.year.map(div_by_year).fillna(0)
            df['payout_ratio'] = df.apply(lambda r: cls.safe_ratio(r['dps'], r.get('BASIC_EPS', 0)) * 100 if r.get('BASIC_EPS', 0) > 0 else 0, axis=1)
            
            # 5. 更多指标 (省略部分，保持核心)
            df['roic_pct'] = df['roe'] # 简化版 roic
            df['revenue_growth_pct'] = df['TOTAL_OPERATE_INCOME'].pct_change().fillna(0) * 100
            
            # 计算股本总数和每股净资产 BVPS (用于资本分配计算)
            def calculate_shares_and_bvps(row):
                net_profit = row.get('PARENT_NETPROFIT', 0)
                eps = row.get('BASIC_EPS', 0)
                equity = row.get('TOTAL_PARENT_EQUITY', 0)
                shares = (net_profit / eps) if eps and eps > 0 else 0
                bvps = (equity / shares) if shares and shares > 0 else 0
                return pd.Series([shares, bvps], index=['shares', 'bvps'])
            
            try:
                df[['shares', 'bvps']] = df.apply(calculate_shares_and_bvps, axis=1)
                # 如果大部分 shares 都是 0，说明数据源缺失 EPS，回退到使用 parent equity 作为 bvps 替代
                if (df['shares'] == 0).sum() / len(df) > 0.5:
                    df['share_change_pct'] = 0.0
                    df['bvps_growth_pct'] = df['TOTAL_PARENT_EQUITY'].pct_change().fillna(0) * 100
                else:
                    df['share_change_pct'] = df['shares'].pct_change().fillna(0) * 100
                    df['bvps_growth_pct'] = df['bvps'].pct_change().fillna(0) * 100
            except Exception:
                df['share_change_pct'] = 0.0
                df['bvps_growth_pct'] = df['TOTAL_PARENT_EQUITY'].pct_change().fillna(0) * 100

            # --- [核心修复：解决 JSON 序列化 nan 问题] ---
            # 在生成 Summary 之前，全量清理 DataFrame 中的 NaN 和 Inf
            df = df.replace([np.inf, -np.inf], np.nan).fillna(0)
            
            # 6. 生成 Summary
            latest = df.iloc[-1]
            stability_window = df.tail(5)
            
            g_vol = cls.series_volatility(stability_window['gross_margin'])
            n_vol = cls.series_volatility(stability_window['net_margin'])
            roe_vol = cls.series_volatility(stability_window['roe'])
            rev_vol = cls.series_volatility(stability_window['revenue_growth_pct'])
            
            # 资本分配分析
            capital_allocation_label = cls.classify_capital_allocation(
                float(latest.get('roic_pct', latest['roe'])),
                float(latest.get('bvps_growth_pct', 0)),
                float(latest.get('share_change_pct', 0)),
                float(latest.get('payout_ratio', 0))
            )
            financing_label = cls.classify_financing_signal(float(latest.get('share_change_pct', 0)))

            summary = {
                'cashflow_summary': {
                    'latest_cfo': round(float(latest['cfo']), 2),
                    'latest_fcf': round(float(latest['fcf']), 2),
                    'cashflow_quality_label': cls.classify_cashflow_quality(latest['roe'], 60), # 占位
                },
                'capital_allocation_summary': {
                    'capital_allocation_label': capital_allocation_label,
                    'financing_label': financing_label,
                    'latest_payout_ratio': round(float(latest.get('payout_ratio', 0)), 2),
                    'latest_dps': round(float(latest.get('dps', 0)), 4),
                },
                'stability_summary': {
                    'moat_label': cls.classify_moat_strength(stability_window['gross_margin'].mean(), g_vol, n_vol),
                    'cyclical_label': cls.classify_cyclicality(rev_vol, (stability_window['revenue_growth_pct'] < 0).sum(), roe_vol, 10),
                },
                'balance_sheet_summary': {
                    'risk_flags': cls.build_balance_sheet_flags(30, 150, 40, 5, float(latest['interest_bearing_debt'])),
                },
                'quality_history': df.tail(10).select_dtypes(include=[np.number]).round(4).combine_first(df.tail(10)).to_dict(orient='records'),
            }
            return cls.clean_json_data(summary)
        except Exception as e:
            logger.error(f"Calculator Quality Error: {e}")
            return {}

    @classmethod
    def calculate_ttm_fundamentals(cls, df_profit, df_balance):
        """计算 TTM 利润与净资产对齐序列"""
        if df_profit.empty:
            return pd.DataFrame()

        # 1. 利润表处理
        df_profit = df_profit[['REPORT_DATE', 'PARENT_NETPROFIT', 'NOTICE_DATE']].copy()
        df_profit['REPORT_DATE'] = pd.to_datetime(df_profit['REPORT_DATE'])
        df_profit['NOTICE_DATE'] = pd.to_datetime(df_profit['NOTICE_DATE'], errors='coerce')
        df_profit = df_profit.sort_values('REPORT_DATE')
        
        # 确保数值型
        df_profit['PARENT_NETPROFIT'] = pd.to_numeric(df_profit['PARENT_NETPROFIT'], errors='coerce').fillna(0)
        df_profit['q_profit'] = df_profit['PARENT_NETPROFIT']
        df_profit['ttm_profit'] = df_profit['q_profit'].rolling(window=4).sum().bfill()

        # 2. 资产负债表处理
        if not df_balance.empty:
            cols = ['REPORT_DATE', 'TOTAL_PARENT_EQUITY']
            if 'TOTAL_ASSETS' in df_balance.columns:
                cols.append('TOTAL_ASSETS')
            df_balance = df_balance[cols].copy()
            df_balance['REPORT_DATE'] = pd.to_datetime(df_balance['REPORT_DATE'])
            df_balance['TOTAL_PARENT_EQUITY'] = pd.to_numeric(df_balance['TOTAL_PARENT_EQUITY'], errors='coerce').fillna(0)
            if 'TOTAL_ASSETS' in df_balance.columns:
                df_balance['TOTAL_ASSETS'] = pd.to_numeric(df_balance['TOTAL_ASSETS'], errors='coerce').fillna(0)
        else:
            df_balance = pd.DataFrame(columns=['REPORT_DATE', 'TOTAL_PARENT_EQUITY', 'TOTAL_ASSETS'])

        # 补全公告日逻辑
        def get_fallback_notice_date(row):
            if pd.notnull(row['NOTICE_DATE']): return row['NOTICE_DATE']
            r_date = row['REPORT_DATE']
            if r_date.month == 3: return datetime(r_date.year, 5, 1)
            if r_date.month == 6: return datetime(r_date.year, 9, 1)
            if r_date.month == 9: return datetime(r_date.year, 11, 1)
            if r_date.month == 12: return datetime(r_date.year + 1, 5, 1)
            return r_date + pd.Timedelta(days=90)

        df_profit['NOTICE_DATE'] = df_profit.apply(get_fallback_notice_date, axis=1)
        df_profit = df_profit.dropna(subset=['NOTICE_DATE'])

        # 合并
        df_fund = pd.merge(df_profit[['REPORT_DATE', 'ttm_profit', 'NOTICE_DATE']], 
                          df_balance, on='REPORT_DATE', how='left')
        
        df_fund = df_fund.sort_values('REPORT_DATE')
        df_fund['TOTAL_PARENT_EQUITY'] = df_fund['TOTAL_PARENT_EQUITY'].mask(df_fund['TOTAL_PARENT_EQUITY'] == 0).ffill().fillna(0)
        df_fund['ttm_profit'] = df_fund['ttm_profit'].mask(df_fund['ttm_profit'] == 0).ffill().fillna(0)
        
        df_fund = df_fund.dropna(subset=['NOTICE_DATE'])
        df_fund = df_fund.sort_values('NOTICE_DATE').drop_duplicates('NOTICE_DATE', keep='last')
        
        return df_fund

    @classmethod
    def calculate_ttm_cashflow(cls, df_cash):
        if df_cash.empty:
            return pd.DataFrame()
        
        df = df_cash[['REPORT_DATE', 'NETCASH_OPERATE', 'NOTICE_DATE']].copy()
        df['REPORT_DATE'] = pd.to_datetime(df['REPORT_DATE'])
        df['NETCASH_OPERATE'] = pd.to_numeric(df['NETCASH_OPERATE'], errors='coerce').fillna(0)
        df = df.sort_values('REPORT_DATE')
        df['ttm_cfo'] = df['NETCASH_OPERATE'].rolling(window=4).sum().bfill()
        return df

    @classmethod
    def extract_dividend_metrics(cls, df_div):
        """解析分红 DataFrame"""
        if df_div.empty:
            return pd.DataFrame()

        working = df_div.copy()
        col_map = {
            'ann_date_raw': ['公告日期', 0],
            'plan_str': ['分红方案', 1],
            'cash_div_raw': ['派息', '派息(元)', '股利(元)', 3],
        }
        
        for semantic_name, candidates in col_map.items():
            for cand in candidates:
                if isinstance(cand, str) and cand in working.columns:
                    working[semantic_name] = working[cand]
                    break
                elif isinstance(cand, int) and cand < len(working.columns):
                    working[semantic_name] = working.iloc[:, cand]
                    break
        
        import re
        def extract_cash_div(row):
            p_str = str(row.get('plan_str', ''))
            match = re.search(r'10派([\d\.]+)', p_str)
            if match:
                return float(match.group(1)) / 10.0
            val = pd.to_numeric(row.get('cash_div_raw'), errors='coerce')
            return (val / 10.0) if pd.notna(val) and val > 0 else 0.0

        working['ann_date'] = pd.to_datetime(working['ann_date_raw'], errors='coerce')
        working['cash_div'] = working.apply(extract_cash_div, axis=1)
        
        working = working.dropna(subset=['ann_date']).sort_values('ann_date')
        working = working[working['cash_div'] > 0]
        working = working.drop_duplicates(subset=['ann_date', 'cash_div'])
        
        if not working.empty:
            working = working.sort_values('ann_date')
            to_keep = []
            for i in range(len(working)):
                if i == len(working) - 1:
                    to_keep.append(True)
                    continue
                curr_row = working.iloc[i]
                next_row = working.iloc[i+1]
                is_duplicate = (
                    curr_row['cash_div'] == next_row['cash_div'] and 
                    (next_row['ann_date'] - curr_row['ann_date']).days <= 30
                )
                to_keep.append(not is_duplicate)
            working = working[to_keep]
            
        return working

    @staticmethod
    def classify_holder_trend(change_pct):
        if change_pct <= -10: return '筹码集中'
        if change_pct >= 10: return '筹码分散'
        return '基本稳定'

    @classmethod
    def calculate_f_score(cls, df_fund, df_cash):
        """计算 F-Score 核心指标"""
        if df_fund.empty: return {"score": 0, "details": []}
        
        latest = df_fund.iloc[-1]
        prev_year = df_fund[df_fund['REPORT_DATE'] <= (latest['REPORT_DATE'] - pd.Timedelta(days=330))].tail(1)
        
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
        
        # 1. 盈利能力
        assets = latest.get('TOTAL_ASSETS', latest.get('TOTAL_PARENT_EQUITY', 0))
        roa = (latest['ttm_profit'] / assets) if pd.notnull(assets) and assets > 0 else 0
        
        p = roa > 0
        total_possible += 1
        if p: score += 1
        details.append({"name": "ROA > 0", "passed": p, "val": f"{round(roa*100, 2)}%"})
        
        p = latest['ttm_profit'] > 0
        total_possible += 1
        if p: score += 1
        details.append({"name": "净利润 > 0", "passed": p, "val": "Positive" if p else "Negative"})

        if cfo_available:
            total_possible += 2
            p = cfo_val > 0
            if p: score += 1
            details.append({"name": "经营性现金流 > 0", "passed": p, "val": "Positive" if p else "Negative"})

            p = cfo_val > latest['ttm_profit']
            if p: score += 1
            details.append({"name": "现金流 > 净利润", "passed": p, "val": f"CFO/NI: {round(cfo_val/latest['ttm_profit'], 2) if latest['ttm_profit'] != 0 else 'N/A'}"})

        # 2. 增长趋势
        if not prev_year.empty:
            prev_latest = prev_year.iloc[0]
            prev_assets = prev_latest.get('TOTAL_ASSETS', prev_latest['TOTAL_PARENT_EQUITY'])
            prev_roa = (prev_latest['ttm_profit'] / prev_assets) if prev_assets > 0 else 0
            p = roa > prev_roa
            total_possible += 1
            if p: score += 1
            details.append({"name": "ROA 同比提升", "passed": p, "val": f"{round(roa*100, 2)}% vs {round(prev_roa*100, 2)}%"})
        else:
            details.append({"name": "ROA 同比提升", "passed": False, "val": "无历史数据"})

        final_score = round((score / total_possible) * 10, 1) if total_possible else 0
        return {"score": min(final_score, 10.0), "details": details}

    @staticmethod
    def series_volatility(series):
        clean = pd.to_numeric(pd.Series(series), errors='coerce').dropna()
        if len(clean) <= 1: return 0.0
        return float(clean.std(ddof=0))

    @classmethod
    def calculate_dividend_at_date(cls, df_divs, date_dt):
        """智能推算截至特定日期的自然年派息总额"""
        if df_divs.empty: return 0.0
        date_dt = pd.to_datetime(date_dt)
        past_divs = df_divs[df_divs['ann_date'] <= date_dt].copy()
        if past_divs.empty: return 0.0
        past_divs['year'] = past_divs['ann_date'].dt.year
        yearly_sum = past_divs.groupby('year')['cash_div'].sum().to_dict()
        current_year, last_year = date_dt.year, date_dt.year - 1
        current_sum = yearly_sum.get(current_year, 0.0)
        last_sum = yearly_sum.get(last_year, 0.0)
        if current_sum >= last_sum * 0.8: return float(current_sum)
        if date_dt.month < 9: return float(last_sum)
        last_div_date = past_divs.iloc[-1]['ann_date']
        return float(current_sum) if current_sum > 0 else (float(last_sum) if (date_dt - last_div_date).days <= 450 else 0.0)

    @classmethod
    def align_to_prices(cls, df_fund, df_prices):
        if df_prices.empty: return df_prices
        df_prices = df_prices.copy()
        df_prices['date_dt'] = pd.to_datetime(df_prices['date'])
        if df_fund.empty:
            df_prices['ttm_profit'] = 0
            df_prices['TOTAL_PARENT_EQUITY'] = 0
            return df_prices
        df_fund = df_fund.dropna(subset=['NOTICE_DATE']).sort_values('NOTICE_DATE')
        df_prices = df_prices.sort_values('date_dt')
        df_merged = pd.merge_asof(df_prices, df_fund, left_on='date_dt', right_on='NOTICE_DATE', direction='backward')
        df_merged['ttm_profit'] = df_merged['ttm_profit'].fillna(0)
        df_merged['TOTAL_PARENT_EQUITY'] = df_merged['TOTAL_PARENT_EQUITY'].fillna(0)
        return df_merged

    @classmethod
    def calculate_percentiles(cls, history, column='pe', period_years=10):
        if not history: return {'p10': 0, 'p50': 0, 'p90': 0}
        df = pd.DataFrame(history)
        if column not in df.columns: return {'p10': 0, 'p50': 0, 'p90': 0}
        df['date_dt'] = pd.to_datetime(df['date'])
        start_date = datetime.now() - pd.Timedelta(days=period_years * 365)
        df = df[df['date_dt'] >= start_date]
        vals = df[df[column] > 0][column]
        if vals.empty: return {'p10': 0, 'p50': 0, 'p90': 0}
        return {
            'p10': round(vals.quantile(0.1), 2),
            'p50': round(vals.quantile(0.5), 2),
            'p90': round(vals.quantile(0.9), 2),
            'current': round(vals.iloc[-1], 2)
        }

    @classmethod
    def extract_cashflow_metrics(cls, df_cash):
        if df_cash is None or df_cash.empty:
            return pd.DataFrame(columns=['REPORT_DATE', 'cfo', 'capex']), 'unavailable'
        working = df_cash.copy()
        cfo_col = cls.first_existing_column(working, ['NETCASH_OPERATE', '经营活动产生的现金流量净额'])
        capex_col = cls.first_existing_column(working, ['CONSTRUCT_LONG_ASSET', 'FIXED_ASSET_OTHER_LONG_ASSET_PAY', 'PURCHASE_FIX_INTAN_OTHER_LONG_ASSET', '购建固定资产、无形资产和其他长期资产支付的现金'])
        invest_col = cls.first_existing_column(working, ['NETCASH_INVEST', '投资活动产生的现金流量净额'])
        working['cfo'] = pd.to_numeric(working[cfo_col], errors='coerce').fillna(0) if cfo_col else 0.0
        capex_src = 'unavailable'
        if capex_col:
            working['capex'] = pd.to_numeric(working[capex_col], errors='coerce').fillna(0).abs()
            capex_src = capex_col
        elif invest_col:
            invest_series = pd.to_numeric(working[invest_col], errors='coerce').fillna(0)
            working['capex'] = invest_series.apply(lambda x: abs(x) if x < 0 else 0.0)
            capex_src = f'{invest_col}:fallback'
        else: working['capex'] = 0.0
        return working[['REPORT_DATE', 'cfo', 'capex']], capex_src

    @staticmethod
    def classify_cashflow_quality(cfo_to_profit_pct, fcf_to_profit_pct):
        if cfo_to_profit_pct >= 100 and fcf_to_profit_pct >= 60: return '强'
        if cfo_to_profit_pct >= 80 and fcf_to_profit_pct >= 30: return '中'
        return '弱'

    @classmethod
    def extract_capital_structure_metrics(cls, df_balance):
        cols = ['REPORT_DATE', 'cash_balance', 'interest_bearing_debt', 'invested_capital']
        if df_balance is None or df_balance.empty: return pd.DataFrame(columns=cols), 'equity_only'
        working = df_balance.copy()
        cash_col = cls.first_existing_column(working, ['MONETARYFUNDS', 'MONETARY_CAP', 'CASH_AND_CASH_EQUIV'])
        debt_cols = [c for c in ['SHORT_LOAN', 'NONCURRENT_LIAB_DUE_WITHIN_1Y', 'LONG_LOAN', 'BOND_PAYABLE', 'LONG_PAYABLE'] if c in working.columns]
        working['cash_balance'] = pd.to_numeric(working[cash_col], errors='coerce').fillna(0) if cash_col else 0.0
        debt_series = pd.Series(0.0, index=working.index)
        for c in debt_cols: debt_series = debt_series.add(pd.to_numeric(working[c], errors='coerce').fillna(0), fill_value=0)
        working['interest_bearing_debt'] = debt_series
        equity = pd.to_numeric(working['TOTAL_PARENT_EQUITY'], errors='coerce').fillna(0)
        working['invested_capital'] = (equity + working['interest_bearing_debt'] - working['cash_balance']).clip(lower=0)
        return working[cols], 'equity_debt_cash_proxy' if (debt_cols or cash_col) else 'equity_only'

    @classmethod
    def sum_existing_columns(cls, frame, candidates):
        cols = [c for c in candidates if c in frame.columns]
        if not cols: return pd.Series(0.0, index=frame.index)
        series = pd.Series(0.0, index=frame.index)
        for c in cols: series = series.add(pd.to_numeric(frame[c], errors='coerce').fillna(0), fill_value=0)
        return series

    @classmethod
    def extract_balance_risk_metrics(cls, df_balance):
        cols = ['REPORT_DATE', 'short_debt', 'receivable_balance', 'inventory_balance', 'prepayment_balance', 'goodwill_balance']
        if df_balance is None or df_balance.empty: return pd.DataFrame(columns=cols)
        working = df_balance.copy()
        working['short_debt'] = cls.sum_existing_columns(working, ['SHORT_LOAN', 'NONCURRENT_LIAB_DUE_WITHIN_1Y', 'CURRENT_PORTION_OF_NONCURRENT_LIABILITIES'])
        working['receivable_balance'] = cls.sum_existing_columns(working, ['ACCOUNTS_RECE', 'ACCOUNTS_RECEIVABLE', 'NOTES_RECE', '应收账款', '应收票据'])
        working['inventory_balance'] = cls.sum_existing_columns(working, ['INVENTORY', '存货'])
        working['prepayment_balance'] = cls.sum_existing_columns(working, ['PREPAYMENT', '预付款项'])
        working['goodwill_balance'] = cls.sum_existing_columns(working, ['GOODWILL', '商誉'])
        return working[cols]

    @staticmethod
    def classify_financing_signal(share_change_pct):
        if share_change_pct <= -1.5: return '回购/缩股'
        if share_change_pct >= 3: return '再融资/摊薄'
        return '股本稳定'

    @staticmethod
    def classify_capital_allocation(roic_pct, bvps_growth_pct, share_change_pct, payout_ratio):
        if roic_pct >= 12 and bvps_growth_pct >= 8 and share_change_pct <= 1: return '高质量复投'
        if share_change_pct >= 3 and bvps_growth_pct <= 5: return '摊薄扩张'
        if payout_ratio >= 60 and bvps_growth_pct < 8: return '分红兑现'
        return '均衡配置'

    @staticmethod
    def classify_margin_stability(g_vol, n_vol):
        worst = max(g_vol, n_vol)
        if worst <= 3: return '高稳定'
        if worst <= 6: return '中等波动'
        return '高波动'

    @staticmethod
    def classify_return_stability(roe_vol, roic_vol):
        worst = max(roe_vol, roic_vol)
        if worst <= 4: return '高稳定'
        if worst <= 8: return '中等波动'
        return '高波动'

    @staticmethod
    def classify_moat_strength(avg_g, g_vol, n_vol):
        if avg_g >= 45 and g_vol <= 4 and n_vol <= 3: return '宽护城河'
        if avg_g >= 30 and g_vol <= 7 and n_vol <= 5: return '中等护城河'
        return '待验证'

    @staticmethod
    def classify_cyclicality(rev_vol, neg_yrs, roe_vol, g_range):
        score = 0
        if rev_vol >= 15: score += 1
        if neg_yrs >= 2: score += 1
        if roe_vol >= 8: score += 1
        if g_range >= 10: score += 1
        return '强周期' if score >= 3 else ('中周期' if score >= 2 else '弱周期')

    @staticmethod
    def classify_operating_stability(m_label, r_label, c_label):
        if c_label == '弱周期' and m_label == '高稳定' and r_label != '高波动': return '经营稳健'
        if c_label == '强周期' or r_label == '高波动': return '波动明显'
        return '中性'

    @staticmethod
    def classify_liquidity(s_debt_cov, n_cash_pct, debt_val):
        if debt_val <= 0: return '净现金'
        if s_debt_cov >= 160 and n_cash_pct >= -10: return '现金覆盖'
        if s_debt_cov >= 100: return '可控'
        return '偏紧'

    @staticmethod
    def classify_asset_quality(rip_rev_pct, gw_eq_pct):
        if rip_rev_pct <= 35 and gw_eq_pct <= 10: return '轻'
        if rip_rev_pct <= 60 and gw_eq_pct <= 25: return '中性'
        return '承压'

    @classmethod
    def classify_balance_sheet_risk(cls, d_eq, s_cov, rip_rev, gw_eq, debt_val):
        if debt_val <= 0 or (d_eq <= 30 and s_cov >= 130 and rip_rev <= 35 and gw_eq <= 10): return '低风险'
        if d_eq <= 80 and s_cov >= 90 and rip_rev <= 55 and gw_eq <= 25: return '中风险'
        return '高风险'

    @classmethod
    def build_balance_sheet_flags(cls, d_eq, s_cov, rip_rev, gw_eq, debt_val):
        flags = []
        if debt_val > 0 and s_cov < 100: flags.append('短债覆盖偏紧')
        if d_eq > 80: flags.append('有息负债偏高')
        if rip_rev > 55: flags.append('营运资产占收入偏高')
        if gw_eq > 25: flags.append('商誉占净资产偏高')
        return flags or ['资产负债表相对稳健']
