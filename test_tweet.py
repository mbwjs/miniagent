#!/usr/bin/env python3
"""Test X MCP server - post a tweet"""
import subprocess, json, os

# Load env
env = {}
with open('/root/miniagent/.env.twitter') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k] = v

merged = os.environ.copy()
merged.update(env)

proc = subprocess.Popen(
    ['node', '/usr/lib/node_modules/@crazyrabbitltc/mcp-twitter-server/dist/index.js'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=merged
)

def rpc(proc, method, params=None):
    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}) + "\n"
    proc.stdin.write(req)
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())

# Init
init = rpc(proc, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}})
print("Init:", init.get("result", {}).get("serverInfo", {}).get("name", "?"))

# Post tweet
result = rpc(proc, "tools/call", {"name": "postTweet", "arguments": {"text": "🧪 测试推文：MiniAgent MCP 集成成功！从 VPS 通过 @crazyrabbitltc 的 X MCP Server 发出。#AI #MCP #buildinpublic"}})
print("Result:", json.dumps(result, indent=2))

# Cleanup
proc.stdin.close()
proc.terminate()
proc.wait()
stderr = proc.stderr.read()
if stderr:
    print("Stderr:", stderr[:500])
