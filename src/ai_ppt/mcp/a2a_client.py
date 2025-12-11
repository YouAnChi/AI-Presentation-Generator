import asyncio
import sys
import os
import json
import uuid
from a2a.client import A2AClient
from a2a.types import AgentCard, SendStreamingMessageRequest, MessageSendParams, Message, Role, TextPart
import httpx

async def run_client(topic):
    # We manually construct the Orchestrator card for this test client
    # In a real app, we would find it via MCP
    orch_card = AgentCard(
        name="PPT Project Manager",
        description="Manager",
        url="http://localhost:10200/",
        capabilities={"streaming": True},
        skills=[],
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"]
    )
    
    print(f"Connecting to Orchestrator at {orch_card.url}...")
    # Set a longer timeout for the client as well, as the entire generation process can take time
    async with httpx.AsyncClient(timeout=120.0) as httpx_client:
        client = A2AClient(httpx_client, orch_card)
        
        print(f"Sending request: {topic}")
        
        # Construct the proper request object
        msg_id = str(uuid.uuid4())
        request = SendStreamingMessageRequest(
            id=msg_id,
            params=MessageSendParams(
                message=Message(
                    message_id=msg_id,
                    role=Role.user,
                    parts=[TextPart(text=topic)]
                )
            )
        )
        
        stream = client.send_message_streaming(request)
        
        if hasattr(stream, '__aiter__'):
            async for chunk in stream:
                 try:
                     # 1. Try accessing nested text (legacy/specific structure)
                     if hasattr(chunk, 'root') and hasattr(chunk.root, 'result') and hasattr(chunk.root.result, 'status'):
                         status = chunk.root.result.status
                         if status.message and status.message.parts:
                             # Access text from TextPart (root.text)
                             part = status.message.parts[0]
                             if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                 print(part.root.text)
                             elif hasattr(part, 'text'):
                                 print(part.text)
                             continue

                     # 2. Try generic content access
                     if hasattr(chunk, 'content'):
                         print(chunk.content)
                     elif hasattr(chunk, 'root') and hasattr(chunk.root, 'content'):
                         print(chunk.root.content)
                     else:
                         # 3. Fallback: print string representation or dump
                         if hasattr(chunk, 'model_dump'):
                             # Filter out None values for cleaner output
                             dump = chunk.model_dump(exclude_none=True)
                             print(json.dumps(dump, default=str))
                         else:
                             print(str(chunk))
                 except Exception as e:
                     print(f"Error printing chunk: {e}")
        else:
            print(f"Stream object is not async iterable: {type(stream)}")

if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI"
    asyncio.run(run_client(topic))
