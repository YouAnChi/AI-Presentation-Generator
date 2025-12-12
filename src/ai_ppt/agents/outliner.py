"""大纲策划（Outliner）智能体：将输入的主题解析为结构化的演示文稿大纲。

核心职责：
- 使用 Gemini 模型根据主题与风格生成 `PresentationOutline`；
- 对输入进行容错解析（支持纯文本或 JSON）；
- 以流式接口返回结构化结果，便于上游编排器消费。

实现要点：
- 通过 `ChatPromptTemplate` 设定输出规范，并用 `with_structured_output(PresentationOutline)` 强制结构化；
- 简化解析逻辑：纯文本输入视为主题，JSON 输入按 `PPTGenerationRequest` 字段解析；
- 所有输出统一使用 `self.format_response(...)` 封装，保持 A2A 协议一致性。
"""

import json
import logging
from dotenv import load_dotenv
from typing import AsyncIterable, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from ai_ppt.common.types import PresentationOutline, PPTGenerationRequest
from ai_ppt.common.utils import get_logger, init_api_key
from ai_ppt.common.base_agent import BaseAgent
from a2a.types import AgentCard

# 自动加载 .env 文件，确保环境变量（如 API Key）可用
load_dotenv()

logger = get_logger(__name__)

class OutlinerAgent(BaseAgent):
    """大纲策划智能体：负责把主题转换为结构化大纲。"""
    def __init__(self):
        super().__init__(
            agent_name="PPT Outliner",
            description="Creates structured outlines for presentations."
        )
        # 验证外部模型所需的 API Key 是否存在
        init_api_key()
        # 初始化 LLM（Gemini）与推理参数
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
        # 定义提示模板：约定输出结构与字段
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
        # 通过 LangChain 的结构化输出能力，确保返回符合 `PresentationOutline` 模型
        self.chain = self.prompt | self.llm.with_structured_output(PresentationOutline)

    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[dict[str, Any]]:
        """流式生成大纲。

        参数：
            query: 主题或包含更多参数的 JSON 字符串。
            context_id: 会话上下文标识。
            task_id: 任务标识。

        返回：
            通过 `yield` 返回结构化字典（Pydantic 模型 `model_dump()`），或错误文本。
        """
        logger.info(f"Received request: {query}")
        
        # 简单解析输入：优先解析 JSON，其次纯文本作为主题
        # 真实场景可使用 LLM 解析复杂命令，或直接约定统一 JSON 输入
        try:
            if query.startswith("{"):
                request_data = json.loads(query)
                request = PPTGenerationRequest(**request_data)
            else:
                # 纯文本回退：仅设置主题，其他参数使用默认值
                request = PPTGenerationRequest(topic=query)
        except Exception as e:
            logger.error(f"Failed to parse query: {e}")
            yield self.format_response(f"Error: Could not parse request. {e}")
            return

        try:
            logger.info(f"Generating outline for topic: {request.topic}")
            # 调用结构化链，返回符合 `PresentationOutline` 的对象
            outline = self.chain.invoke({
                "topic": request.topic,
                "num_slides": request.num_slides,
                "style": request.style
            })
            logger.info("Outline generated successfully")
            
            # 返回结果：转换为字典便于 JSON 序列化
            yield self.format_response(outline.model_dump())
            
        except Exception as e:
            logger.error(f"Error generating outline: {e}")
            yield self.format_response(f"Error: {e}")

    def get_agent_card(self, host: str, port: int) -> AgentCard:
        """生成当前智能体的 AgentCard，并声明其工具与标签。"""
        card = super().get_agent_card(host, port)
        card.skills = [
            {
                "id": "create_outline",
                "name": "Create Outline",
                "description": "根据给定的主题生成结构化的演示文稿大纲（包含标题、布局等）",
                "tags": ["outline", "planning", "大纲", "策划"]
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
        # 启动 Outliner 的 A2A 服务端
        agent = OutlinerAgent()
        start_agent_server(agent, host, port)
        
    main()
