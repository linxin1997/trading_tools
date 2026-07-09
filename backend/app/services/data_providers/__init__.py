# 数据提供商模块包初始化
# 新增 provider 需在此导出

from .base import BaseDataProvider
from .akshare import AKShareProvider
from .baostock_provider import BaostockProvider, get_provider as get_baostock
from .tencent_provider import TencentProvider

__all__ = [
    "BaseDataProvider",
    "AKShareProvider",
    "BaostockProvider",
    "get_baostock",
    "TencentProvider",
]
