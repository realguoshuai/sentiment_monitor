#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情监控系统 - Web服务器
提供仪表板和数据访问
"""

import http.server
import socketserver
import os
import json
from datetime import datetime
from pathlib import Path

PORT = 8888

class SentimentHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()
    
    def do_GET(self):
        if self.path == '/' or self.path == '/dashboard.html':
            self.path = '/dashboard.html'
            return super().do_GET()
        
        if self.path == '/api/data':
            self.send_json_data()
            return
        
        return super().do_GET()
    
    def send_json_data(self):
        data_dir = Path(__file__).parent / 'data' / 'output'
        today = datetime.now().strftime('%Y%m%d')
        
        latest_file = None
        for f in sorted(data_dir.glob('sentiment_*.json'), reverse=True):
            if f.name.startswith(f'sentiment_{today}'):
                latest_file = f
                break
        
        if not latest_file:
            files = list(data_dir.glob('sentiment_*.json'))
            latest_file = files[0] if files else None
        
        if latest_file and latest_file.exists():
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
                return
            except Exception as e:
                print(f'Error reading file: {e}')
        
        self.send_response(404)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'{"error": "No data found"}')

def run_server():
    os.chdir(Path(__file__).parent)
    
    try:
        with socketserver.TCPServer(("", PORT), SentimentHandler) as httpd:
            print(f"\n{'='*60}")
            print(f"舆情监控系统 Web服务器")
            print(f"{'='*60}")
            print(f"\n仪表板: http://localhost:{PORT}/dashboard.html")
            print(f"API接口: http://localhost:{PORT}/api/data")
            print(f"\n按 Ctrl+C 停止服务器")
            print(f"{'='*60}\n")
            
            httpd.serve_forever()
    except OSError as e:
        print(f"\n错误: 端口 {PORT} 已被占用")
        print(f"错误信息: {e}")
        print(f"\n解决方案:")
        print(f"1. 关闭占用端口的程序")
        print(f"2. 修改 server.py 中的 PORT 变量")
        input("\n按回车键退出...")

if __name__ == "__main__":
    run_server()
