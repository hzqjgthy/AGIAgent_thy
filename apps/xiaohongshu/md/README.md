# Xiaohongshu Ops Assistant

This app is an AGIAgent template for Xiaohongshu (RED) operation workflows.

## Features
- Login status checks
- Note generation and publishing
- Feed search and detail analysis
- Interaction actions (comment/reply/like/favorite)
- Performance review and optimization suggestions

## MCP Config
This app uses `apps/xiaohongshu/mcp_servers.json` by default:
- `xiaohongshu-mcp` -> `http://localhost:18060/mcp`

## Run
```bash
python agia.py --app xiaohongshu "Plan and publish a Xiaohongshu post"
```
