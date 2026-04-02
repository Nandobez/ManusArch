# Manus AI Agent Architecture - Recipe for Replication

## Overview

Manus is an **autonomous AI agent** that wraps foundation models (Claude 3.5/3.7, Qwen) with an orchestration layer that enables real-world task execution. It's not a new model - it's an **engineering pattern** for making LLMs act autonomously.

---

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER REQUEST                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PLANNER MODULE                             │
│  - Breaks task into numbered steps                              │
│  - Outputs to todo.md file                                      │
│  - Can re-plan if requirements change                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       AGENT LOOP                                │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │ ANALYZE  │ → │  PLAN    │ → │ EXECUTE  │ → │ OBSERVE  │ ──┐ │
│  │ context  │   │ next     │   │ tool/    │   │ result   │   │ │
│  │ + events │   │ action   │   │ code     │   │          │   │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   │ │
│       ▲                                                       │ │
│       └───────────────────────────────────────────────────────┘ │
│                    (repeat until task complete)                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SANDBOX ENVIRONMENT                        │
│  - Ubuntu Linux VM in cloud                                     │
│  - Shell (bash with sudo)                                       │
│  - Browser (headless, controllable)                             │
│  - Python 3.10 + Node.js 20                                     │
│  - File system access                                           │
│  - Internet access                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Foundation Model (The Brain)

The LLM that does reasoning. Manus uses:
- **Claude 3.5/3.7** - Primary reasoning engine
- **Qwen (fine-tuned)** - Supplementary model
- **Multi-model routing** - Different models for different tasks (coding vs reasoning vs knowledge)

**Open Source Alternatives:**
- CodeActAgent (fine-tuned Mistral 7B) - Specifically trained for code-as-action
- Llama 3 / Mistral - General purpose
- Qwen open weights
- Or use APIs: Claude API, GPT-4 API

### 2. CodeAct Paradigm (The Action Language)

**This is the key innovation.** Instead of the LLM outputting structured tool calls like:
```json
{"tool": "search", "query": "weather in Tokyo"}
```

The LLM outputs **executable Python code**:
```python
import agent_tools
result = agent_tools.search_web("weather in Tokyo")
print(result)
```

**Why this is better:**
- Code can combine multiple operations in one action
- Code can have conditionals, loops, error handling
- Code can use any Python library
- Much more flexible than fixed tool schemas
- 30%+ higher success rate on complex tasks (per CodeAct paper)

**Implementation:**
1. Create a Python module `agent_tools.py` with functions like:
   - `search_web(query)` - Web search
   - `get_url_content(url)` - Fetch page content
   - `run_shell(command)` - Execute shell commands
   - `read_file(path)` / `write_file(path, content)`
   - `browser_navigate(url)` / `browser_click(selector)`

2. Execute LLM-generated code in sandboxed environment
3. Capture stdout/stderr as "observation"
4. Feed observation back to LLM for next iteration

### 3. Agent Loop (The Control Flow)

```python
def agent_loop(user_request):
    event_stream = [{"type": "user", "content": user_request}]
    plan = generate_plan(user_request)
    event_stream.append({"type": "plan", "content": plan})

    while not task_complete:
        # 1. Build context from recent events
        context = build_context(event_stream)

        # 2. Ask LLM for next action (code)
        action_code = llm.generate(context)
        event_stream.append({"type": "action", "content": action_code})

        # 3. Execute the code in sandbox
        result = sandbox.execute(action_code)
        event_stream.append({"type": "observation", "content": result})

        # 4. Check if done
        if is_final_answer(result):
            task_complete = True

    return extract_final_result(event_stream)
```

**Critical Rules:**
- Only ONE action per iteration (wait for result before next action)
- Always observe the result before deciding next step
- If error occurs: diagnose, retry, or try alternative approach
- Maximum iterations limit to prevent infinite loops

### 4. Planner Module (Task Decomposition)

Before executing, break the task into steps:

```markdown
# todo.md

## Task: Create a data visualization report

- [x] 1. Search for relevant datasets
- [x] 2. Download and clean the data
- [ ] 3. Generate visualizations with matplotlib
- [ ] 4. Write analysis summary
- [ ] 5. Compile into PDF report
```

**Implementation:**
- Use a separate LLM call at the start: "Break this task into steps"
- Store in `todo.md` file
- Update status as steps complete
- Re-plan if user changes requirements

### 5. Memory System

**Three types of memory:**

#### a) Event Stream (Short-term)
- Chronological log of all events in current session
- Types: user message, action, observation, plan, knowledge
- Truncate old events when context window fills
- Keep most recent N events + summary of older ones

#### b) File System (Persistent Scratchpad)
- Save intermediate results to files
- `notes.txt` - Information gathered during research
- `todo.md` - Task progress tracker
- `draft_*.md` - Document sections being written
- Allows agent to "forget" details but retrieve when needed

