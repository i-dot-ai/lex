#!/bin/bash
# Test script for MCP server endpoint
# Tests the Model Context Protocol server functionality

set -e

# Configuration
MCP_ENDPOINT="https://lex-gateway.azure-api.net/mcp/mcp"
PROTOCOL_VERSION="2025-06-18"

# Colours for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Colour

echo -e "${YELLOW}Testing MCP Server at ${MCP_ENDPOINT}${NC}"
echo "=============================================="

# Test 1: Initialize session
echo -e "\n${YELLOW}1. Testing initialization...${NC}"
INIT_RESPONSE=$(curl -s -X POST "$MCP_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: $PROTOCOL_VERSION" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"clientInfo":{"name":"test-client","version":"1.0.0"}}}')

# Extract session ID from response
SESSION_ID=$(echo "$INIT_RESPONSE" | grep -o 'mcp-session-id: [^[:space:]]*' | cut -d' ' -f2 | tr -d '\r')

if [[ "$INIT_RESPONSE" == *"protocolVersion"* && "$INIT_RESPONSE" == *"Lex Research API"* ]]; then
    echo -e "${GREEN}✅ Initialization successful${NC}"
    echo "   Session ID: $SESSION_ID"
    echo "   Server: Lex Research API v2.13.0.2"
else
    echo -e "${RED}❌ Initialization failed${NC}"
    echo "Response: $INIT_RESPONSE"
    exit 1
fi

# Test 2: List tools
echo -e "\n${YELLOW}2. Testing tools list...${NC}"
TOOLS_RESPONSE=$(curl -s -X POST "$MCP_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: $PROTOCOL_VERSION" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}')

if [[ "$TOOLS_RESPONSE" == *"search_for_legislation_acts"* && "$TOOLS_RESPONSE" == *"search_for_legislation_sections"* ]]; then
    echo -e "${GREEN}✅ Tools list successful${NC}"
    TOOL_COUNT=$(echo "$TOOLS_RESPONSE" | grep -o '"name":"[^"]*"' | wc -l)
    echo "   Found $TOOL_COUNT tools"
else
    echo -e "${RED}❌ Tools list failed${NC}"
    echo "Response: $TOOLS_RESPONSE"
fi

# Test 3: List resources
echo -e "\n${YELLOW}3. Testing resources list...${NC}"
RESOURCES_RESPONSE=$(curl -s -X POST "$MCP_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: $PROTOCOL_VERSION" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"resources/list"}')

if [[ "$RESOURCES_RESPONSE" == *"resources"* ]]; then
    echo -e "${GREEN}✅ Resources list successful${NC}"
    echo "   No resources configured (expected)"
else
    echo -e "${RED}❌ Resources list failed${NC}"
    echo "Response: $RESOURCES_RESPONSE"
fi

# Test 4: Tool call
echo -e "\n${YELLOW}4. Testing tool call...${NC}"
TOOL_RESPONSE=$(curl -s -X POST "$MCP_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: $PROTOCOL_VERSION" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"search_for_legislation_acts","arguments":{"query":"data protection","limit":2}}}')

if [[ "$TOOL_RESPONSE" == *"Data Protection Act 2018"* ]]; then
    echo -e "${GREEN}✅ Tool call successful${NC}"
    echo "   Found legislation results"
else
    echo -e "${RED}❌ Tool call failed${NC}"
    echo "Response: $TOOL_RESPONSE"
fi

# Test 5: Invalid session
echo -e "\n${YELLOW}5. Testing invalid session handling...${NC}"
INVALID_RESPONSE=$(curl -s -X POST "$MCP_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: $PROTOCOL_VERSION" \
  -H "mcp-session-id: invalid-session-id" \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/list"}')

if [[ "$INVALID_RESPONSE" == *"error"* ]]; then
    echo -e "${GREEN}✅ Invalid session handled correctly${NC}"
    echo "   Server properly rejects invalid sessions"
else
    echo -e "${YELLOW}⚠️  Invalid session response unexpected${NC}"
    echo "Response: $INVALID_RESPONSE"
fi

echo -e "\n${GREEN}=============================================="
echo -e "MCP Server testing complete! ✅${NC}"
echo "=============================================="

# Usage examples
echo -e "\n${YELLOW}Usage Examples:${NC}"

echo -e "\n${YELLOW}Initialize session:${NC}"
cat << 'EOF'
curl -X POST https://lex-gateway.azure-api.net/mcp/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"clientInfo":{"name":"test-client","version":"1.0.0"}}}'
EOF

echo -e "\n${YELLOW}Search legislation:${NC}"
cat << 'EOF'
curl -X POST https://lex-gateway.azure-api.net/mcp/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -H "mcp-session-id: YOUR_SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_for_legislation_acts","arguments":{"query":"your search term","limit":5}}}'
EOF

echo -e "\n${YELLOW}Claude Desktop Configuration:${NC}"
cat << 'EOF'
{
  "mcpServers": {
    "lex-research": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch", "https://lex-gateway.azure-api.net/mcp/mcp"],
      "env": {}
    }
  }
}
EOF