import asyncio
from fastmcp import FastMCP
from ai_ppt.agents.orchestrator import OrchestratorAgent
from ai_ppt.common.utils import get_logger

logger = get_logger(__name__)

# Initialize MCP Server
mcp = FastMCP("AI PPT Generator")
orchestrator = OrchestratorAgent()

@mcp.tool()
async def generate_ppt(topic: str, num_slides: int = 5) -> str:
    """
    Generates a PowerPoint presentation based on the given topic.
    
    Args:
        topic: The main topic of the presentation.
        num_slides: The number of slides to generate (default: 5).
        
    Returns:
        The file path to the generated PPTX file.
    """
    logger.info(f"Received request to generate PPT for topic: {topic}")
    try:
        file_path = await orchestrator.run(topic, num_slides)
        return f"Presentation generated successfully! File saved at: {file_path}"
    except Exception as e:
        logger.error(f"Error generating PPT: {e}")
        return f"Error generating PPT: {str(e)}"

if __name__ == "__main__":
    mcp.run()
