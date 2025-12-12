"""编排器（Orchestrator）智能体：基于 MCP 进行代理发现，基于 A2A 进行代理调用，
以串行管线的方式完成从主题到最终 PPT 的自动化生成。

核心职责：
- 通过 MCP 根据任务描述查找合适的外部代理（大纲/文案/图片/构建）；
- 通过 A2A 协议以统一消息结构调用代理，并容错解析响应；
- 将完整流程拆分为四个阶段：规划大纲、生成文案、生成图片、构建 PPT；
- 在流式接口中逐步输出过程状态，便于客户端实时展示进度。

重要约束与约定：
- 本示例采用“单流程、串行”执行，不做并发与重试；
- 响应解析优先读取 `Task.artifacts` 的文本，其次回退到 `status.message` 或 `Message.parts`；
- 因为各代理可能返回自由文本或包含 Markdown 三引号包裹的 JSON，解析前会做清洗；
- 若图片生成失败不会中止流程，构建阶段仍可继续执行。
"""

import json
import uuid
import logging
import traceback
from dotenv import load_dotenv
from typing import AsyncIterable, Any
from a2a.types import AgentCard, SendMessageRequest, MessageSendParams, Message, Role, TextPart, Task
from ai_ppt.common.types import PresentationOutline, PPTGenerationRequest, SlideContent
from ai_ppt.common.utils import get_logger, init_api_key
from ai_ppt.common.base_agent import BaseAgent
from a2a.client import A2AClient
from a2a_mcp.mcp import client as mcp_client
from a2a_mcp.common.utils import get_mcp_server_config
import httpx
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 自动加载 .env 文件，确保环境变量（如 API Key）可用
load_dotenv()

logger = get_logger(__name__)

