# 小红书运营助手

这是一个面向小红书运营场景的 AGIAgent App 模板。

## 功能
- 账号登录状态检查
- 笔记内容生成与发布
- Feed 检索与详情分析
- 评论/回复/点赞/收藏等互动动作
- 数据复盘与下一轮优化建议

## MCP 配置
本 App 使用 `apps/xiaohongshu/mcp_servers.json`，默认连接：
- `xiaohongshu-mcp` -> `http://localhost:18060/mcp`

## 启动示例
```bash
python agia.py --app xiaohongshu "帮我做一周的小红书选题并发布第一篇"
```
