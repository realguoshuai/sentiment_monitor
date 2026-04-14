import requests

def test_tencent_api(symbol, period, limit):
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},{period},,,{limit},qfq"
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if data.get('code') == 0:
            stock_data = data['data'].get(symbol, {})
            days = stock_data.get('qfq'+period) or stock_data.get(period) or []
            print(f"Period: {period}, Count: {len(days)}")
            if days:
                print(f"First: {days[0][0]}, Last: {days[-1][0]}")
        else:
            print(f"Period: {period} failed with code {data.get('code')}")
    except Exception as e:
        print(f"Error for {period}: {e}")

symbol = "sz000423"
test_tencent_api(symbol, "day", 30)
test_tencent_api(symbol, "month", 60)
test_tencent_api(symbol, "year", 10)
