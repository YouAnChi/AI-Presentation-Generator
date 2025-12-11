import json
import logging
from typing import AsyncIterable, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from ai_ppt.common.types import SlideContent
from ai_ppt.common.utils import get_logger, init_api_key
from ai_ppt.common.base_agent import BaseAgent
from a2a.types import AgentCard

logger = get_logger(__name__)

class CopywriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="PPT Copywriter",
            description="Writes engaging content and speaker notes for presentation slides."
        )
        init_api_key()
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
        self.prompt = ChatPromptTemplate.from_template(
            """
            You are a professional presentation copywriter. Your task is to write the content and speaker notes for a specific slide.
            
            Slide Title: {title}
            Slide Layout: {layout}
            Presentation Topic: {topic}
            
            1. Write concise, engaging body text (bullet points or short paragraphs) suitable for a presentation slide.
            2. Write detailed speaker notes that explain the points in depth.
            3. Suggest a prompt for an image generation model (like DALL-E or Midjourney) that would visually represent this slide.
            
            Return the result as a JSON object matching the SlideContent structure (updating body_text, speaker_notes, and image_prompt).
            """
        )
        self.chain = self.prompt | self.llm.with_structured_output(SlideContent)

    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[dict[str, Any]]:
        logger.info(f"Received request: {query}")
        
        try:
            # Expecting a JSON string containing slide data and topic
            data = json.loads(query)
            slide = SlideContent(**data["slide"])
            topic = data["topic"]
            
            logger.info(f"Generating content for slide: {slide.title}")
            
            # We pass the partial slide object to structured output to fill in the missing fields
            result = self.chain.invoke({
                "title": slide.title,
                "layout": slide.layout,
                "topic": topic
            })
            
            # Merge result back into original slide object
            slide.body_text = result.body_text
            slide.speaker_notes = result.speaker_notes
            slide.image_prompt = result.image_prompt
            
            logger.info("Content generated successfully")
            yield self.format_response(slide.model_dump())
            
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            yield self.format_response(f"Error: {e}")

    def get_agent_card(self, host: str, port: int) -> AgentCard:
        card = super().get_agent_card(host, port)
        card.skills = [
            {
                "id": "write_content",
                "name": "Write Slide Content",
                "description": "Writes body text and speaker notes for a specific slide title and layout",
                "tags": ["content", "copywriting"]
            }
        ]
        return card

if __name__ == "__main__":
    import click
    from ai_ppt.common.server_utils import start_agent_server
    
    @click.command()
    @click.option("--host", default="localhost")
    @click.option("--port", default=10202)
    def main(host, port):
        agent = CopywriterAgent()
        start_agent_server(agent, host, port)
        
    main()
