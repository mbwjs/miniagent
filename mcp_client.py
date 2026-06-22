#!/usr/bin/env python3
"""
Simple MCP client — talks to any MCP server over stdio JSON-RPC.
Usage: python3 mcp_client.py <server_cmd...>
"""

import subprocess
import json
import sys
import os
import signal


class MCPClient:
    def __init__(self, cmd: list[str], env: dict = None):
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged_env,
            text=True,
        )
        self._request_id = 0
        self._tools = None

    def _rpc(self, method: str, params: dict = None) -> dict:
        self._request_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        payload = json.dumps(req) + "\n"
        self.proc.stdin.write(payload)
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            stderr_output = self.proc.stderr.read()
            raise RuntimeError(f"Server closed stdout. stderr: {stderr_output}")
        return json.loads(line)

    def initialize(self):
        result = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "miniagent", "version": "1.0"},
        })
        # Send initialized notification
        self.proc.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }) + "\n")
        self.proc.stdin.flush()
        return result

    def list_tools(self) -> list[dict]:
        result = self._rpc("tools/list")
        self._tools = result.get("result", {}).get("tools", [])
        return self._tools

    def call_tool(self, name: str, arguments: dict) -> dict:
        result = self._rpc("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        return result.get("result", {})

    def close(self):
        self.proc.stdin.close()
        self.proc.terminate()
        self.proc.wait()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 mcp_client.py <cmd> [args...]")
        print("  e.g. python3 mcp_client.py github-mcp")
        sys.exit(1)

    cmd = sys.argv[1:]
    
    # Check for GitHub token
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    env = {}
    if token:
        env["GITHUB_PERSONAL_ACCESS_TOKEN"] = token
        env["GITHUB_TOKEN"] = token
    
    client = MCPClient(cmd, env=env)
    
    try:
        print("→ Initializing...")
        init_result = client.initialize()
        server_info = init_result.get("result", {}).get("serverInfo", {})
        print(f"   Server: {server_info.get('name', '?')} v{server_info.get('version', '?')}")
        print(f"   Capabilities: {json.dumps(init_result.get('result', {}).get('capabilities', {}))}")

        print("\n→ Listing tools...")
        tools = client.list_tools()
        print(f"   {len(tools)} tools available:\n")
        for t in tools:
            desc = t.get("description", "?")
            inputs = t.get("inputSchema", {}).get("properties", {})
            required = t.get("inputSchema", {}).get("required", [])
            print(f"   🔧 {t['name']}")
            print(f"      {desc}")
            if inputs:
                print(f"      Params: {', '.join(inputs.keys())}")
                if required:
                    print(f"      Required: {', '.join(required)}")
            print()

        # Interactive mode
        if len(sys.argv) == 2 and sys.argv[1] == "github-mcp":
            print("=" * 50)
            print("Interactive mode — type a tool name + JSON args")
            print("  e.g.:  list_issues {\"owner\": \"mbwjs\", \"repo\": \"miniagent\"}")
            print("  or:    /quit")
            print("=" * 50)
            
            while True:
                try:
                    line = input("\n> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                
                if line == "/quit":
                    break
                
                parts = line.split(" ", 1)
                tool_name = parts[0]
                args = {}
                if len(parts) > 1:
                    try:
                        args = json.loads(parts[1])
                    except json.JSONDecodeError as e:
                        print(f"   ❌ Invalid JSON: {e}")
                        continue
                
                try:
                    result = client.call_tool(tool_name, args)
                    content = result.get("content", [])
                    for c in content:
                        if c.get("type") == "text":
                            print(f"   {c['text'][:2000]}")
                        else:
                            print(f"   [{c.get('type')}]")
                except Exception as e:
                    print(f"   ❌ Error: {e}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
