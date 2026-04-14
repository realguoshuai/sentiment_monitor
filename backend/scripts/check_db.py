from bootstrap_django import setup_django
setup_django()

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
django.setup()

from api.models import Stock, SentimentData

print("--- ALL STOCKS IN DB ---")
for stock in Stock.objects.all():
    print(stock.name, stock.symbol)

print("\n--- LATEST SENTIMENT DATE PER STOCK ---")
for stock in Stock.objects.all():
    sd = SentimentData.objects.filter(stock=stock).order_by('-date').first()
    if sd:
        print(f"{stock.name}: {sd.date} (News: {sd.news_count}, Reports: {sd.report_count})")
    else:
        print(f"{stock.name}: NO DATA")

