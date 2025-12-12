"""MCP Server 定义：将 Orchestrator 的能力以工具形式暴露给 MCP 客户端。

主要职责：
- 使用 FastMCP 创建一个 MCP 服务器实例，注册工具 `generate_ppt`；
- 工具接收主题与页数参数，调用编排器生成并返回结果路径；
- 供 `mcp.client` 或其他 MCP 客户端以标准协议调用。

注意：示例调用了 `orchestrator.run(topic, num_slides)`，
如当前 `OrchestratorAgent` 未实现 `run` 方法，则需自行补充（或改为汇聚 A2A 流式结果）。
"""

import asyncio  # 预留：如需并行或异步任务管理可使用
from fastmcp import FastMCP  # 轻量 MCP 服务框架
from ai_ppt.agents.orchestrator import OrchestratorAgent  # 项目经理（编排器）
from ai_ppt.common.utils import get_logger  # 统一日志工具

logger = get_logger(__name__)

# 初始化 MCP Server，并声明服务名称
mcp = FastMCP("AI PPT Generator")
# 初始化编排器实例，用于实际执行生成逻辑
orchestrator = OrchestratorAgent()


@mcp.tool()
async def generate_ppt(topic: str, num_slides: int = 5) -> str:
    """生成 PPT 的 MCP 工具。

    参数:
        topic (str): 演示文稿主题。
        num_slides (int): 期望生成的页数，默认 5。

    返回:
        str: 成功时返回保存的 PPTX 文件路径提示；失败时返回错误信息。
    """
    logger.info(f"Received request to generate PPT for topic: {topic}")
    try:
        # 调用编排器生成 PPT（需要 OrchestratorAgent 提供 run 方法）
        file_path = await orchestrator.run(topic, num_slides)
        return f"Presentation generated successfully! File saved at: {file_path}"
    except Exception as e:
        # 捕获异常并记录日志，返回友好的错误提示
        logger.error(f"Error generating PPT: {e}")
        return f"Error generating PPT: {str(e)}"


if __name__ == "__main__":
    # 以默认配置启动 MCP Server（FastMCP 会启动内置事件循环）
    mcp.run()
