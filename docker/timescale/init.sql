-- 启用 TimescaleDB 扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- 日 K 线超表
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_daily (
    symbol     TEXT        NOT NULL,   -- 股票代码，如 000001.SZ
    trade_date DATE        NOT NULL,   -- 交易日（DATE 类型避免时区歧义）
    open       NUMERIC(10,2),
    high       NUMERIC(10,2),
    low        NUMERIC(10,2),
    close      NUMERIC(10,2),
    pre_close  NUMERIC(10,2),
    volume     BIGINT,                 -- 成交量（股）
    amount     NUMERIC(16,2),          -- 成交额（元）
    amplitude  NUMERIC(5,2),           -- 振幅 %
    pct_change NUMERIC(5,2),           -- 涨跌幅 %
    turn       NUMERIC(6,4),           -- 换手率
    PRIMARY KEY (symbol, trade_date)
);

-- 转换为超表
SELECT create_hypertable('stock_daily', 'trade_date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- 配置压缩策略：30天前的数据自动压缩
ALTER TABLE stock_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);
SELECT add_compression_policy('stock_daily', INTERVAL '30 days');

-- 连续聚合：每日涨幅榜（减少重复全表扫描）
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_gainers
WITH (timescaledb.continuous) AS
SELECT symbol,
       time_bucket('1 day', trade_date) AS day,
       close,
       pct_change,
       volume,
       RANK() OVER (PARTITION BY time_bucket('1 day', trade_date) ORDER BY pct_change DESC) AS rank
FROM stock_daily
GROUP BY symbol, trade_date, close, pct_change, volume
WITH NO DATA;

SELECT add_continuous_aggregate_policy('daily_gainers',
    start_offset    => INTERVAL '7 days',
    end_offset      => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 day'
);

-- ============================================================
-- 分钟 K 线超表
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_minute (
    symbol      TEXT           NOT NULL,
    trade_time  TIMESTAMPTZ    NOT NULL,
    open        NUMERIC(10,2),
    high        NUMERIC(10,2),
    low         NUMERIC(10,2),
    close       NUMERIC(10,2),
    volume      BIGINT,
    amount      NUMERIC(16,2),
    PRIMARY KEY (symbol, trade_time)
);

SELECT create_hypertable('stock_minute', 'trade_time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

ALTER TABLE stock_minute SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);
SELECT add_compression_policy('stock_minute', INTERVAL '7 days');

-- ============================================================
-- 新闻原始数据表
-- ============================================================
CREATE TABLE IF NOT EXISTS news_raw (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT        NOT NULL,
    title           TEXT        NOT NULL,
    content         TEXT,
    url             TEXT        UNIQUE,
    publish_time    TIMESTAMPTZ NOT NULL,
    crawl_time      TIMESTAMPTZ DEFAULT NOW(),
    related_stocks  TEXT[],
    sentiment_label TEXT,
    sentiment_score NUMERIC(5,4),
    is_duplicate    BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_news_publish_time ON news_raw (publish_time DESC);
CREATE INDEX IF NOT EXISTS idx_news_stock ON news_raw USING GIN (related_stocks);
CREATE INDEX IF NOT EXISTS idx_news_sentiment ON news_raw (sentiment_label);

-- ============================================================
-- 持仓表
-- ============================================================
CREATE TABLE IF NOT EXISTS portfolio (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT         NOT NULL DEFAULT 'default',
    symbol      TEXT         NOT NULL,
    name        TEXT         NOT NULL,
    cost_price  NUMERIC(10,2) NOT NULL,
    volume      INTEGER      NOT NULL,
    group_id    INTEGER,                     -- 所属分组
    add_time    TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS portfolio_snapshot (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT         NOT NULL DEFAULT 'default',
    symbol        TEXT         NOT NULL,
    current_price NUMERIC(10,2),
    pnl           NUMERIC(12,2),
    pnl_pct       NUMERIC(6,4),
    snapshot_time TIMESTAMPTZ  DEFAULT NOW()
);

-- ============================================================
-- 持仓分组表
-- ============================================================
CREATE TABLE IF NOT EXISTS watchlist_group (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    user_id     TEXT DEFAULT 'default'
);

-- ============================================================
-- 数据质量检查表
-- ============================================================
CREATE TABLE IF NOT EXISTS data_quality (
    id          SERIAL PRIMARY KEY,
    check_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    check_name  TEXT NOT NULL,
    result      TEXT,
    is_abnormal BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 因子值表（长表范式，统一存储因子数据）
-- ============================================================
CREATE TABLE IF NOT EXISTS factor_value (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT           NOT NULL,
    trade_date  DATE           NOT NULL,
    factor_name TEXT           NOT NULL,   -- 因子名，如 ma_5, rsi_14, macd_dif
    value       NUMERIC(20,6),             -- 因子值
    created_at  TIMESTAMPTZ    DEFAULT NOW(),
    UNIQUE (symbol, trade_date, factor_name)
);

CREATE INDEX IF NOT EXISTS idx_factor_lookup
    ON factor_value (symbol, trade_date, factor_name);

CREATE INDEX IF NOT EXISTS idx_factor_date_factor
    ON factor_value (trade_date, factor_name);

-- ============================================================
-- 股票基本信息表
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_info (
    symbol      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    list_date   DATE,            -- 上市日期（用于回测幸存者偏差过滤）
    delist_date DATE,            -- 退市日期
    sector      TEXT,            -- 所属行业
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
