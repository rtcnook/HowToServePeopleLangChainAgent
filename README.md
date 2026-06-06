# HowToServePeopleLangChainAgent

基于 **LangChain + LangGraph** 的多智能体考公/考编岗位检索系统。

---

## 架构

```
用户输入
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  CEO Agent (LangGraph ReAct + 5 个委托工具)            │
│                                                      │
│  ┌──────────────────┐  ┌──────────────────┐          │
│  │ google_search    │  │ url_context      │          │
│  │ Agent            │  │ Agent            │          │
│  │                  │  │                  │          │
│  │ web_search 工具   │  │ read_url 工具     │          │
│  │ (Tavily/Duck)    │  │ (WebBaseLoader)  │          │
│  └──────────────────┘  └──────────────────┘          │
│                                                      │
│  ┌──────────────────┐  ┌──────────────────┐          │
│  │ job_search       │  │ task             │          │
│  │ Agent            │  │ Agent            │          │
│  │                  │  │                  │          │
│  │ 考公/考编专项搜索  │  │ 写作/编码/分析    │          │
│  └──────────────────┘  └──────────────────┘          │
│                                                      │
│  ┌──────────────────┐                                │
│  │ quality          │                                │
│  │ Agent            │                                │
│  │                  │                                │
│  │ 输出质量审查       │                                │
│  └──────────────────┘                                │
└──────────────────────────────────────────────────────┘
    │
    ▼
汇总后的最终答案
```

### 工作流程

1. 用户输入查询（例如：「男，2019年毕业，计算机科学与技术，想找山西太原考公岗位」）
2. CEO 识别到是考公需求 → 调用 `delegate_job_search`
3. job_search_agent 联网搜索岗位公告/职位表 → 返回结构化结果
4. CEO 如需要可继续调用 `delegate_quality_review` 检查结果
5. CEO 汇总后输出最终答案

其他场景：
- 普通搜索 → CEO 直接调用 `delegate_google_search`
- 给的链接 → CEO 调用 `delegate_url_context`
- 写文档/方案 → CEO 调用 `delegate_task`

---

## 快速开始

### 环境要求

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/) 包管理器（或 pip）

### 1. 安装依赖

```bash
cd HowToServePeopleLangChainAgent
uv sync
```

### 2. 配置 .env

项目根目录已有 `.env` 文件，按需修改：

```bash
# 模型后端（三选一）
LLM_PROVIDER=dashscope          # 阿里云百炼（推荐）
# LLM_PROVIDER=siliconflow      # 硅基流动
# LLM_PROVIDER=gemini           # Google Gemini

# 模型名称
LLM_MODEL=qwen3.7-plus

# 阿里云百炼 API Key
DASHSCOPE_KEY=sk-...y

# LangSmith 追踪（可选）
LANGSMITH_API_KEY=lsv2_p...y
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=LangChainCourse

# 阿里云 OSS（可选）
OSS_ACCESS_KEY_ID=***
OSS_ACCESS_KEY_SECRET=***
OSS_BUCKET=***
```

### 3. 运行

```bash
# 交互式 CLI
uv run main.py

# 或编程调用
python -c "from ServePeopleLangChainAgent import run; print(run('查一下今天北京天气'))"
```

---

## 支持的模型后端

| 后端 | LLM_PROVIDER | 需要的 Key | 说明 |
|---|---|---|---|
| **阿里云百炼** | `dashscope` | `DASHSCOPE_KEY_P1+P2` | 中文场景最优，有 100 万 Token 免费额度 |
| **硅基流动** | `siliconflow` | `SILICONFLOW_API_KEY` | OpenAI 兼容，支持 Qwen/DeepSeek 等 |
| **Google Gemini** | `gemini` | `GOOGLE_API_KEY` | 英文最强，需科学上网 |

### 可用模型（阿里云百炼）

