"""公共数据模型：描述 PPT 生成过程中的核心结构。

包含：
- `SlideContent`：单页幻灯片的内容结构；
- `PresentationOutline`：整份演示文稿的大纲结构；
- `PPTGenerationRequest`：生成请求的参数结构。
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class SlideContent(BaseModel):
    """单页幻灯片的内容结构。"""
    page_number: int = Field(description="页码")
    title: str = Field(description="幻灯片标题")
    layout: str = Field(description="幻灯片版式（如 'Title Slide'、'Title and Content'）", default="Title and Content")
    body_text: Optional[str] = Field(description="正文内容/要点列表", default=None)
    speaker_notes: Optional[str] = Field(description="演讲者备注", default=None)
    image_prompt: Optional[str] = Field(description="用于生成图片的提示词", default=None)
    image_path: Optional[str] = Field(description="生成图片的本地路径", default=None)


class PresentationOutline(BaseModel):
    """整份演示文稿的大纲结构。"""
    topic: str = Field(description="演示文稿的主题")
    slides: List[SlideContent] = Field(description="幻灯片列表")


class PPTGenerationRequest(BaseModel):
    """PPT 生成请求参数结构。"""
    topic: str
    num_slides: int = 5
    style: str = "professional"
