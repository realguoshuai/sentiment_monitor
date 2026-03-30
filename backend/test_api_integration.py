import requests

def test_api_endpoint(period, limit):
    symbols = "sz000423,sz002304"
    url = f"http://127.0.0.1:8000/api/sentiment/comparison_historical/?symbols={symbols}&limit={limit}&period={period}"
    print(f"Testing URL: {url}")
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            s1 = symbols.split(',')[0].upper()
            points = data.get(s1, [])
            print(f"Period: {period}, Points: {len(points)}")
            if points:
                print(f"  First: {points[0]}")
                print(f"  Last:  {points[-1]}")
        else:
            print(f"Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Request failed: {e}")

# Note: The server must be running for this to work.
# If I cannot run the server, I can test the PriceService directly via python manage.py shell.
