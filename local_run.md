# AI PPT 生成系统指南

如果你希望在不同的终端中分别启动各个服务以便于观察日志和调试，请按照以下步骤操作。

## 1. 准备工作

在每个新打开的终端中，你都需要先进入项目目录并设置环境变量（尤其是 `PYTHONPATH` 和 `GOOGLE_API_KEY`）。

为了方便，建议在每个终端先运行以下通用设置命令：

```bash
# 1. 进入项目目录
cd /Users/lpd/Documents/a2a-samples-main/samples/python/agents/a2a_mcp/samples/python/agents/ai_ppt_generator

# 2. 激活虚拟环境 (如果已安装 uv)
source .venv/bin/activate

# 3. 设置 PYTHONPATH (确保能找到 src 和上级模块)
export PYTHONPATH=$PYTHONPATH:$(pwd)/src:$(pwd)/../../../../src

# 4. 加载环境变量 (主要是 GOOGLE_API_KEY)
# 你可以直接 export 或者让 python-dotenv 自动加载 .env 文件
export GOOGLE_API_KEY=AIzaSyCbj0NJpGYnnctxuDsa3r6eCji1vrsPJnU
```

---

## 2. 逐步启动服务

请打开 **6 个独立的终端窗口**，分别执行以下命令：

### 终端 1: 启动 MCP Server (负责 Agent 发现)
这是系统的“人才市场”，必须最先启动。
```bash
uv run src/ai_ppt/mcp/a2a_mcp_server.py
```
*   **端口**: 10100

### 终端 2: 启动 Orchestrator (项目经理)
这是系统的“大脑”，负责接收请求和编排流程。
```bash
uv run src/ai_ppt/agents/orchestrator.py --port 10200
```
*   **端口**: 10200

### 终端 3: 启动 Outliner (大纲策划师)
负责生成 PPT 结构大纲。
```bash
uv run src/ai_ppt/agents/outliner.py --port 10201
```
*   **端口**: 10201

### 终端 4: 启动 Copywriter (文案撰写师)
负责为每一页 PPT 撰写详细内容。
```bash
uv run src/ai_ppt/agents/copywriter.py --port 10202
```
*   **端口**: 10202

### 终端 5: 启动 Builder (构建工程师)
负责将内容打包成最终的 .pptx 文件。
```bash
uv run src/ai_ppt/agents/builder.py --port 10203
```
*   **端口**: 10203

### 终端 6: 发送客户端请求 (测试)
当前面 5 个服务都启动并显示 Ready 后，在这个终端发送任务指令。

```bash
# 替换 "AI未来的发展趋势" 为你想要的主题
uv run src/ai_ppt/mcp/a2a_client.py "AI未来的发展趋势"
```

---

## 3. 常见问题

*   **端口冲突**：如果启动失败提示端口被占用，请检查是否有旧的进程未关闭（可以使用 `lsof -i :10200` 查看）。
*   **找不到模块**：如果报错 `ModuleNotFoundError`，请务必检查步骤 1 中的 `export PYTHONPATH` 是否在当前终端执行过。
