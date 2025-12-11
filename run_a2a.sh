#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "Error: .env file not found. Please create one from .env.example"
    exit 1
fi

echo "Setting up environment..."
uv venv --allow-existing
source .venv/bin/activate

# Install server dependencies if needed
# We assume 'uv pip install .' has been run with [server] extra or we run it now
# uv pip install .[server]

# Set PYTHONPATH
# We need to include:
# 1. The current project src (for ai_ppt)
# 2. The parent project src (for a2a_mcp module which we depend on)
PARENT_SRC=$(builtin cd "$(pwd)/../../../../src"; pwd)
export PYTHONPATH=$PYTHONPATH:$(pwd)/src:$PARENT_SRC

# Load .env file
set -a
source .env
set +a

# Cleanup function
cleanup() {
    echo "Shutting down all agents..."
    kill $(jobs -p) 2>/dev/null
}
trap cleanup EXIT

echo "Starting MCP Server (Port 10100)..."
# We reuse the existing MCP server logic but point it to our agent cards
# Note: We need to make sure the MCP server knows where to look for cards.
# For this demo, we might need to copy/link agent_cards to where mcp_server expects or run a local mcp server.
# Let's assume we run a local instance of the MCP server from this project.
# We will create a simple mcp server wrapper for this project.

# Create a temporary mcp server script that points to our agent_cards
cat > src/ai_ppt/mcp/a2a_mcp_server.py <<PY
import os
from a2a_mcp.mcp import server
# Patch the AGENT_CARDS_DIR
server.AGENT_CARDS_DIR = 'agent_cards'
if __name__ == '__main__':
    server.serve('localhost', 10100, 'sse')
PY

uv run src/ai_ppt/mcp/a2a_mcp_server.py &
MCP_PID=$!
sleep 2

echo "Starting Orchestrator Agent (Port 10200)..."
uv run src/ai_ppt/agents/orchestrator.py --port 10200 &
ORCH_PID=$!
sleep 2

echo "Starting Outliner Agent (Port 10201)..."
uv run src/ai_ppt/agents/outliner.py --port 10201 &
OUTLINER_PID=$!
sleep 2

echo "Starting Copywriter Agent (Port 10202)..."
uv run src/ai_ppt/agents/copywriter.py --port 10202 &
COPYWRITER_PID=$!
sleep 2

echo "Starting Builder Agent (Port 10203)..."
uv run src/ai_ppt/agents/builder.py --port 10203 &
BUILDER_PID=$!
sleep 2

echo "---------------------------------------------------------"
echo "All Agents Started. System Ready."
echo "---------------------------------------------------------"

echo "Enter your PPT topic (or press Enter for default):"
read -r topic

if [ -z "$topic" ]; then
    topic="The Future of Artificial Intelligence"
fi

# Now we use a simple client to call the Orchestrator via MCP
# But wait, our client.py was calling 'generate_ppt' tool on MCP.
# We need to update our MCP server to expose 'generate_ppt' which calls Orchestrator via A2A?
# OR we can just use the Orchestrator as the entry point.

# Let's update client.py to call the Orchestrator Agent directly via A2A Client for simplicity
# OR use the MCP 'find_agent' to get Orchestrator and then call it.

echo "Running Client..."
cat > src/ai_ppt/mcp/a2a_client.py <<PY
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
PY

uv run src/ai_ppt/mcp/a2a_client.py "$topic"

# Keep alive to see logs if needed, or exit
wait
