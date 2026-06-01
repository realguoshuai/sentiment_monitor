"""
数据源 Provider 层 —— 为上层 Service 提供统一的数据获取接口。

设计原则：
- 每个 Provider 封装一个外部数据源
- 上层 Service 通过 fallback 链调用多个 Provider，对调用方透明
- Provider 内部处理认证、限流、重试和数据格式归一化
"""
