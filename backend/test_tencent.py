import requests
resp = requests.get('http://qt.gtimg.cn/q=sz000423')
resp.encoding = 'gbk'
fields = resp.text.split('="')[1].split('~')
for i, val in enumerate(fields):
    print(f"Index {i}: {val}")
