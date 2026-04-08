```
███╗   ███╗ █████╗ ███╗   ██╗██╗   ██╗███████╗ █████╗ ██████╗  ██████╗██╗  ██╗
████╗ ████║██╔══██╗████╗  ██║██║   ██║██╔════╝██╔══██╗██╔══██╗██╔════╝██║  ██║
██╔████╔██║███████║██╔██╗ ██║██║   ██║███████╗███████║██████╔╝██║     ███████║
██║╚██╔╝██║██╔══██║██║╚██╗██║██║   ██║╚════██║██╔══██║██╔══██╗██║     ██╔══██║
██║ ╚═╝ ██║██║  ██║██║ ╚████║╚██████╔╝███████║██║  ██║██║  ██║╚██████╗██║  ██║
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
```

# ManusArch — Manus-like Autonomous Agent

Autonomous agent system with a Docker sandbox and an LLM-driven orchestrator. Inspired by the Manus architecture: the orchestrator runs on your host and drives an isolated container that has Firefox, Python, Playwright and a shell, so the agent can browse, write code and run commands without touching your machine.

```
┌─────────────────────────┐         ┌─────────────────────────┐
│     ORCHESTRATOR        │         │       SANDBOX           │
│       (host)            │         │   (Docker container)    │
│                         │         │                         │
│  ┌─────────────────┐    │         │  ┌─────────────────┐    │
│  │   LLM Client    │    │         │  │    Firefox      │    │
│  │ (Claude / GPT / │    │         │  │    Python       │    │
│  │  Groq / Ollama) │    │  docker │  │    Playwright   │    │
│  └────────┬────────┘    │   exec  │  │    Shell        │    │
│           │             │ ───────▶│  └─────────────────┘    │
│  ┌────────▼────────┐    │         │                         │
│  │   Agent Loop    │    │◀─────── │  Result / Output        │
│  └─────────────────┘    │         │                         │
└─────────────────────────┘         └─────────────────────────┘
```

## Features

- **Sandboxed execution** — every action runs inside Docker, away from the host.
- **Multi-provider LLM client** — OpenAI, Anthropic, Groq and Ollama supported out of the box.
- **Agent loop** — plan, act, observe, repeat, until the task is done.
- **Specialized sub-agents** — coordinator, web, file, data and code agents.
- **Headless or visual** — view the browser via noVNC or a native VNC client.

## Quickstart

### 1. Build and run the sandbox

```bash
docker build -t agent-sandbox .
docker run -d -p 6080:6080 -p 5900:5900 --name sandbox agent-sandbox
docker ps
```

### 2. Set up the orchestrator

```bash
cd orchestrator
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Export the API key for the provider you want to use:

```bash
export OPENAI_API_KEY=...        # or
export ANTHROPIC_API_KEY=...     # or
export GROQ_API_KEY=...
```

### 3. Run the agent

```bash
python example.py
```

Type a task and watch the agent execute it inside the sandbox.

## Accessing the Sandbox

| Method               | URL / Command                       |
|----------------------|-------------------------------------|
| noVNC (browser view) | http://localhost:6080/vnc.html      |
| VNC client           | `localhost:5900`                    |
| Direct shell         | `docker exec -it sandbox bash`      |

## Project Layout

```
ManusArch/
├── Dockerfile                       # Sandbox image
├── supervisord.conf                 # Process supervisor
├── start.sh                         # Container entrypoint
├── run.sh                           # Helper launcher
├── manus-architecture-recipe.md     # Technical write-up
├── sandbox_scripts/
│   └── browser_server.py            # Playwright bridge
└── orchestrator/
    ├── agent.py                     # Agent loop
    ├── llm_client.py                # Multi-provider client
    ├── project_manager.py
    ├── main.py
    ├── example.py
    ├── agents/                      # coordinator, web, file, data, code
    └── requirements.txt
```

## Configuration

API keys are read from environment variables — never committed:

| Provider  | Env var               |
|-----------|-----------------------|
| OpenAI    | `OPENAI_API_KEY`      |
| Anthropic | `ANTHROPIC_API_KEY`   |
| Groq      | `GROQ_API_KEY`        |
| Ollama    | runs locally, no key  |

## License

MIT.
