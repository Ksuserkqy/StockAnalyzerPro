import requests
import uuid
import os
from dotenv import load_dotenv; load_dotenv()

MCP_URL = "https://data-api.investoday.net/data/mcp/preset"
API_KEY = os.environ.get('STOCK_MCP_API_KEY')

def call(method: str, params: dict):
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{MCP_URL}?apiKey={API_KEY}",
        json=payload,
        headers=headers,
        timeout=60
    )

    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"MCP error: {data['error']}")
    return data

def mcp_to_openai_tool(mcp_tool):
    return {
        "type": "function",
        "function": {
            "name": mcp_tool["name"],
            "description": mcp_tool.get("description"),
            "parameters": mcp_tool.get("inputSchema")
        },
    }

def tool_list():
    data = call("tools/list", {})
    mcp_tools = data.get("result", []).get("tools", [])
    return [mcp_to_openai_tool(t) for t in mcp_tools]

def tool_call(name, arguments):
    return call(
        "tools/call",
        {
            "name": name,
            "arguments": arguments
        }
    )

if __name__ == "__main__":
    print(tool_list())
    print(tool_call("get_stock_quote_realtime", {"stockCode": "600519"}))