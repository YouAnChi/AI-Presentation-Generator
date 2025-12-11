from pydantic import BaseModel, Field
from typing import List, Optional

class SlideContent(BaseModel):
    """Represents the content of a single PPT slide."""
    page_number: int = Field(description="The page number of the slide")
    title: str = Field(description="The title of the slide")
    layout: str = Field(description="The layout of the slide (e.g., 'Title Slide', 'Title and Content')", default="Title and Content")
    body_text: Optional[str] = Field(description="The main content/bullet points of the slide", default=None)
    speaker_notes: Optional[str] = Field(description="Notes for the speaker", default=None)
    image_prompt: Optional[str] = Field(description="Prompt to generate an image for this slide", default=None)
    image_path: Optional[str] = Field(description="Local path to the generated image", default=None)

class PresentationOutline(BaseModel):
    """Represents the complete outline of a presentation."""
    topic: str = Field(description="The main topic of the presentation")
    slides: List[SlideContent] = Field(description="List of slides in the presentation")

class PPTGenerationRequest(BaseModel):
    """Request object for generating a PPT."""
    topic: str
    num_slides: int = 5
    style: str = "professional"
