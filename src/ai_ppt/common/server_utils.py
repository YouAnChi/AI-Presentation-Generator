"""A2A 服务器启动工具：为任意 `BaseAgent` 创建并运行基于 Starlette 的 HTTP 服务。

核心职责：
- 将智能体的 `AgentCard` 与请求处理器装配到 `A2AStarletteApplication`；
- 配置内存任务存储与推送通知组件（可替换为持久化实现）；
- 使用 `uvicorn` 启动 HTTP 服务，监听指定主机与端口。

实现要点：
- `GenericAgentExecutor` 统一封装代理的执行入口；
- `DefaultRequestHandler` 负责 A2A 协议的请求-响应处理与任务管理；
- 推送通知相关组件可用于异步状态更新或进度通知。
"""

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
    """为指定智能体启动 Starlette HTTP 服务（A2A 协议）。

    参数：
        agent: 需要对外暴露的智能体实例。
        host: 监听地址，例如 `localhost`。
        port: 监听端口，例如 `10200`。
    """
    logger.info(f"Starting {agent.agent_name} on {host}:{port}")
    
    # 生成智能体名片，作为 A2A 服务的自描述信息
    agent_card = agent.get_agent_card(host, port)
    
    # 推送通知组件：用于异步向客户端发送状态更新（本示例使用内存实现）
    client = AsyncClient()
    push_notification_config_store = InMemoryPushNotificationConfigStore()
    push_notification_sender = BasePushNotificationSender(
        client, config_store=push_notification_config_store
    )

    # 默认请求处理器：负责将 HTTP 请求转换为智能体的执行调用
    request_handler = DefaultRequestHandler(
        agent_executor=GenericAgentExecutor(agent=agent),
        task_store=InMemoryTaskStore(),
        push_config_store=push_notification_config_store,
        push_sender=push_notification_sender,
    )

    # 组装 A2A Starlette 应用：绑定名片与请求处理器
    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )

    # 启动 Uvicorn 服务
    uvicorn.run(server.build(), host=host, port=port)
