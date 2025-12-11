import asyncio
import sys
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp import ClientSession, StdioServerParameters
import os

async def run_client(query: str):
    # Use SSE for connection if server is running separately, or STDIO if we spawn it
    # For simplicity, assuming we run the server separately on a port
    
    # Example using STDIO to spawn the server directly for a single run
    server_script_path = os.path.join(os.path.dirname(__file__), "server.py")
    
    # Ensure we use the same python interpreter
    python_executable = sys.executable
    
    # We need to set PYTHONPATH to include src
    env = os.environ.copy()
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

    server_params = StdioServerParameters(
        command=python_executable,
        args=[server_script_path],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List tools to verify
            tools = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")
            
            # Call the tool
            print(f"Generating PPT for: {query}")
            result = await session.call_tool("generate_ppt", arguments={"topic": query, "num_slides": 5})
            
            print("Result:")
            print(result.content[0].text)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        query = "The Future of Artificial Intelligence"
    
    asyncio.run(run_client(query))
