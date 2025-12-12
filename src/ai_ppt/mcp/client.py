"""MCP 客户端示例：以 STDIO 方式本地拉起 MCP Server 并调用工具。

工作流程：
1. 构造 `StdioServerParameters`，使用当前 Python 解释器直接启动 `server.py`；
2. 通过 `stdio_client` 建立与本地 MCP Server 的通信；
3. 初始化会话、列出工具、调用 `generate_ppt` 并打印返回内容。

备注：如果 MCP Server 已独立以 SSE 方式运行，可改用 `sse_client` 连接远程地址。
"""

import asyncio  # 运行异步客户端入口
import sys  # 读取命令行参数
from mcp.client.stdio import stdio_client  # 本地 STDIO 方式连接 MCP Server
from mcp.client.sse import sse_client  # 预留：SSE 方式连接远程 MCP Server
from mcp import ClientSession, StdioServerParameters  # MCP 客户端会话与服务器参数定义
import os  # 路径与环境变量处理


async def run_client(query: str):
    """运行 MCP 客户端，调用本项目 MCP Server 暴露的 `generate_ppt` 工具。

    参数:
        query (str): 用户输入的主题文本，将作为工具的 `topic` 参数。
    """
    # 如果服务已独立运行（SSE），可改用 `sse_client` 连接。
    # 这里使用 STDIO：在同一进程内直接启动 `server.py` 并建立管道通信。

    # 指向 MCP Server 脚本（本地启动）
    server_script_path = os.path.join(os.path.dirname(__file__), "server.py")
    
    # 使用相同的 Python 解释器，避免环境不一致问题
    python_executable = sys.executable
    
    # 设置 PYTHONPATH，使 `src/` 目录中的模块可被导入
    env = os.environ.copy()
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

    # 配置 STDIO Server 启动参数
    server_params = StdioServerParameters(
        command=python_executable,
        args=[server_script_path],
        env=env
    )

    # 通过 STDIO 建立连接，获得读写流，创建客户端会话
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化 MCP 会话（握手与能力协商）
            await session.initialize()
            
            # 列出可用工具，验证服务端是否注册成功
            tools = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")
            
            # 调用 `generate_ppt` 工具：传入主题与默认 5 页参数
            print(f"Generating PPT for: {query}")
            result = await session.call_tool("generate_ppt", arguments={"topic": query, "num_slides": 5})
            
            # 打印工具返回结果（此示例返回字符串文本）
            print("Result:")
            print(result.content[0].text)


if __name__ == "__main__":
    # 从命令行读取主题，默认使用 "The Future of Artificial Intelligence"
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        query = "The Future of Artificial Intelligence"
    
    # 运行客户端入口
    asyncio.run(run_client(query))
