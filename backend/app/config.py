"""
全局配置模块

使用 pydantic-settings 从环境变量或 .env 文件加载配置项。
"""

from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置类，通过 pydantic-settings 读取环境变量"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 应用基础配置
    APP_NAME: str = "A股盯盘与复盘系统"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # 数据库配置（PostgreSQL / TimescaleDB）
    DATABASE_URL: str = Field(default="", description="数据库连接 URL")
    DATABASE_ECHO: bool = False

    # DuckDB 配置（本地分析用）
    DUCKDB_PATH: str = str(Path.home() / ".astock" / "analysis.duckdb")

    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery 配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # 外部数据源配置（akshare 无需 API Key，tushare 需注册获取）
    TUSHARE_TOKEN: str = ""

    # Ollama 大模型服务配置
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_SENTIMENT_MODEL: str = "qwen2.5:3b-instruct-q4_K_M"

    # 新闻爬取频率（分钟）
    NEWS_CRAWL_CLS_INTERVAL: int = 10
    NEWS_CRAWL_EASTMONEY_INTERVAL: int = 15
    NEWS_CRAWL_XUEQIU_INTERVAL: int = 30

    # CORS 配置
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000"], description="CORS 允许的域名")

    # 日志级别
    LOG_LEVEL: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()
