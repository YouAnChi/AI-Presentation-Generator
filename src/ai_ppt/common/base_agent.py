"""A2A 智能体基类：统一封装智能体的名片生成、流式接口约定与响应格式。

核心职责：
- 约定所有智能体必须实现异步 `stream` 方法，支持流式返回；
- 统一生成 `AgentCard`（智能体名片），声明能力与输入输出模式；
- 提供 `format_response`，将任意内容格式化为 A2A 流式消息结构。

使用说明：
- 子类需实现 `stream(query, context_id, task_id)`，并通过 `yield` 返回格式化消息；
- 可在子类中覆盖 `get_agent_card` 以添加技能（skills）等信息；
- `format_response` 会把 `dict`/`list` 自动转为 JSON 字符串，其余类型转为 `str`。
"""

import json
import logging
from abc import abstractmethod
from typing import AsyncIterable, Any

from a2a.types import AgentCard
from ai_ppt.common.utils import get_logger

logger = get_logger(__name__)

class BaseAgent:
    """所有 A2A 智能体的基类。"""

    def __init__(
        self,
        agent_name: str,
        description: str,
        content_types: list[str] | None = None,
    ):
        self.agent_name = agent_name
        self.description = description
        self.content_types = content_types or ['text', 'text/plain']

    @abstractmethod
    async def stream(
        self, query: str, context_id: str, task_id: str
    ) -> AsyncIterable[dict[str, Any]]:
        """智能体的流式接口：根据输入异步生成结果并逐步返回。

        参数：
            query: 输入的查询/指令文本或 JSON。
            context_id: 会话上下文标识，用于链路追踪。
            task_id: 任务标识，用于链路追踪。

        返回：
            异步可迭代的字典对象，每个元素代表一次流式输出。
        """
        pass

    def get_agent_card(self, host: str, port: int) -> AgentCard:
        """生成当前智能体的名片（AgentCard）。

        名片包含：名称、描述、版本、URL、能力声明、默认输入输出模式与技能列表。
        子类可在返回后追加或修改 `skills`，用于外部发现与调用。
        """
        return AgentCard(
            name=self.agent_name,
            description=self.description,
            version="1.0.0",
            url=f"http://{host}:{port}/",
            capabilities={
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": False,
            },
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            skills=[],  # Skills should be loaded from config or defined in subclass
        )

    def format_response(self, content: Any, is_complete: bool = True) -> dict[str, Any]:
        """将内容格式化为 A2A 流式响应字典。

        行为：
        - 若 `content` 为 `dict` 或 `list`，尝试序列化为 JSON 字符串；失败则退回 `str(content)`。
        - 其他类型直接转为字符串。
        - 统一返回字段包括：`response_type`、`is_task_complete`、`require_user_input`、`content`。
        """
        if isinstance(content, dict) or isinstance(content, list):
             try:
                 content_str = json.dumps(content)
             except:
                 content_str = str(content)
        else:
             content_str = str(content)
             
        return {
            'response_type': 'text',
            'is_task_complete': is_complete,
            'require_user_input': False,
            'content': content_str,
        }
