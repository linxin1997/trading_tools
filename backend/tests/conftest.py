"""
pytest 测试配置文件

定义测试用的 fixtures，如异步客户端、测试数据库等。
"""

import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def async_client() -> AsyncClient:
    """
    创建异步 HTTP 测试客户端

    Returns:
        AsyncClient: httpx 异步客户端
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
