from bootstrap_django import setup_django
setup_django()

import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.models import Stock
from api.price_service import PriceService
from api.serializers import StockSerializer
from rest_framework.response import Response

def test_add_stock(symbol, name=''):
    print(f"Testing add stock: {symbol} ({name})")
    data = {'symbol': symbol, 'name': name, 'keywords': []}
    
    symbol = data.get('symbol', '').strip().upper()
    fixed_symbol = PriceService._fix_symbol(symbol)
    data['symbol'] = fixed_symbol
    
    keywords = data.get('keywords', [])
    if isinstance(keywords, list):
        data['keywords'] = json.dumps(keywords, ensure_ascii=False)
    elif keywords in (None, ''):
        data['keywords'] = json.dumps([fixed_symbol[2:]], ensure_ascii=False)
    
    if not data.get('name'):
        rt = PriceService.get_realtime_price([fixed_symbol])
        if fixed_symbol in rt:
            data['name'] = rt[fixed_symbol]['name']
            print(f"Fetched name: {data['name']}")
        else:
            data['name'] = fixed_symbol
            print(f"Fallback name: {data['name']}")
            
    serializer = StockSerializer(data=data)
    if serializer.is_valid():
        try:
            instance = serializer.save()
            print(f"Successfully added: {instance.name} ({instance.symbol})")
        except Exception as e:
            print(f"Save failed: {e}")
    else:
        print(f"Validation failed: {serializer.errors}")

if __name__ == "__main__":
    # Test with a known stock
    test_add_stock("600000") # 娴﹀彂閾惰

