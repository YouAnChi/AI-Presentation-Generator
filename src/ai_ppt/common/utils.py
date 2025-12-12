"""公共工具函数：统一日志配置与外部 API Key 检查。

包含：
- `get_logger`：配置并返回指定名称的 `logging.Logger`；
- `init_api_key`：检查必需的环境变量（如 `GOOGLE_API_KEY`），缺失时抛错。
"""

import os
import logging
from fastmcp import FastMCP


def get_logger(name: str) -> logging.Logger:
    """获取带统一格式的 Logger。

    行为：
    - 设置日志级别为 INFO；
    - 设置日志格式包含时间、模块名、级别与消息；
    - 返回指定名称的 Logger。
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    return logging.getLogger(name)


def init_api_key():
    """检查外部模型所需的 API Key 是否存在。

    当前示例使用 Google Gemini，需要环境变量 `GOOGLE_API_KEY`。
    若未设置则抛出 `ValueError`，防止后续运行失败。
    """
    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY environment variable is not set")
