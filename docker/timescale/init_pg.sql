-- 初始化 PostgreSQL 数据库表结构
-- 注意：此版本不含 TimescaleDB 扩展，适用于标准 PostgreSQL 环境
-- 开发/测试用，生产环境建议使用 TimescaleDB

-- ============================================================
-- 日 K 线表
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_daily (
    symbol     TEXT        NOT NULL,   -- 股票代码，如 000001.SZ
    trade_date DATE        NOT NULL,   -- 交易日
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

-- ============================================================
-- 分钟 K 线表
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_minute (
    symbol     TEXT        NOT NULL,
    trade_time TIMESTAMPTZ NOT NULL,
    open       NUMERIC(10,2),
    high       NUMERIC(10,2),
    low        NUMERIC(10,2),
    close      NUMERIC(10,2),
    volume     BIGINT,
    amount     NUMERIC(16,2),
    PRIMARY KEY (symbol, trade_time)
);

-- ============================================================
-- 新闻原始数据表
-- ============================================================
CREATE TABLE IF NOT EXISTS news_raw (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT        NOT NULL,          -- 来源
    title           TEXT        NOT NULL,           -- 标题
    content         TEXT,                           -- 正文
    url             TEXT,                           -- 原文链接
    publish_time    TIMESTAMPTZ,                    -- 发布时间
    crawl_time      TIMESTAMPTZ DEFAULT NOW(),       -- 抓取时间
    related_stocks  TEXT[],                          -- 关联股票数组
    sentiment_label TEXT,                            -- 情感标签
    sentiment_score NUMERIC(5,4)                     -- 情感分数
);

CREATE INDEX IF NOT EXISTS idx_news_publish_time ON news_raw (publish_time DESC);
CREATE INDEX IF NOT EXISTS idx_news_stock ON news_raw USING GIN (related_stocks);

-- ============================================================
-- 持仓表
-- ============================================================
CREATE TABLE IF NOT EXISTS portfolio (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT        NOT NULL DEFAULT 'default',
    symbol      TEXT        NOT NULL,                -- 股票代码
    name        TEXT        NOT NULL,                -- 股票名称
    cost_price  NUMERIC(10,2) NOT NULL,              -- 成本价
    volume      INTEGER     NOT NULL,                -- 持有数量
    group_id    INTEGER,                             -- 分组 ID
    add_time    TIMESTAMPTZ DEFAULT NOW()            -- 添加时间
);

CREATE INDEX IF NOT EXISTS idx_portfolio_user ON portfolio (user_id);

-- ============================================================
-- 因子值表（长表范式）
-- ============================================================
CREATE TABLE IF NOT EXISTS factor_value (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT           NOT NULL,
    trade_date  DATE           NOT NULL,
    factor_name TEXT           NOT NULL,
    value       NUMERIC(20,6),
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
    list_date   DATE,
    delist_date DATE,
    sector      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
