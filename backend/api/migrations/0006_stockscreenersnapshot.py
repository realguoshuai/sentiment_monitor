from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_stock_industry_peer_symbols'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockScreenerSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('snapshot_date', models.DateField(db_index=True, verbose_name='快照日期')),
                ('symbol', models.CharField(db_index=True, max_length=20, verbose_name='股票代码')),
                ('name', models.CharField(max_length=50, verbose_name='股票名称')),
                ('industry', models.CharField(blank=True, default='', max_length=80, verbose_name='行业')),
                ('price', models.FloatField(default=0, verbose_name='价格')),
                ('market_cap', models.FloatField(default=0, verbose_name='总市值')),
                ('pe', models.FloatField(default=0, verbose_name='市盈率')),
                ('pb', models.FloatField(default=0, verbose_name='市净率')),
                ('dividend_yield', models.FloatField(default=0, verbose_name='股息率')),
                ('roe_proxy_pct', models.FloatField(default=0, verbose_name='ROE 代理')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '选股快照',
                'verbose_name_plural': '选股快照',
                'ordering': ['symbol'],
                'unique_together': {('snapshot_date', 'symbol')},
            },
        ),
        migrations.AddIndex(
            model_name='stockscreenersnapshot',
            index=models.Index(fields=['snapshot_date', 'pb'], name='api_stocksc_snapsho_9bf31c_idx'),
        ),
        migrations.AddIndex(
            model_name='stockscreenersnapshot',
            index=models.Index(fields=['snapshot_date', 'pe'], name='api_stocksc_snapsho_a3ec85_idx'),
        ),
        migrations.AddIndex(
            model_name='stockscreenersnapshot',
            index=models.Index(fields=['snapshot_date', 'roe_proxy_pct'], name='api_stocksc_snapsho_640c9a_idx'),
        ),
        migrations.AddIndex(
            model_name='stockscreenersnapshot',
            index=models.Index(fields=['snapshot_date', 'dividend_yield'], name='api_stocksc_snapsho_766b06_idx'),
        ),
    ]
