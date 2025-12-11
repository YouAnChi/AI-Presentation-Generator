import os
import json
import logging
from typing import AsyncIterable, Any
from pptx import Presentation
from ai_ppt.common.types import PresentationOutline
from ai_ppt.common.utils import get_logger
from ai_ppt.common.base_agent import BaseAgent
from a2a.types import AgentCard

logger = get_logger(__name__)

class BuilderAgent(BaseAgent):
    def __init__(self, output_dir: str = "output"):
        super().__init__(
            agent_name="PPT Builder",
            description="Compiles content into a final PowerPoint file."
        )
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def build_presentation(self, outline: PresentationOutline, filename: str = "presentation.pptx") -> str:
        logger.info(f"Building presentation: {outline.topic}")
        prs = Presentation()
        
        for slide_content in outline.slides:
            # Simple layout mapping
            if "Title Slide" in slide_content.layout:
                layout_index = 0
            elif "Title and Content" in slide_content.layout:
                layout_index = 1
            elif "Section Header" in slide_content.layout:
                layout_index = 2
            elif "Two Content" in slide_content.layout:
                layout_index = 3
            else:
                layout_index = 1 
            
            slide_layout = prs.slide_layouts[layout_index]
            slide = prs.slides.add_slide(slide_layout)
            
            # Set Title
            if slide.shapes.title:
                slide.shapes.title.text = slide_content.title
            
            # Set Body Text
            if len(slide.placeholders) > 1 and slide_content.body_text:
                body_shape = slide.placeholders[1]
                if hasattr(body_shape, "text"):
                    body_shape.text = slide_content.body_text
            
            # Add Speaker Notes
            if slide_content.speaker_notes and slide.has_notes_slide:
                notes_slide = slide.notes_slide
                notes_slide.notes_text_frame.text = slide_content.speaker_notes

        output_path = os.path.join(self.output_dir, filename)
        prs.save(output_path)
        logger.info(f"Presentation saved to: {output_path}")
        return output_path

    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[dict[str, Any]]:
        logger.info(f"Received request to build PPT")
        
        try:
            # Expecting JSON string of PresentationOutline
            data = json.loads(query)
            outline = PresentationOutline(**data)
            
            output_path = self.build_presentation(outline)
            
            yield self.format_response(f"Presentation built successfully: {output_path}")
            
        except Exception as e:
            logger.error(f"Error building PPT: {e}")
            yield self.format_response(f"Error: {e}")

    def get_agent_card(self, host: str, port: int) -> AgentCard:
        card = super().get_agent_card(host, port)
        card.skills = [
            {
                "id": "build_ppt",
                "name": "Build PPT File",
                "description": "Generates a .pptx file from structured slide data",
                "tags": ["builder", "pptx"]
            }
        ]
        return card

if __name__ == "__main__":
    import click
    from ai_ppt.common.server_utils import start_agent_server
    
    @click.command()
    @click.option("--host", default="localhost")
    @click.option("--port", default=10203)
    def main(host, port):
        agent = BuilderAgent()
        start_agent_server(agent, host, port)
        
    main()
