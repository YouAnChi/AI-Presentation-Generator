"""文案撰写（Copywriter）智能体：根据单页标题与布局生成正文、演讲备注与图片提示。

核心职责：
- 使用 Gemini 模型补全 `SlideContent` 的文本字段与 `image_prompt`；
- 输入约定为包含 `slide` 与 `topic` 的 JSON 字符串；
- 以流式接口返回结构化结果，便于编排器更新每页内容。

实现要点：
- 使用 `with_structured_output(SlideContent)` 强制返回结构化对象；
- 将生成结果合并回原有 `SlideContent`，保持其他字段不变；
- 错误时返回友好文本，不中断上游编排流程。
"""

import json
import logging
from dotenv import load_dotenv
from typing import AsyncIterable, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from ai_ppt.common.types import SlideContent
from ai_ppt.common.utils import get_logger, init_api_key
from ai_ppt.common.base_agent import BaseAgent
from a2a.types import AgentCard

# 自动加载 .env 文件，确保环境变量（如 API Key）可用
load_dotenv()

logger = get_logger(__name__)

class CopywriterAgent(BaseAgent):
    """文案撰写智能体：负责单页正文与备注的生成。"""
    def __init__(self):
        super().__init__(
            agent_name="PPT Copywriter",
            description="Writes engaging content and speaker notes for presentation slides."
        )
        # 验证外部模型所需的 API Key
        init_api_key()
        # 初始化 LLM（Gemini）与推理参数
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
        # 定义提示模板，约束输出结构与风格
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
        # 通过结构化输出强制返回 `SlideContent` 模型
        self.chain = self.prompt | self.llm.with_structured_output(SlideContent)

    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[dict[str, Any]]:
        """流式生成单页文案。

        参数：
            query: JSON 字符串，包含 `slide`（部分字段已填）与 `topic`。
            context_id: 会话上下文标识。
            task_id: 任务标识。

        返回：
            通过 `yield` 返回合并后的 `SlideContent` 字典，或错误文本。
        """
        logger.info(f"Received request: {query}")
        
        try:
            # 预期输入为 JSON：包含原始 `slide` 与 `topic`
            data = json.loads(query)
            slide = SlideContent(**data["slide"])
            topic = data["topic"]
            
            logger.info(f"Generating content for slide: {slide.title}")
            
            # 传入标题/布局/主题，生成缺失字段（正文/备注/图片提示）
            result = self.chain.invoke({
                "title": slide.title,
                "layout": slide.layout,
                "topic": topic
            })
            
            # 将生成结果合并回原始 `SlideContent`
            slide.body_text = result.body_text
            slide.speaker_notes = result.speaker_notes
            slide.image_prompt = result.image_prompt
            
            logger.info("Content generated successfully")
            yield self.format_response(slide.model_dump())
            
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            yield self.format_response(f"Error: {e}")

    def get_agent_card(self, host: str, port: int) -> AgentCard:
        """生成当前智能体的 AgentCard，并声明其工具与标签。"""
        card = super().get_agent_card(host, port)
        card.skills = [
            {
                "id": "write_content",
                "name": "Write Slide Content",
                "description": "根据给定的标题和布局，为单张幻灯片撰写正文文本和演讲备注",
                "tags": ["content", "copywriting", "文案", "写作"]
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
        # 启动 Copywriter 的 A2A 服务端
        agent = CopywriterAgent()
        start_agent_server(agent, host, port)
        
    main()
