#!/usr/bin/env python3
"""Mock MCP server for testing.

Implements a minimal MCP server that responds to initialize, tools/list,
and tools/call over stdio JSON-RPC. Used by the MCP manager tests.
"""

import json
import sys


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method", "")
        req_id = req.get("id")

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mock-mcp", "version": "1.0.0"},
                },
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass  # notification, no response

        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "mock_tool_1",
                            "description": "Mock tool 1",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                        {
                            "name": "mock_tool_2",
                            "description": "Mock tool 2",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                    ]
                },
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = req.get("params", {}).get("name", "")
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": f"Mock result for {tool_name}"}]},
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
