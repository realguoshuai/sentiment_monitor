import requests
url = "http://qt.gtimg.cn/q=sz000423,sz000858,sz002384,sh600519"
try:
    r = requests.get(url, timeout=5)
    print("STATUS:", r.status_code)
    print("ENCODING:", r.encoding)
    print("TEXT SHORT:", r.text[:200])
except Exception as e:
    print("ERROR:", e)
