import os
from a2a_mcp.mcp import server
# Patch the AGENT_CARDS_DIR
server.AGENT_CARDS_DIR = 'agent_cards'
if __name__ == '__main__':
    server.serve('localhost', 10100, 'sse')
