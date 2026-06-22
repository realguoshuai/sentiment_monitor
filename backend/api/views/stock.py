"""股票 CRUD 视图 + 单股采集队列"""

import json
import logging
import re
import threading
import time
from collections import deque

from django.core.cache import cache
from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.response import Response

from ..models import Stock
from ..serializers import StockSerializer
from ..price_service import PriceService
from ..utils import format_symbol
from collector.collector import collect_stock_data

logger = logging.getLogger(__name__)

COLLECTION_LOCK_KEY = 'manual_collection_lock'

# 单股采集队列（模块级全局状态，Gunicorn 多进程下各 worker 独立）
_single_stock_lock = threading.Lock()
_single_stock_queue = deque()
_single_stock_pending_ids = set()
_single_stock_thread = None


class StockViewSet(viewsets.ModelViewSet):
    """股票视图集"""
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    lookup_field = 'symbol'

    @staticmethod
    def _coerce_list(value):
        if value in (None, ''):
            return []
        if isinstance(value, (list, tuple, set)):
            items = list(value)
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith('['):
                try:
                    parsed = json.loads(raw)
                    items = parsed if isinstance(parsed, list) else [raw]
                except (TypeError, ValueError):
                    items = re.split(r'[,，\n]+', raw)
            else:
                items = re.split(r'[,，\n]+', raw)
        else:
            items = [value]
        return [str(item).strip() for item in items if str(item).strip()]

    @classmethod
    def _normalize_peer_symbols(cls, value, current_symbol=''):
        current_fixed = format_symbol(current_symbol) if current_symbol else ''
        normalized = []
        for item in cls._coerce_list(value):
            fixed_symbol = format_symbol(item)
            if fixed_symbol == current_fixed or fixed_symbol in normalized:
                continue
            normalized.append(fixed_symbol)
        return normalized

    def _normalize_stock_payload(self, raw_data, *, partial=False, current_symbol=''):
        data = raw_data.copy()
        current_fixed = format_symbol(current_symbol) if current_symbol else ''
        symbol = str(data.get('symbol', '') or '').strip().upper()
        fixed_symbol = current_fixed

        if symbol:
            fixed_symbol = format_symbol(symbol)
            data['symbol'] = fixed_symbol
        elif not partial:
            raise ValueError('股票代码不能为空')

        if not partial or 'keywords' in data:
            keywords = self._coerce_list(data.get('keywords', []))
            if not keywords and fixed_symbol:
                keywords = [fixed_symbol[2:]]
            data['keywords'] = json.dumps(keywords, ensure_ascii=False)

        if not partial or 'peer_symbols' in data:
            peer_symbols = self._normalize_peer_symbols(data.get('peer_symbols', []), fixed_symbol)
            data['peer_symbols'] = json.dumps(peer_symbols, ensure_ascii=False)

        if not partial or 'industry' in data:
            data['industry'] = str(data.get('industry', '') or '').strip()

        return data, fixed_symbol

    def create(self, request, *args, **kwargs):
        """添加股票时自动修复代码格式"""
        try:
            data, fixed_symbol = self._normalize_stock_payload(request.data, partial=False)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not data.get('name'):
            try:
                rt = PriceService.get_realtime_price([fixed_symbol])
                if fixed_symbol in rt:
                    data['name'] = rt[fixed_symbol]['name']
                else:
                    data['name'] = fixed_symbol
            except Exception as e:
                logger.warning(f"Failed to fetch stock name for {fixed_symbol}: {e}")
                data['name'] = fixed_symbol

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except IntegrityError:
            return Response({'error': f'股票 {fixed_symbol} 已存在'}, status=status.HTTP_409_CONFLICT)
        _trigger_single_stock_collection(serializer.instance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            data, _ = self._normalize_stock_payload(
                request.data, partial=False, current_symbol=instance.symbol,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            data, _ = self._normalize_stock_payload(
                request.data, partial=True, current_symbol=instance.symbol,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """删除股票"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _trigger_single_stock_collection(stock: Stock) -> None:
    """新增股票后在后台补采该标的。"""

    def worker():
        global _single_stock_thread

        while True:
            with _single_stock_lock:
                if not _single_stock_queue:
                    _single_stock_thread = None
                    return
                stock_id = _single_stock_queue.popleft()
                _single_stock_pending_ids.discard(stock_id)

            queued_stock = Stock.objects.filter(pk=stock_id).first()
            if queued_stock is None:
                logger.info("Skip auto collection for deleted stock id=%s", stock_id)
                continue

            _lock_wait_count = 0
            while cache.get(COLLECTION_LOCK_KEY):
                _lock_wait_count += 1
                if _lock_wait_count > 30:
                    logger.warning("Global collection lock held too long, proceeding with %s anyway", queued_stock.symbol)
                    break
                logger.info("Global collection in progress. Waiting 10 seconds before collecting %s...", queued_stock.symbol)
                time.sleep(10)

            try:
                collect_stock_data(queued_stock)
                logger.info("Auto collected sentiment data for newly added stock %s", queued_stock.symbol)
            except Exception:
                logger.exception("Auto collection failed for newly added stock %s", queued_stock.symbol)

    global _single_stock_thread
    with _single_stock_lock:
        if stock.pk in _single_stock_pending_ids:
            return

        _single_stock_queue.append(stock.pk)
        _single_stock_pending_ids.add(stock.pk)

        if _single_stock_thread is None or not _single_stock_thread.is_alive():
            _single_stock_thread = threading.Thread(target=worker, daemon=True)
            _single_stock_thread.start()