| 模型 | 免费额度 | 定位 |
|---|---|---|
| `qwen3.7-plus` | 各 100 万 Token / 90 天 | ⚖️ 推荐，速度快效果好 |
| `qwen3.7-max` | 各 100 万 Token / 90 天 | 🏆 旗舰，最强推理 |
| `qwen3.6-flash` | 各 100 万 Token / 90 天 | ⚡ 轻量快速 |
| `qwen-plus` | — | 旧版 Plus |
| `qwen-max` | — | 旧版 Max |

---

## 项目结构

```
HowToServePeopleLangChainAgent/
├── main.py                          # CLI 入口
├── pyproject.toml                   # 项目元数据 + 依赖
├── .env                             # 环境变量（API Key、模型配置）
├── README.md                        # 本文档
│
└── ServePeopleLangChainAgent/       # 核心包
    ├── __init__.py                  # 公共 API 导出
    ├── config.py                    # 环境加载、LangSmith、模型工厂
    ├── prompts.py                   # 全部 6 个 Agent 的系统提示词
    ├── tools.py                     # 基础工具：搜索、URL 读取
    ├── agents.py                    # 子 Agent 构建 + 委托工具包装
    └── orchestrator.py              # CEO Agent + run() / run_async()
```

### 模块职责

| 文件 | 行数 | 职责 |
|---|---|---|
| `config.py` | ~80 | 读取 `.env`、初始化 LangSmith、构建模型（支持 3 个后端） |
| `prompts.py` | ~86 | 5 个子 Agent + 1 个 CEO 的中文 System Prompt |
| `tools.py` | ~75 | `web_search`（Tavily 优先 / DuckDuckGo 回退）+ `read_url` |
| `agents.py` | ~119 | 构建 5 个 ReAct Agent，包装为 `@tool` 供 CEO 调用 |
| `orchestrator.py` | ~49 | 构建 CEO Agent，暴露 `run()` / `run_async()` 入口 |

---

## API 参考

### Python API

```python
from ServePeopleLangChainAgent import run, run_async, get_ceo_agent

# 同步调用——返回完整文本
answer = run("你的问题")
print(answer)

# 异步调用
answer = await run_async("你的问题")

# 获取底层 CEO Agent（调试用）
ceo = get_ceo_agent()
```

### 委托工具

CEO Agent 有 5 个委托工具可用：

| 工具名 | 用途 | 何时调用 |
|---|---|---|
| `delegate_google_search` | 联网搜索 | 实时信息、新闻、政策 |
| `delegate_url_context` | 读取 URL 内容 | 用户给了链接 |
| `delegate_job_search` | 考公/考编岗位搜索 | 用户找体制内工作 |
| `delegate_task` | 执行具体任务 | 写文档、编码、分析 |
| `delegate_quality_review` | 检查输出质量 | 审查结果正确性 |

---

## 搜索后端

两种搜索方式自动切换：

- **Tavily**（设置了 `TAVILY_API_KEY` 时）→ 结构化结果，带标题/URL/摘要
- **DuckDuckGo**（默认回退）→ 免费，无需 API Key

---

## 与原版（ADK）的区别

| 维度 | Google ADK 版 | LangChain 版 |
|---|---|---|
| 框架 | Google ADK 2.1 | LangChain 1.3 + LangGraph 1.2 |
| 搜索 | GoogleSearchTool | Tavily / DuckDuckGo |
| 模型 | 仅 Gemini | Gemini / SiliconFlow / DashScope 三后端 |
| Agent 模式 | `LlmAgent` + `AgentTool` | `create_react_agent` + `@tool` |
| 初始化 | 导入即构建 | 懒加载，`run()` 时才构建 |
| 异步 | 内置 | `run_async()` |
| LanguageSmith 追踪 | 无 | 自动启用（配置 Key 后） |

---

## 常见问题

### Q: 怎么切换模型？

编辑 `.env`：
```bash
LLM_MODEL=qwen3.7-plus   # 改成想要的名字
```

### Q: 怎么关掉 LangSmith？

删除或注释 `.env` 里的 `LANGSMITH_API_KEY` 行。

### Q: 搜索不到结果？

默认用 DuckDuckGo，有时结果较少。建议配置 Tavily：
```bash
TAVILY_API_KEY=*** your key
```
