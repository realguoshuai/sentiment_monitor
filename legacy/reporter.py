#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情报告生成模块
生成HTML和文本报告
"""

import os
from datetime import datetime
from typing import Dict, Any


class SentimentReporter:
    """舆情报告生成器"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_html_report(self, sentiment_data: Dict[str, Any]):
        """生成HTML可视化报告"""
        date_str = datetime.now().strftime('%Y%m%d')
        filename = os.path.join(self.output_dir, f'sentiment_report_{date_str}.html')
        
        html_content = self._build_html(sentiment_data)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"  HTML报告已生成: {filename}")
        
        return filename
    
    def _build_html(self, sentiment_data: Dict[str, Any]) -> str:
        """构建HTML内容"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        rows = []
        for symbol, data in sentiment_data.items():
            name = data['name']
            stats = data['statistics']
            score = data['sentiment_score']
            label = data['sentiment_label']
            hot = data['hot_score']
            disc_count = stats.get('discussion_count', 0)
            
            # 情感颜色
            color = '#28a745' if label == '正面' else ('#dc3545' if label == '负面' else '#ffc107')
            
            rows.append(f"""
            <tr>
                <td>{name}</td>
                <td>{stats['total_count']}</td>
                <td>{stats['news_count']}</td>
                <td>{stats['report_count']}</td>
                <td>{stats['announcement_count']}</td>
                <td>{disc_count}</td>
                <td>{stats['social_count']}</td>
                <td style="color: {color}">{label} ({score:.2f})</td>
                <td>{hot:.1f}</td>
            </tr>
            """)
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>舆情监控报告 - {date_str}</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        .info {{ color: #666; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: center; }}
        th {{ background: #007bff; color: white; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        tr:hover {{ background: #e9ecef; }}
        .positive {{ color: #28a745; }}
        .negative {{ color: #dc3545; }}
        .neutral {{ color: #ffc107; }}
        .summary {{ margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px; }}
        .footer {{ margin-top: 30px; text-align: center; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 舆情监控报告 - {date_str}</h1>
        <div class="info">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        
        <table>
            <thead>
                <tr>
                    <th>股票</th>
                    <th>总舆情</th>
                    <th>新闻</th>
                    <th>研报</th>
                    <th>公告</th>
                    <th>讨论</th>
                    <th>社交</th>
                    <th>情感</th>
                    <th>热度</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        
        <div class="summary">
            <h3>📈 舆情摘要</h3>
            <ul>
                <li>监控股票数量: {len(sentiment_data)}</li>
                <li>总舆情数量: {sum(d['statistics']['total_count'] for d in sentiment_data.values())}</li>
                <li>正面舆情: {sum(d['statistics']['positive_count'] for d in sentiment_data.values())}</li>
                <li>负面舆情: {sum(d['statistics']['negative_count'] for d in sentiment_data.values())}</li>
            </ul>
        </div>
        
        <div class="footer">
            生成于舆情监控系统 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
        """
        return html
    
    def generate_summary_report(self, sentiment_data: Dict[str, Any]):
        """生成汇总文本报告"""
        date_str = datetime.now().strftime('%Y%m%d')
        filename = os.path.join(self.output_dir, f'sentiment_summary_{date_str}.txt')
        
        lines = [
            "=" * 60,
            f"舆情监控汇总报告 - {datetime.now().strftime('%Y-%m-%d')}",
            "=" * 60,
            "",
        ]
        
        # 按情感排序
        sorted_data = sorted(sentiment_data.values(), 
                           key=lambda x: x['sentiment_score'], 
                           reverse=True)
        
        for data in sorted_data:
            name = data['name']
            stats = data['statistics']
            label = data['sentiment_label']
            score = data['sentiment_score']
            hot = data['hot_score']
            
            lines.append(f"{name} ({data['symbol']})")
            lines.append(f"  情感: {label} ({score:.2f})")
            lines.append(f"  热度: {hot:.1f}")
            lines.append(f"  舆情: 新闻{stats['news_count']} | 研报{stats['report_count']} | 公告{stats['announcement_count']} | 社交{stats['social_count']}")
            lines.append("")
        
        lines.append("=" * 60)
        
        report = '\n'.join(lines)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"  汇总报告已生成: {filename}")
        
        return filename
