
# Vertex AI × LangChain — Minimal Chain & Composite Graph (Text-Only)

A tiny, multi-file skeleton that runs either:
- a **single LCEL chain** (no agents/tools), or
- a **minimal composite graph** (Runner → Router → Refiner) via LangGraph.

All LLM calls use **Vertex AI (Gemini)**. I/O is **plain text** (`response_mime_type="text/plain"`). No external tools or retrieval.

---

## Highlights

- **LCEL minimalism:** `ChatPromptTemplate → ChatVertexAI → StrOutputParser`
- **Composite orchestration:** atomic agents in `src/agents/`, team-owned wiring in `src/composite_agents/`, and generic graph builders in `src/chains/`
- **Config-driven:** `src/config/default.yaml` for project/region/model; optional per-agent overrides
- **Credential modes:**  
  - Local explicit **Service Account (SA) JSON**  
  - Cloud **ADC** via `USE_ADC=true`
- **Pinned deps** (`src/requirements_langchain.txt`) for reproducible runs

---

## Repo Layout
```

.
├── README.md
├── requirements.txt                    # (optional umbrella; prefer src/requirements\_langchain.txt)
└── src
├── config/
│   └── default.yaml                    # project/region/model/overrides
├── config.py                           # YAML+env loader, SA/ADC handling
├── core/
│   └── agent\_protocol.py              # tiny Agent Protocol
├── llm/
│   └── vertex.py                       # ChatVertexAI factory
├── prompts/
│   ├── base\_prompt.py
│   ├── judge\_router\_prompt.py
│   └── refiner\_prompt.py
├── agents/                             # atomic agents (single responsibility)
│   ├── runner\_agent.py
│   ├── router\_agent.py
│   └── refiner\_agent.py
├── chains/                             # generic connection patterns
│   ├── graphs.py                       # LangGraph builders
│   └── simple\_chain.py                # LCEL chain factory
├── composite\_agents/                  # team-maintained orchestrations
│   └── runner\_router\_refiner.py      # Runner → Router → (Refiner)
├── schemas/
│   └── io.py                           # Pydantic I/O
├── runner/
│   ├── run\_simple.py                  # single-chain CLI
│   └── run\_graph.py                   # composite graph CLI
├── probe\_vertex.py                    # env & reachability probe
└── requirements\_langchain.txt         # pinned, known-good deps

````

---

## Requirements

- Python **3.11 – 3.13**
- A Google Cloud project with **Vertex AI** enabled (you’ll set the ID/region in YAML)

Install pinned deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r src/requirements_langchain.txt
````

**Pinned versions (for reference):**

```
langchain==0.3.27
langchain-core==0.3.72
langchain-google-vertexai==2.0.28

langgraph==0.6.4
langgraph-checkpoint==2.1.1
langgraph-prebuilt==0.6.4
langgraph-sdk==0.2.0

pydantic==2.11.7
vertexai==1.43.0
google-cloud-aiplatform==1.108.0
google-auth==2.40.3
PyYAML==6.0.2
```

---

## Configuration

### 1) `src/config/default.yaml`

Fill with **your** project/region and (optionally) a local key filename. Keep the file user-agnostic; do **not** commit actual keys.

```yaml
project: "<your-project-id>"
location: "us-central1"

# If running locally with a Service Account key under src/.keys/
# (Do NOT commit the key; this is just a filename reference.)
credentials_name: "<your-key-file>.json"

# Global LLM defaults
model_name: "gemini-2.0-flash"
temperature: 0.2
max_output_tokens: 512
response_mime_type: "text/plain"

# Optional per-agent overrides (keys must match lookups in code)
agents:
  runner:
    model: "gemini-2.0-flash"
  refiner:
    temperature: 0.0
```

### 2) Credentials

* **Local SA (default)**
  Place your key at `src/.keys/<your-key-file>.json` and reference it via `credentials_name` in YAML.

* **Cloud ADC**
  Deploy with a Service Account that has `roles/aiplatform.user` and set:

  ```bash
  export USE_ADC=true
  ```

  You can also override project/region via env:

  ```bash
  export GOOGLE_CLOUD_PROJECT="<your-project-id>"
  export GOOGLE_CLOUD_REGION="us-central1"
  ```

> The repo never hardcodes `project` or key names; everything is configurable.

---

## Run Locally

### Single LCEL Chain (no agents/tools)

```bash
python -m src.runner.run_simple --input "Say exactly: OK."
```

**Expected JSON**

```json
{
  "text": "OK."
}
```

### Composite Graph: Runner → Router → (Refiner)

* **PASS path** (Router rule: `draft.strip() == "OK."`)

```bash
python -m src.runner.run_graph --input "Say exactly: OK."
# -> {"text":"OK."}
```

* **REFINE path** (force test the refiner branch)

```bash
python -m src.runner.run_graph --input "Say: hi" --force_refine
# -> Refiner rewrites to satisfy requirements (keeps intent, plain text output)
```

---

## Probe (optional)

Quick env & reachability checks:

```bash
# Library versions, config source, creds env
python -m src.probe_vertex

# Plus a real model call
python -m src.probe_vertex --call
```

---

## Extending

* **Add an atomic agent**: implement `invoke(state: dict) -> dict` (see `src/core/agent_protocol.py`).
* **Add a composite**: create a new module in `src/composite_agents/` that wires agents using builders in `src/chains/`.
* **Change routing**: edit `RouterAgent` (deterministic rule) or switch to LLM judging (`prompts/judge_router_prompt.py`).
* **Per-agent LLM tuning**: put overrides under `agents:` in YAML; `vertex.py` merges defaults + overrides.

---

## What’s Included (MVP)

* **Text-only** LCEL chain on Vertex AI Gemini
* **Composite** two-agent (+refiner) graph with deterministic routing
* **Clean ownership boundaries**:

  * `agents/` = atomic implementations
  * `chains/` = generic connection patterns
  * `composite_agents/` = team-maintained orchestrations
  * `config/` = environment-portable, no hardcoded project/key names
