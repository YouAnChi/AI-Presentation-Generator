import json
import logging
from abc import abstractmethod
from typing import AsyncIterable, Any

from a2a.types import AgentCard
from ai_ppt.common.utils import get_logger

logger = get_logger(__name__)

class BaseAgent:
    """Base class for all A2A agents."""

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
        """Stream response from the agent."""
        pass

    def get_agent_card(self, host: str, port: int) -> AgentCard:
        """Generates the agent card for this agent."""
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
        """Formats the response for A2A stream."""
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