class OrchestratorAgent(BaseAgent):
    """项目经理（编排器）智能体。

    作用：
    - 对外作为 A2A 代理暴露服务与技能卡片；
    - 对内根据任务需求串联多个下游代理完成端到端生成；
    - 统一日志、错误处理与响应格式。
    """
    def __init__(self):
        super().__init__(
            agent_name="PPT Project Manager",
            description="Manages the end-to-end process of generating a PowerPoint presentation based on a user topic."
        )
        # 初始化外部模型所需的 API Key（如 Google Gemini），无则直接抛错。
        init_api_key()
        
        # 初始化 LLM 用于动态决策
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
        self.planner_prompt = ChatPromptTemplate.from_template(
            """
            你是一个 AI 演示文稿生成团队的项目经理（Orchestrator）。
            你的目标是从工具目录中找到最合适的 Agent 来完成特定的子任务。
            
            当前子任务目标: {goal}
            
            请写一个简短、精准的搜索查询（1句话）来寻找能够完成此目标的 Agent。
            请使用中文进行搜索，并包含核心关键词（例如：大纲、文案、图片、构建）。
            不要提及具体的 Agent 名称（如 "Outliner"），请描述该 Agent 应该具备的功能。
            请直接输出查询语句，不要包含其他解释。
            
            搜索查询:
            """
        )
        self.planner_chain = self.planner_prompt | self.llm | StrOutputParser()

    async def _decide_agent_search_query(self, goal: str) -> str:
        """利用 LLM 根据当前目标生成最佳的 Agent 搜索查询。"""
        try:
            logger.info(f"【智能决策】正在思考如何寻找合适的帮手，目标任务：{goal}")
            query = await self.planner_chain.ainvoke({"goal": goal})
            cleaned_query = query.strip()
            logger.info(f"【智能决策】思考完毕，决定搜索关键词：\"{cleaned_query}\"")
            return cleaned_query
        except Exception as e:
            logger.warning(f"【智能决策】思考失败，将使用原始目标作为兜底：{e}")
            return goal  # Fallback to the goal itself

    async def _find_agent_by_task(self, task_description: str) -> AgentCard:
        """通过 MCP 根据任务描述发现并返回合适的代理名片（AgentCard）。

        参数：
            task_description: 对下游能力的自然语言描述，例如“Create a presentation outline”。

        返回：
            AgentCard：包含代理的基础信息、地址、能力声明等。
        """
        logger.info(f"【寻找帮手】正在 MCP 市场中检索能力匹配的 Agent，搜索描述：\"{task_description}\"")
        # 从统一配置获取 MCP Server 的连接信息（主机/端口/传输方式）
        config = get_mcp_server_config()
        
        # 建立到 MCP Server 的会话，并调用 find_agent 进行匹配搜索
        # 提示：生产环境请将端口与传输方式改为可配置，避免硬编码。
        async with mcp_client.init_session(config.host, config.port, config.transport) as session:
            result = await mcp_client.find_agent(session, task_description)
            # MCP 返回的 content 为 TextContent 列表，这里取第一项并反序列化为 JSON
            agent_card_json = json.loads(result.content[0].text)
            logger.info(f"【寻找帮手】找到最匹配的 Agent：{agent_card_json['name']} (URL: {agent_card_json['url']})")
            return AgentCard(**agent_card_json)

    async def _call_agent(self, agent_card: AgentCard, query: str) -> str:
        """使用 A2A 协议调用远程代理，并尽可能提取文本结果。

        参数：
            agent_card: 被调用代理的名片（包含 URL、能力等）。
            query: 发送给代理的请求文本或 JSON 字符串。

        返回：
            str：优先返回 `artifacts` 中的文本，其次回退到 `status.message` 或普通 `Message` 的文本；
                 如无法解析则返回响应对象的字符串表示，异常时返回 `Error: ...`。
        """
        logger.info(f"【任务委派】正在呼叫 \"{agent_card.name}\" 执行任务...")
        
        try:
            # 为可能较耗时的生成任务设置更长的网络超时时间
            async with httpx.AsyncClient(timeout=200.0) as httpx_client:
                client = A2AClient(httpx_client, agent_card)
                
                # 发送非流式消息并等待单次响应
                # 简化处理：此处不处理流式分片，实际应用可改为流式接口
                
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
                
                # 解析响应：按照 artifacts -> status -> message 的优先级提取文本
                if hasattr(response, 'root') and hasattr(response.root, 'result'):
                    result = response.root.result
                    
                    # 情况 1：Task 类型，且包含 artifacts（优先使用，通常为真实产出）
                    if isinstance(result, Task) or (hasattr(result, 'artifacts') and result.artifacts):
                        if result.artifacts:
                            # 倒序遍历，寻找首个包含文本的工件（避免前序为空或非文本）
                            for artifact in reversed(result.artifacts):
                                if artifact.parts:
                                    part = artifact.parts[0]
                                    # 兼容不同字段位置：part.root.text 或 part.text
                                    if hasattr(part, 'root') and part.root and hasattr(part.root, 'text') and part.root.text:
                                        return part.root.text
                                    elif hasattr(part, 'text') and part.text:
                                        return part.text
                    
                    # 情况 2：Task 类型，使用状态消息作为回退（当 artifacts 不可用时）
                    if hasattr(result, 'status') and result.status and result.status.message and result.status.message.parts:
                        part = result.status.message.parts[0]
                        if hasattr(part, 'root') and part.root and hasattr(part.root, 'text'):
                            return part.root.text
                        elif hasattr(part, 'text'):
                            return part.text
                            
                    # 情况 3：普通 Message 类型，直接读取 parts 文本
                    if isinstance(result, Message) and result.parts:
                        part = result.parts[0]
                        if hasattr(part, 'root') and hasattr(part.root, 'text'):
                            return part.root.text
                        elif hasattr(part, 'text'):
                            return part.text

                # 兜底：无法识别结构，返回响应的字符串表示
                return str(response)
        except Exception as e:
            # 增强错误日志：包含堆栈与异常组（Python 3.11+）的子异常信息
            error_msg = f"【任务异常】呼叫 \"{agent_card.name}\" 失败：{e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            # 如果是 ExceptionGroup，逐条打印子异常便于定位问题
            if hasattr(e, 'exceptions'):
                for i, sub_exc in enumerate(e.exceptions):
                    logger.error(f"子异常 {i+1}: {sub_exc}")
            
            return f"Error: {e}"

    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[dict[str, Any]]:
        """以流式方式编排整个 PPT 生成流程，并逐步输出状态消息。

        参数：
            query: 用户输入的主题（或包含更多参数的文本）。
            context_id: 会话上下文标识（用于链路追踪）。
            task_id: 本次任务标识（用于链路追踪）。

        返回：
            AsyncIterable[dict[str, Any]]：通过 `yield` 逐步返回格式化的状态消息，
            最终返回构建阶段的结果文本（文件路径或描述）。
        """
        logger.info(f"【收到请求】开始处理 PPT 生成项目，主题：\"{query}\"")
        
        try:
            # 1. 解析输入请求
            # 这里采用简单启发：将原始 query 直接作为主题
            topic = query
            request = PPTGenerationRequest(topic=topic)
            
            yield self.format_response(f"【项目启动】开始处理 PPT 生成项目，主题：\"{topic}\"", is_complete=False)

            # 2. 规划大纲（调用 Outliner 代理）
            yield self.format_response("【流程进度】第 1 步：规划大纲...", is_complete=False)
            
            # 动态决策：寻找负责大纲的代理
            search_query = await self._decide_agent_search_query("我需要为演示文稿生成一个结构化的大纲。")
            outliner_card = await self._find_agent_by_task(search_query)
            
            # 将生成请求序列化为 JSON 字符串发送给大纲代理
            outliner_response_str = await self._call_agent(outliner_card, request.model_dump_json())
            
            # 解析响应（约定返回 PresentationOutline 的 JSON 字符串）
            try:
                # 清洗可能的 Markdown 包裹（```json ... ```）
                cleaned_str = outliner_response_str.strip()
                if cleaned_str.startswith("```json"):
                    cleaned_str = cleaned_str[7:]
                if cleaned_str.endswith("```"):
                    cleaned_str = cleaned_str[:-3]
                
                # 如果返回以 Error: 开头，则视为失败并中止流程
                if cleaned_str.startswith("Error:"):
                     yield self.format_response(f"Outliner Agent Failed: {cleaned_str}")
                     return

                outline_data = json.loads(cleaned_str)
                outline = PresentationOutline(**outline_data)
                yield self.format_response(f"【大纲就绪】已生成 {len(outline.slides)} 页大纲。", is_complete=False)
            except (json.JSONDecodeError, Exception) as e:
                 # 大纲代理返回非预期文本或解析失败，直接输出原文并结束
                 yield self.format_response(f"Error from Outliner: {outliner_response_str}")
                 return

            # 3. 生成文案（循环调用 Copywriter 代理）
            yield self.format_response("【流程进度】第 2 步：生成文案...", is_complete=False)
            
            # 动态决策：寻找负责写文案的代理
            search_query = await self._decide_agent_search_query("我需要为每张幻灯片编写详细的正文内容和演讲者备注。")
            copywriter_card = await self._find_agent_by_task(search_query)
            
            updated_slides = []
            for i, slide in enumerate(outline.slides):
                yield self.format_response(f"正在撰写第 {i+1}/{len(outline.slides)} 页文案：{slide.title}...", is_complete=False)
                
                # 为文案代理准备负载：包含当前幻灯片结构与主题
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
                    # 单页解析失败：保留原始幻灯片内容，避免中断整体流程
                    logger.error(f"【解析失败】无法解析幻灯片响应：{slide_response_str}")
                    updated_slides.append(slide)

            outline.slides = updated_slides

            # 3. 生成图片（调用 Image Generator 代理）
            yield self.format_response("【流程进度】第 3 步：生成图片...", is_complete=False)
            
            try:
                # 动态决策：寻找负责生成图片的代理
                search_query = await self._decide_agent_search_query("我需要根据文本提示词生成图片文件。")
                image_gen_card = await self._find_agent_by_task(search_query)
                
                slides_with_images = []
                for i, slide in enumerate(outline.slides):
                    if slide.image_prompt:
                        yield self.format_response(f"正在生成第 {i+1}/{len(outline.slides)} 页配图...", is_complete=False)
                        
                        payload = {
                            "prompt": slide.image_prompt,
                            "title": slide.title
                        }
                        
                        image_response_str = await self._call_agent(image_gen_card, json.dumps(payload))
                        
                        try:
                            # 约定解析：返回结构中包含 `image_path`
                            cleaned_str = image_response_str.strip()
                            if cleaned_str.startswith("```json"):
                                cleaned_str = cleaned_str[7:]
                            if cleaned_str.endswith("```"):
                                cleaned_str = cleaned_str[:-3]
                                
                            image_data = json.loads(cleaned_str)
                            if "image_path" in image_data:
                                slide.image_path = image_data["image_path"]
                        except Exception as e:
                            # 图片生成失败：记录错误但不影响后续流程
                            logger.error(f"【图片生成失败】幻灯片 \"{slide.title}\" 配图生成出错：{e}")
                        
                    slides_with_images.append(slide)
                
                outline.slides = slides_with_images
                
            except Exception as e:
                # 图片阶段整体失败：记录告警并继续进入构建阶段
                logger.warning(f"【跳过图片】图片生成阶段异常或跳过：{e}")
                pass

            # 4. 构建 PPT 文件（调用 Builder 代理）
            yield self.format_response("【流程进度】第 4 步：构建最终文件...", is_complete=False)
            
            # 动态决策：寻找负责构建最终文件的代理
            search_query = await self._decide_agent_search_query("我需要将所有幻灯片数据编译成一个 .pptx 文件。")
            builder_card = await self._find_agent_by_task(search_query)
            
            build_response_str = await self._call_agent(builder_card, outline.model_dump_json())
            
            yield self.format_response(f"【项目完成】PPT 生成完毕！ {build_response_str}")

        except Exception as e:
            # 顶层异常捕获：输出详细堆栈并以错误消息收尾
            logger.error(f"【编排异常】Orchestrator error: {e}")
            logger.error(traceback.format_exc())
            yield self.format_response(f"Error: {e}")

    def get_agent_card(self, host: str, port: int) -> AgentCard:
        """生成当前编排器的 AgentCard，并补充技能声明以便外部发现与调用。"""
        card = super().get_agent_card(host, port)
        card.skills = [
            {
                "id": "generate_ppt",
                "name": "Generate PPT",
                "description": "根据主题生成完整的 PPT 文件",
                "tags": ["ppt", "presentation", "generator"],
                "examples": ["创建一个关于 AI 趋势的 5 页演示文稿"]
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
        # 启动编排器的 A2A 服务端，供外部客户端或其他代理调用
        agent = OrchestratorAgent()
        start_agent_server(agent, host, port)
        
    main()
