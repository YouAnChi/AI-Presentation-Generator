import json
import logging
from typing import AsyncIterable, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from ai_ppt.common.types import PresentationOutline, PPTGenerationRequest
from ai_ppt.common.utils import get_logger, init_api_key
from ai_ppt.common.base_agent import BaseAgent
from a2a.types import AgentCard

logger = get_logger(__name__)

class OutlinerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="PPT Outliner",
            description="Creates structured outlines for presentations."
        )
        init_api_key()
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
        self.prompt = ChatPromptTemplate.from_template(
            """
            You are an expert presentation outliner. Your task is to create a structured outline for a presentation based on the given topic.
            
            Topic: {topic}
            Number of Slides: {num_slides}
            Style: {style}
            
            Create a detailed outline with {num_slides} slides. 
            For each slide, provide:
            1. A catchy Title
            2. A layout type (Title Slide, Title and Content, Section Header, Two Content)
            
            Return the result as a JSON object matching the PresentationOutline structure.
            """
        )
        self.chain = self.prompt | self.llm.with_structured_output(PresentationOutline)

    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[dict[str, Any]]:
        logger.info(f"Received request: {query}")
        
        # Simple parsing of the query to extract request parameters
        # In a real scenario, we might use an LLM to parse the query or expect a JSON string
        try:
            if query.startswith("{"):
                request_data = json.loads(query)
                request = PPTGenerationRequest(**request_data)
            else:
                # Fallback for plain text
                request = PPTGenerationRequest(topic=query)
        except Exception as e:
            logger.error(f"Failed to parse query: {e}")
            yield self.format_response(f"Error: Could not parse request. {e}")
            return

        try:
            logger.info(f"Generating outline for topic: {request.topic}")
            outline = self.chain.invoke({
                "topic": request.topic,
                "num_slides": request.num_slides,
                "style": request.style
            })
            logger.info("Outline generated successfully")
            
            # Return the result
            # We convert Pydantic model to dict for JSON serialization
            yield self.format_response(outline.model_dump())
            
        except Exception as e:
            logger.error(f"Error generating outline: {e}")
            yield self.format_response(f"Error: {e}")

    def get_agent_card(self, host: str, port: int) -> AgentCard:
        card = super().get_agent_card(host, port)
        card.skills = [
            {
                "id": "create_outline",
                "name": "Create Outline",
                "description": "Generates a structured outline (titles, layouts) for a given topic",
                "tags": ["outline", "planning"]
            }
        ]
        return card

if __name__ == "__main__":
    import click
    from ai_ppt.common.server_utils import start_agent_server
    
    @click.command()
    @click.option("--host", default="localhost")
    @click.option("--port", default=10201)
    def main(host, port):
        agent = OutlinerAgent()
        start_agent_server(agent, host, port)
        
    main()
