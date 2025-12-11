import json
import uuid
import logging
import traceback
from typing import AsyncIterable, Any
from a2a.types import AgentCard, SendMessageRequest, MessageSendParams, Message, Role, TextPart, Task
from ai_ppt.common.types import PresentationOutline, PPTGenerationRequest, SlideContent
from ai_ppt.common.utils import get_logger, init_api_key
from ai_ppt.common.base_agent import BaseAgent
from a2a.client import A2AClient
from a2a_mcp.mcp import client as mcp_client
from a2a_mcp.common.utils import get_mcp_server_config
import httpx

logger = get_logger(__name__)

class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="PPT Project Manager",
            description="Manages the end-to-end process of generating a PowerPoint presentation based on a user topic."
        )
        init_api_key()

    async def _find_agent_by_task(self, task_description: str) -> AgentCard:
        """Finds a suitable agent for the task using MCP."""
        logger.info(f"Finding agent for task: {task_description}")
        config = get_mcp_server_config()
        
        # In this sample, we assume the MCP server is running on the default port
        # In production, this should be configurable
        async with mcp_client.init_session(config.host, config.port, config.transport) as session:
            result = await mcp_client.find_agent(session, task_description)
            # The result content is a list of TextContent, we parse the first one
            agent_card_json = json.loads(result.content[0].text)
            logger.info(f"Found agent: {agent_card_json['name']}")
            return AgentCard(**agent_card_json)

    async def _call_agent(self, agent_card: AgentCard, query: str) -> str:
        """Calls a remote agent using A2A protocol."""
        logger.info(f"Calling agent {agent_card.name} with query: {query[:50]}...")
        
        try:
            # Set a longer timeout for LLM generation tasks
            async with httpx.AsyncClient(timeout=60.0) as httpx_client:
                client = A2AClient(httpx_client, agent_card)
                
                # Send message and wait for the result
                # For simplicity, we assume the agent returns a single response
                # In a real scenario, we might handle streaming chunks
                
                msg_id = str(uuid.uuid4())
                request = SendMessageRequest(
                    id=msg_id,
                    params=MessageSendParams(
                        message=Message(
                            message_id=msg_id,
                            role=Role.user,
                            parts=[TextPart(text=query)]
                        )
                    )
                )
                
                response = await client.send_message(request)
                
                # Extract content from response
                if hasattr(response, 'root') and hasattr(response.root, 'result'):
                    result = response.root.result
                    
                    # Case 1: Result is a Task with artifacts
                    # We prioritize artifacts as they contain the actual output
                    if isinstance(result, Task) or (hasattr(result, 'artifacts') and result.artifacts):
                        if result.artifacts:
                            # Iterate backwards to find the first artifact with text content
                            for artifact in reversed(result.artifacts):
                                if artifact.parts:
                                    part = artifact.parts[0]
                                    # Check for text in various locations
                                    if hasattr(part, 'root') and part.root and hasattr(part.root, 'text') and part.root.text:
                                        return part.root.text
                                    elif hasattr(part, 'text') and part.text:
                                        return part.text
                    
                    # Case 2: Result is a Task with status message
                    # Only fallback to status if no artifacts were found or they were empty
                    if hasattr(result, 'status') and result.status and result.status.message and result.status.message.parts:
                        part = result.status.message.parts[0]
                        if hasattr(part, 'root') and part.root and hasattr(part.root, 'text'):
                            return part.root.text
                        elif hasattr(part, 'text'):
                            return part.text
                            
                    # Case 3: Result is a Message
                    if isinstance(result, Message) and result.parts:
                        part = result.parts[0]
                        if hasattr(part, 'root') and hasattr(part.root, 'text'):
                            return part.root.text
                        elif hasattr(part, 'text'):
                            return part.text

                # Fallback
                return str(response)
        except Exception as e:
            # Enhanced error logging to uncover TaskGroup/ExceptionGroup details
            error_msg = f"Error calling agent {agent_card.name}: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            # If it's an ExceptionGroup (Python 3.11+), log sub-exceptions
            if hasattr(e, 'exceptions'):
                for i, sub_exc in enumerate(e.exceptions):
                    logger.error(f"Sub-exception {i+1}: {sub_exc}")
            
            return f"Error: {e}"

    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[dict[str, Any]]:
        logger.info(f"Received request: {query}")
        
        try:
            # 1. Parse Request
            # Simple heuristic: if query is just a topic
            topic = query
            request = PPTGenerationRequest(topic=topic)
            
            yield self.format_response(f"Starting project for topic: {topic}", is_complete=False)

            # 2. Plan Outline (Call Outliner Agent)
            yield self.format_response("Step 1: Planning Outline...", is_complete=False)
            
            outliner_card = await self._find_agent_by_task("Create a presentation outline")
            
            # We send the request as a JSON string to the outliner
            outliner_response_str = await self._call_agent(outliner_card, request.model_dump_json())
            
            # Parse the response (assuming it returns the JSON of PresentationOutline)
            try:
                # Clean up response string if needed (sometimes it might have markdown blocks)
                cleaned_str = outliner_response_str.strip()
                if cleaned_str.startswith("```json"):
                    cleaned_str = cleaned_str[7:]
                if cleaned_str.endswith("```"):
                    cleaned_str = cleaned_str[:-3]
                
                # Check if response is an error message
                if cleaned_str.startswith("Error:"):
                     yield self.format_response(f"Outliner Agent Failed: {cleaned_str}")
                     return

                outline_data = json.loads(cleaned_str)
                outline = PresentationOutline(**outline_data)
                yield self.format_response(f"Outline created with {len(outline.slides)} slides.", is_complete=False)
            except (json.JSONDecodeError, Exception) as e:
                 # If outliner returned text error or something else
                 yield self.format_response(f"Error from Outliner: {outliner_response_str}")
                 return

            # 3. Generate Content (Call Copywriter Agent Loop)
            yield self.format_response("Step 2: Generating Content...", is_complete=False)
            
            copywriter_card = await self._find_agent_by_task("Write content for a slide")
            
            updated_slides = []
            for i, slide in enumerate(outline.slides):
                yield self.format_response(f"Writing content for slide {i+1}/{len(outline.slides)}: {slide.title}...", is_complete=False)
                
                # Prepare payload for copywriter
                payload = {
                    "slide": slide.model_dump(),
                    "topic": outline.topic
                }
                
                slide_response_str = await self._call_agent(copywriter_card, json.dumps(payload))
                
                try:
                    cleaned_str = slide_response_str.strip()
                    if cleaned_str.startswith("```json"):
                        cleaned_str = cleaned_str[7:]
                    if cleaned_str.endswith("```"):
                        cleaned_str = cleaned_str[:-3]
                        
                    updated_slide_data = json.loads(cleaned_str)
                    updated_slide = SlideContent(**updated_slide_data)
                    updated_slides.append(updated_slide)
                except:
                    logger.error(f"Failed to parse slide response: {slide_response_str}")
                    updated_slides.append(slide) # Keep original if failed

            outline.slides = updated_slides

            # 4. Build PPT (Call Builder Agent)
            yield self.format_response("Step 3: Building PPT File...", is_complete=False)
            
            builder_card = await self._find_agent_by_task("Build PowerPoint file")
            
            build_response_str = await self._call_agent(builder_card, outline.model_dump_json())
            
            yield self.format_response(f"Project Complete! {build_response_str}")

        except Exception as e:
            logger.error(f"Orchestration error: {e}")
            logger.error(traceback.format_exc())
            yield self.format_response(f"Error: {e}")

    def get_agent_card(self, host: str, port: int) -> AgentCard:
        card = super().get_agent_card(host, port)
        card.skills = [
            {
                "id": "generate_ppt",
                "name": "Generate PPT",
                "description": "Generates a complete PPT file from a topic",
                "tags": ["ppt", "presentation", "generator"],
                "examples": ["Create a 5-slide presentation about AI trends"]
            }
        ]
        return card

if __name__ == "__main__":
    import click
    from ai_ppt.common.server_utils import start_agent_server
    
    @click.command()
    @click.option("--host", default="localhost")
    @click.option("--port", default=10200)
    def main(host, port):
        agent = OrchestratorAgent()
        start_agent_server(agent, host, port)
        
    main()