#### c) Knowledge Base (RAG)
- Vector database of documents, guides, best practices
- Query when domain knowledge needed
- Inject relevant chunks as "Knowledge" events

### 6. Tool Suite

| Tool | Purpose | Implementation |
|------|---------|----------------|
| Web Search | Find information | SerpAPI, Bing API, or scraping |
| Browser | Navigate, click, fill forms | Playwright, Selenium |
| Shell | Run system commands | subprocess in Docker |
| Python REPL | Execute code | exec() in sandbox |
| File I/O | Read/write files | Standard filesystem |
| API Calls | External data sources | requests library |

---

## Open Source Implementation Stack

### Recommended Stack

```
┌─────────────────────────────────────────┐
│           User Interface                │
│    (CLI, Web UI, or API endpoint)       │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         Orchestrator (Python)           │
│  - Agent loop logic                     │
│  - Event stream management              │
│  - Tool dispatch                        │
└─────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│   LLM    │ │  Tools   │ │  Memory  │
│  Server  │ │ Sandbox  │ │  Store   │
│ (vLLM)   │ │ (Docker) │ │ (FAISS)  │
└──────────┘ └──────────┘ └──────────┘
```

### Component Choices

| Component | Option 1 (Recommended) | Option 2 | Option 3 |
|-----------|------------------------|----------|----------|
| **LLM** | CodeActAgent (Mistral) | Claude API | GPT-4 API |
| **LLM Server** | vLLM | Ollama | FastChat |
| **Sandbox** | Docker container | Podman | VM |
| **Browser** | Playwright | Selenium | Puppeteer |
| **Orchestration** | Custom Python | LangChain | AutoGPT fork |
| **Vector Store** | FAISS | ChromaDB | Milvus |
| **Web Search** | SerpAPI | Bing API | DuckDuckGo |

### Minimal Setup

```bash
# 1. Install dependencies
pip install langchain playwright faiss-cpu vllm

# 2. Setup Docker sandbox
docker build -t agent-sandbox .

# 3. Download CodeActAgent model
# (or configure API keys for Claude/GPT-4)

# 4. Run orchestrator
python agent.py
```

---

## System Prompt Template

```markdown
You are an autonomous AI agent with access to a Linux environment.

<capabilities>
- Execute shell commands (bash)
- Browse the web (headless browser)
- Write and execute Python code
- Read and write files
- Call external APIs
</capabilities>

<rules>
1. Always respond with a tool action, never just text (unless delivering final result)
2. One action per turn - wait for observation before next action
3. Save important information to files, don't rely on memory
4. Cite sources when providing factual information
5. If an action fails, diagnose and retry or try alternative
6. Update todo.md as you complete steps
</rules>

<agent_loop>
1. Analyze: Review current state and events
2. Plan: Decide next action based on todo list
3. Execute: Output code/command to run
4. Observe: Check result
5. Repeat until task complete
</agent_loop>

<output_format>
When taking action, output Python code in a code block:
```python
# Your action code here
```

When task is complete, output final result in plain text.
</output_format>
```

---

## Implementation Checklist

### Phase 1: Basic Agent Loop
- [ ] Set up LLM inference (local or API)
- [ ] Implement simple tool: Python REPL
- [ ] Create agent loop that executes code and feeds back results
- [ ] Test with simple math/coding tasks

### Phase 2: Tool Expansion
- [ ] Add web search tool
- [ ] Add browser automation (Playwright)
- [ ] Add file I/O tools
- [ ] Add shell command execution
- [ ] Set up Docker sandbox for isolation

### Phase 3: Planning & Memory
- [ ] Implement planner module (task decomposition)
- [ ] Add todo.md tracking
- [ ] Set up vector store for RAG
- [ ] Implement context truncation/summarization

### Phase 4: Polish
- [ ] Add error handling and retry logic
- [ ] Implement max iterations safeguard
- [ ] Add progress notifications to user
- [ ] Build user interface (CLI or web)
- [ ] Add logging and debugging tools

---

## Key Insights

1. **It's mostly prompt engineering** - The architecture is powerful, but reliability comes from detailed system prompts with rules and examples.

2. **Code > JSON for actions** - The CodeAct approach is significantly more capable than structured tool calls.

3. **Files as memory** - Externalizing state to files is crucial for long tasks that exceed context windows.

4. **One step at a time** - Forcing the agent to wait for each action's result prevents runaway behavior.

5. **Multi-model is optional** - Start with one good model, add routing later for optimization.

6. **Sandbox is essential** - Never run LLM-generated code on your actual system.

---

## References

- CodeAct Paper: https://openreview.net/forum?id=jJ9BoXAfFa
- CodeActAgent Repo: https://github.com/xingyaoww/code-act
- Manus Prompts (leaked): https://gist.github.com/jlia0/db0a9695b3ca7609c9b1a08dcbf872c9
- AutoGPT: https://github.com/Significant-Gravitas/AutoGPT
- LangChain Agents: https://python.langchain.com/docs/modules/agents/
