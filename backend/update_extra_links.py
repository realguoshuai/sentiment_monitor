import os
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.models import Stock

def update_donge():
    try:
        # Dong'e Ejiao is SZ000423 in this system
        stock = Stock.objects.get(symbol='SZ000423')
        extra = [
            {"name": "互动易", "url": "https://irm.cninfo.com.cn/ircs/search?keyword=000423", "color": "emerald"},
            {"name": "招标", "url": "https://szecp.crc.com.cn/search/fullsearch.html?wd=%E4%B8%9C%E9%98%BF%E9%98%BF%E8%83%B6", "color": "amber"}
        ]
        stock.extra_links = json.dumps(extra)
        stock.save()
        print("Updated Dong'e Ejiao (SZ000423) successfully.")
    except Stock.DoesNotExist:
        print("Stock SZ000423 not found.")

if __name__ == '__main__':
    update_donge()
