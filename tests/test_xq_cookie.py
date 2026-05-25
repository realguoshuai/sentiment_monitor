import requests
url = "https://xueqiu.com"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}
try:
    r = requests.get(url, headers=headers, timeout=5)
    print("STATUS:", r.status_code)
    print("COOKIES:", r.cookies.get_dict())
except Exception as e:
    print("ERROR:", e)
