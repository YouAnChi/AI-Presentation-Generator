import uvicorn
import logging
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a_mcp.common.agent_executor import GenericAgentExecutor
from httpx import AsyncClient
from ai_ppt.common.base_agent import BaseAgent

logger = logging.getLogger(__name__)

def start_agent_server(agent: BaseAgent, host: str, port: int):
    """Starts a Starlette server for the given agent."""
    logger.info(f"Starting {agent.agent_name} on {host}:{port}")
    
    agent_card = agent.get_agent_card(host, port)
    
    client = AsyncClient()
    push_notification_config_store = InMemoryPushNotificationConfigStore()
    push_notification_sender = BasePushNotificationSender(
        client, config_store=push_notification_config_store
    )

    request_handler = DefaultRequestHandler(
        agent_executor=GenericAgentExecutor(agent=agent),
        task_store=InMemoryTaskStore(),
        push_config_store=push_notification_config_store,
        push_sender=push_notification_sender,
    )

    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )

    uvicorn.run(server.build(), host=host, port=port)
