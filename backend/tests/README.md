# FundRadar Backend Tests

## 运行方式

```bash
cd ~/clawd/fund-radar/backend
source ../.venv/bin/activate
PYTHONPATH=. python -m pytest tests/ -v --tb=short
```

## 测试分层

- `test_crawlers.py` — 爬虫层：雪球、新闻、基金净值（需要网络）
- `test_analyzers.py` — 分析层：LLM解析、评分、情感分析、信号生成（需要LLM API）
- `test_signal_pusher.py` — 推送层：消息格式化（纯逻辑，不需要外部服务）
- `test_e2e.py` — 端到端：爬虫→分析→信号→格式化全链路
