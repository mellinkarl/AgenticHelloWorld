# Vertex AI × LangChain — Modular Agents Backend

A concise, production-oriented backend that separates **reusable atomic Agents** from **team-owned composite Agents**, running on **Vertex AI (Gemini)**.
Default is text-only mode; tools are optional and pluggable.

---

## Table of Contents

* [1. Overview](#1-overview)

* [2. Architecture](#2-architecture)

* [3. Directory Structure](#3-directory-structure)

* [4. Configuration & Credentials (YAML, Overrides, Defaults, Logging)](#4-configuration--credentials-yaml-overrides-defaults-logging)

  * [4.1 `default.yaml` Contents](#41-defaultyaml-contents)
  * [4.2 Per-Agent Overrides — Names & Mapping](#42-per-agent-overrides--names--mapping)
  * [4.3 Defaults When Not Overridden](#43-defaults-when-not-overridden)
  * [4.4 ADC vs Local SA Key](#44-adc-vs-local-sa-key)
  * [4.5 Logging Configuration (Location & Method)](#45-logging-configuration-location--method)

* [5. Prompts (Universal vs Composite-local vs Dynamic)](#5-prompts-universal-vs-composite-local-vs-dynamic)

  * [5.1 Selecting a Universal Prompt](#51-selecting-a-universal-prompt)
  * [5.2 Composite-local Prompt](#52-composite-local-prompt)
  * [5.3 Dynamic Prompt Generation](#53-dynamic-prompt-generation)
  * [5.4 Rules First + LLM Fallback](#54-rules-first--llm-fallback)

* [6. Atomic Agents (Quick Reference)](#6-atomic-agents-quick-reference)

* [7. Composite Agents](#7-composite-agents)

  * [7.1 Example: `test_graph` Composite Agent](#71-example-test_graph-composite-agent)

* [8. Tools & Registry](#8-tools--registry)

* [9. FastAPI (Invoke Any Agent)](#9-fastapi-invoke-any-agent)

  * [9.1 Endpoints](#91-endpoints)
  * [9.2 Request/Response Pattern](#92-requestresponse-pattern)
  * [9.3 Call Examples](#93-call-examples)

* [10. Testing (Using Goldens)](#10-testing-using-goldens)

* [11. Local Runner (Temporary)](#11-local-runner-temporary)

* [12. Development Workflow](#12-development-workflow)

* [13. Roadmap / TODO](#13-roadmap--todo)

* [Appendix A — Agent Details](#appendix-a--agent-details)

---

## 1. Overview

* **Atomic Agent**: Reads `state: Dict[str, Any]`, returns a small **delta dict** to be merged.
* **Composite Agent**: Orchestrates multiple atomic Agents, exposing the same `.invoke()` interface.
* **Prompt**: Three categories — **Universal Registry**, **Composite-local**, **Dynamically Generated**.
* **Tools**: Python callables, registered once, invoked via a lightweight Agent wrapper.
* Configuration automatically supports **ADC** and local SA key; logging is **structured JSON**.

---

## 2. Architecture

1. Request arrives (HTTP / Local runner), carrying `state`.
2. **Agent** executes: reads only required keys, returns a delta.
3. Controller / Composite Agent merges delta into `state`, continues to the next step.
4. Output is standardized (`{"text": "..."}` or `{"json": {...}}`).

Supports:

* **Sync**: `invoke(state) -> Dict[str, Any]`
* **Async placeholder**: `ainvoke(state) -> Dict[str, Any]` (upgradeable to async/streaming)

---

## 3. Directory Structure

```bash
src/
├── agents/                          # Atomic Agents (reusable)
│   ├── diff_enforcer_agent.py
│   ├── length_keyword_guard_agent.py
│   ├── llm_router_agent.py
│   ├── llm_runner_agent.py
│   ├── python_tool_agent.py
│   ├── refiner_agent.py
│   ├── rule_router_agent.py
│   ├── schema_enforcer_agent.py
│   └── template_filler_agent.py
│
├── app/                              # FastAPI app and routes
│   ├── main.py
│   └── routes/
│
├── composite_agents/                 # Team-owned composite Agents
│   └── test_linear/
│
├── config/                           # Configuration & logging
│   ├── config.py
│   ├── default.yaml
│   └── logging_config.py
│
├── core/                             # Protocols & instrumentation
│   ├── agent_protocol.py
│   ├── context.py
│   ├── instrumentation.py
│   └── logging_utils.py
│
├── llm/                              # LLM wrapper
│   └── vertex.py
│
├── prompts/                          # Universal prompts & registry
│   ├── __init__.py
│   ├── base_prompt.py
│   ├── llm_router_prompt.py
│   └── refiner_prompt.py
│
├── runner/                           # Local runner
│   └── run_composite_test.py
│
├── tools/                            # Tool functions & registry
│   ├── registry.py
│   └── date_tool.py
│
├── tests/                            # Tests & helpers
│   ├── helpers/
│   └── ...
└── probe_vertex.py
```

---

## 4. Configuration & Credentials (YAML, Overrides, Defaults, Logging)

### 4.1 `default.yaml` Contents (Extended Version)

```yaml
# GCP / Auth
project: your-gcp-project
location: us-central1
credentials_name: your-service-account.json

# Global LLM defaults
model_name: gemini-2.0-flash
temperature: 0.2
top_p: 0.95
top_k: 40
candidate_count: 1
max_output_tokens: 1024
response_mime_type: text/plain
system_instruction: ""
stop_sequences: []
timeout_s: 60

# Per-Agent overrides
agents:
  runner:
    temperature: 0.1
    system_instruction: "Be brief and literal."
  refiner:
    max_output_tokens: 1024
  decider:
    temperature: 0.0
    system_instruction: "You only decide route labels."

# Retry policy
retry:
  max_attempts: 3
  initial_backoff_s: 0.5
  max_backoff_s: 8.0
  multiplier: 2.0

# Logging
logging:
  level: INFO
  format: json
  include_request_id: true
  file: logs/app.log
  rotate_mb: 10
  rotate_backups: 5
```

---

**Minimal `src/config/default.yaml`**

```yaml
project: aime-hello-world
location: us-central1
model_name: gemini-2.0-flash
temperature: 0.2
max_output_tokens: 1024

logging:
  level: INFO
  format: json
  file: logs/app.log         # Optional, leave empty to log to stdout only
  rotate_mb: 10
  rotate_backups: 5
```

**Per-agent override example (inherits global if omitted)**

```yaml
agents:
  runner:                   # → LLMRunnerAgent
    temperature: 0.1
  refiner:                  # → RefinerAgent
    max_output_tokens: 2048
  decider:                  # → LLMRouterAgent
    model: gemini-2.0-pro
```

> Runtime:
>
> * `get_vertex_chat_model(agent="runner")` merges: Global → `agents.runner` → Call-time overrides (**kwargs**).
> * If `agents.runner` is not set, it uses global `llm` defaults entirely.

---

### 4.2 Per-Agent Overrides — Names & Mapping

| YAML Key | Agent Class    | Example Call                             |
| -------- | -------------- | ---------------------------------------- |
| runner   | LLMRunnerAgent | `get_vertex_chat_model(agent="runner")`  |
| refiner  | RefinerAgent   | `get_vertex_chat_model(agent="refiner")` |
| decider  | LLMRouterAgent | `get_vertex_chat_model(agent="decider")` |

### 4.3 Defaults When Not Overridden

Defaults to global `model_name`, `temperature`, etc.

### 4.4 ADC vs Local SA Key

* `USE_ADC=true` → Application Default Credentials
* Else use `GOOGLE_APPLICATION_CREDENTIALS` or `src/.keys/{credentials_name}`

### 4.5 Logging Configuration

See `src/config/logging_config.py`.
Each Agent logs `invoke.start` and `invoke.end` (with preview, result, and duration in ms).

---

## 5. Prompts (Universal vs Composite-local vs Dynamic)

### 5.1 Selecting a Universal Prompt

Located in `src/prompts/`, registered in `PROMPTS`.
HTTP call:

```bash
curl -X POST localhost:8000/agents/LLMRunnerAgent/invoke \
  -H 'content-type: application/json' \
  -d '{"state":{"user_input":"Say OK"},"args":{"prompt_name":"runner/personal"}}'
```

### 5.2 Composite-local Prompt

Placed under `src/composite_agents/<name>/prompts/`, used only by that composite:

```python
from src.agents.llm_router_agent import LLMRouterAgent
from .prompts.route_v1 import ROUTE_PROMPT

state.update(LLMRouterAgent(prompt=ROUTE_PROMPT).invoke(state))
```

### 5.3 Dynamic Prompt Generation

Based on `state` or config, dynamically construct:

```python
from langchain_core.prompts import ChatPromptTemplate
from src.config.config import Config
from src.agents.llm_runner_agent import LLMRunnerAgent

cfg = Config.load()
sys_msg = f"You are a {state.get('domain','generic')} assistant."
prompt = ChatPromptTemplate.from_messages([("system", sys_msg), ("user", "{user_input}")])

state.update(LLMRunnerAgent(prompt=prompt, llm_kwargs=cfg.llm_kwargs(agent="runner", temperature=0.1)).invoke(state))
```

### 5.4 Rules First + LLM Fallback

Run `RuleRouterAgent` first; if undecided, fall back to LLM:

```python
state.update(RuleRouterAgent(rules={...}, default_route="llm_decide").invoke(state))
if state.get("route") == "llm_decide":
    state.update(LLMRouterAgent(prompt=ROUTE_PROMPT).invoke(state))
```

---

## 6. Atomic Agents (Quick Reference)

| Agent                   | Purpose                     | Reads                 | Writes             |
| ----------------------- | --------------------------- | --------------------- | ------------------ |
| LLMRunnerAgent          | Prompt → LLM → draft        | `user_input`          | `draft`            |
| RuleRouterAgent         | Rule-based routing          | `draft`               | `route`, `reasons` |
| LLMRouterAgent          | LLM-based routing           | `user_input`, `draft` | `route`, `raw`     |
| RefinerAgent            | Rewrite (preserve intent)   | `draft`               | `text`             |
| SchemaEnforcerAgent     | Normalize to text/JSON      | `text`/`draft`        | `text`/`json`      |
| LengthKeywordGuardAgent | Length/keyword check        | `text`                | `ok`, `violations` |
| DiffEnforcerAgent       | Ensure `text` ≠ `draft`     | `draft`, `text`       | `text`             |
| PythonToolAgent         | Invoke registered tool      | kwargs                | `<output_key>`     |
| TemplateFillerAgent     | Render `.format()` template | template keys         | `<output_key>`     |

---

## 7. Composite Agents

Composite Agents chain atomic Agents, may have local Prompts and conditional logic, maintained independently by the team.

### 7.1 Example: `test_graph` Composite Agent

`src/composite_agents/test_graph/graph.py` is a composite Agent that can be used as a template.

Flow:

1. LLM generates 6 lowercase letters
2. Routing (TRIPLE/DOUBLE/NONE)
3. Execute branch logic
4. Uniformly pass through `SchemaEnforcerAgent` to return `{"text": "..."}`

---

## 8. Tools & Registry

Functions go in `src/tools/`, registered in `registry.py`; use `PythonToolAgent` to invoke and write to the target key.

---

## 9. FastAPI (Invoke Any Agent)

### Start Server

```bash
uvicorn src.app.main:app --reload --port 8000
```

Upon start, JSON logs will be output and each response will include an `x-request-id` header.

---

### 9.1 Endpoints

* `GET /agents` → List Agents
* `POST /agents/{agent_name}/invoke` → Generic call
* Dedicated: `/agents/python-tool/invoke`, `/agents/template-filler/invoke`

### 9.2 Request/Response Pattern

* Request: `state`, optional `args`, `async_mode`
* Response: `agent`, `ms`, `state_in`, `state_out`

### 9.3 Call Examples

#### 1) LLMRunnerAgent (sync)

```bash
curl -X POST localhost:8000/agents/LLMRunnerAgent/invoke \
  -H 'content-type: application/json' \
  -d '{"state":{"user_input":"Say exactly: OK."},"async_mode":false}'
```

#### 2) PythonToolAgent (async)

```bash
curl -X POST localhost:8000/agents/python-tool/invoke \
  -H 'content-type: application/json' \
  -d '{"state":{},"args":{"tool_name":"date.today","output_key":"today"},"async_mode":true}'
```

#### 3) `test_graph` Composite Agent

```bash
curl -X POST localhost:8000/composites/test-graph/invoke \
  -H 'content-type: application/json' \
  -d '{"state":{"user_input":"kickstart"}}'
```

This composite will generate letters → route → run branch → return:

```json
{"text":"..."}
```

---

## 10. Testing (Using Goldens)

Tests are in `src/tests/`, run with `pytest -q`.
Use `--write-goldens` to update baseline files.

---

## 11. Local Runner (Temporary)

Quick tests under `src/runner/`; `probe_vertex.py` checks environment and config.

---

## 12. Development Workflow

1. Add or modify atomic Agent in `src/agents/`
2. Place Prompt in universal or composite-local directory
3. Create/extend composite in `src/composite_agents/`
4. Register tools
5. Test via HTTP or local runner
6. Add tests and update goldens

---

## 13. Roadmap / TODO

* Support streaming (`astream_events`) + SSE/WebSocket
* Expand universal Prompts, add health checks
* More composite examples
* Latency/Token monitoring & optimization
* Update `probe_vertex.py`

---

## Appendix A — Agent Details

**LLMRunnerAgent**
Reads: `user_input` → Writes: `draft`, supports injecting Prompt via `args.prompt_name`

**RuleRouterAgent**
Rule-based routing → Writes: `route`, `reasons`

**LLMRouterAgent**
LLM-based routing → Writes: `route`, `raw`

**RefinerAgent**
Light rewrite → Writes: `text`

**SchemaEnforcerAgent**
Normalize to `{"text": ...}` or `{"json": ...}`

**LengthKeywordGuardAgent**
Check length & keywords → Writes: `ok`, `violations`

**DiffEnforcerAgent**
Ensure `text` is different from `draft`

**PythonToolAgent**
Invoke registered tool → Writes `<output_key>`

**TemplateFillerAgent**
Render `.format()` template → Writes `<output_key>`

---
