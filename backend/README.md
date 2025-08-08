# Vertex AI × LangChain — Minimal Chain (No Agents/No Tools)

A tiny, multi-file skeleton that runs a **single LangChain chain** on **Vertex AI (Gemini)** from your local machine. No agents, no tools—just `prompt | model | parser` (LCEL). Clean, documented, and ready to extend.

## Highlights

* **LCEL minimalism:** `ChatPromptTemplate → ChatVertexAI → StrOutputParser`.
* **Stable text I/O:** `response_mime_type="text/plain"`.
* **Credential strategy:**

  * **Local default:** explicitly load a Service Account (SA) JSON.
  * **Cloud switch:** set `USE_ADC=true` to use Application Default Credentials (ADC).
* **Pinned, known-good versions** for reproducible runs.

## Repo Layout

```
.
├─ src/
│  ├─ .keys/               # privite key folder for testing
│  ├─ config.py            # Project/region/model; explicit SA loader; USE_ADC switch
│  ├─ llm/
│  │  └─ vertex.py         # vertexai.init + ChatVertexAI wiring
│  ├─ prompts/
│  │  └─ base_prompt.py    # Minimal system+user prompt
│  ├─ schemas/
│  │  └─ io.py             # Pydantic I/O schemas
│  ├─ chains/
│  │  └─ simple_chain.py   # LCEL chain factory
│  └─ runner/
│     └─ run_simple.py     # CLI entrypoint
└─ requirements.txt
```

## Requirements

* Python **3.11 or 3.12** (recommended)
* Google Cloud project/region with Vertex AI enabled

  * `project = aime-hello-world`
  * `location = us-central1`
* SA key placed at: `src/.keys/aime-hello-world-2cd68fc662f2.json`

### Python packages (pinned)

```
langchain==0.3.27
langchain-core==0.3.72
langchain-google-vertexai==2.0.28
google-cloud-aiplatform==1.107.0
pydantic>=2.7,<3
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Credentials

* **Do not commit keys.** Keep your SA JSON at `src/.keys/...` (already referenced by `config.py`).
* Local runs **explicitly** load the key and pass credentials to both `vertexai.init` and `ChatVertexAI`.
* Cloud runs (Cloud Run/GKE) can switch to **ADC** via an env var.

## Run Locally (MVP)

```bash
python -m src.runner.run_simple --input "Say exactly: OK."
```

**Expected output**

```json
{
  "text": "OK."
}
```

## Probe Mode (optional)

A quick preflight to verify model reachability and text channel.

```bash
python -m src.runner.run_simple --input "__probe__"
```

## Switch Between Local SA and Cloud ADC

* **Local SA (default):** no env needed; `config.py` loads `src/.keys/...` and injects credentials.
* **Cloud ADC:** set env var and deploy with a service account that has `roles/aiplatform.user`.

```bash
export USE_ADC=true
```

## Configuration Knobs

* **Project/region/model:** `src/config.py`

  * `project="aime-hello-world"`, `location="us-central1"`
  * `model_name="gemini-2.0-flash"` (stable, widely available)
* **Generation params:** `temperature`, `max_output_tokens`
* **Prompt:** `src/prompts/base_prompt.py`

## What’s Working (MVP)

* End-to-end LCEL chain returns stable plain-text via Vertex AI Gemini:

  * Local run with **explicit SA credentials**
  * Optional cloud run with **ADC**
* Minimal CLI produces JSON output suitable for piping to a frontend.
