-- V3 migration: 互联网搜索舆情维度
-- 1. daily_signals 加 search_sentiment_score 列
-- 2. 新建 search_sentiments 表

-- 1. 加列（IF NOT EXISTS 兼容已有数据库）
ALTER TABLE daily_signals 
ADD COLUMN IF NOT EXISTS search_sentiment_score FLOAT;

COMMENT ON COLUMN daily_signals.search_sentiment_score IS '互联网搜索舆情分 -1~1 (V3)';

-- 2. 新建表
CREATE TABLE IF NOT EXISTS search_sentiments (
    id SERIAL PRIMARY KEY,
    sentiment_score FLOAT NOT NULL,
    sentiment_label VARCHAR(20) NOT NULL,
    result_count INTEGER NOT NULL DEFAULT 0,
    bullish_count INTEGER NOT NULL DEFAULT 0,
    bearish_count INTEGER NOT NULL DEFAULT 0,
    neutral_count INTEGER NOT NULL DEFAULT 0,
    key_points JSON,
    summary TEXT,
    query_terms JSON,
    raw_results JSON,
    llm_raw_response JSON,
    captured_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_sentiments_captured ON search_sentiments (captured_at);

COMMENT ON TABLE search_sentiments IS '搜索引擎舆情快照 (V3 — Serper.dev + LLM)';
