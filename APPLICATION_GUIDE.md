# 2agent — Simple Application Guide

This document explains what the application does, what happens when you use it, and where each part of the code lives.

## 1. What is this application?

**2agent (BRD Copilot)** takes a Business Requirements Document (BRD), extracts its contents, turns the requirements into structured JSON, checks that JSON, and uses it to suggest a workflow and the agent capabilities needed for the work.

After processing, you can inspect the result and ask follow-up questions in the chat interface.

It is important to distinguish **planning** from **execution**: the current workflow creates a proposed workflow plan and identifies matching agent capabilities. It does not execute every task in that generated plan.

## 2. The whole flow at a glance

```text
User
  |
  v
Streamlit UI (ui/app.py)
  |  uploads the BRD
  v
FastAPI (api/routes.py)
  |
  v
Supervisor (agents/supervisor.py)
  |
  +--> ExtractorService (services/extractor_service.py)
  |      |
  |      +--> existing extractor.py
  |      |      - reads document text
  |      |      - performs OCR for supported images
  |      |      - extracts embedded files and images
  |      |      - optionally downloads external document links
  |      |      - processes discovered files recursively
  |      |
  |      +--> normalized document data + source lineage
  |
  v
LangGraph workflow (graph/workflow_graph.py)
  |
  +--> 1. JSON generator
  +--> 2. Validator
  |       |-- invalid --> stop further analysis
  |       '-- valid
  +--> 3. Reasoning agent
  +--> 4. Workflow planner
  +--> 5. Agent identifier
  +--> 6. Usage summary
  |
  v
Saved session + generated JSON
  |
  v
Streamlit shows results; user can ask follow-up questions
  |
  v
Copilot reads stored knowledge and asks Azure OpenAI for an answer
```

## 3. What happens when I upload a document?

### Step 1 — The UI sends the file

**File:** `ui/app.py`

The Streamlit page lets you select a BRD and click **Generate Knowledge Base**. It sends the file to the backend's `POST /api/v1/documents` endpoint. The UI uses `BRD_API_URL` if set; otherwise, it expects the API at `http://localhost:8000/api/v1`.

### Step 2 — The API checks and stores the upload

**File:** `api/routes.py`

The API accepts a limited set of file extensions and checks the configured maximum upload size. It calculates a SHA-256 hash and stores the uploaded bytes under a hash-based filename, avoiding a duplicate write if that file is already present.

It then creates a new session ID and calls the supervisor. Processing currently happens synchronously inside the upload request, so the request stays open while the pipeline runs.

### Step 3 — The supervisor runs extraction once

**Files:** `agents/supervisor.py`, `services/extractor_service.py`, `extractor.py`

The supervisor creates a document ID and asks `ExtractorService` to process the file. The service loads a fresh instance of the existing root-level `extractor.py`, configures its input and output paths, and calls its `main()` function.

The extractor attempts to read text from the document. Depending on the file type and its contents, it can also:
- run OCR on supported image files;
- extract embedded documents and images from supported PDF and Office files;
- find external hyperlinks in Office documents and attempt to download linked files, subject to configuration and access permissions;
- recursively process extracted or downloaded child files;
- record errors and the status of external links.

The service then converts the extractor's output into a consistent document state and builds a source-lineage graph. The lineage graph records which file contained or linked to another file. It is about **where content came from**, not proof that every extracted statement is true.

### Step 4 — The JSON generator structures the BRD

**Files:** `graph/nodes.py`, `agents/json_generator.py`, `prompts/generator_prompt.py`, `schemas/brd_schema.py`

The first LangGraph node passes the extracted document state and the expected BRD schema to the Azure OpenAI service. The model is instructed to return JSON that organizes information such as:
- business, functional, and non-functional requirements;
- workflows and stakeholders;
- dependencies, constraints, risks, and assumptions;
- acceptance criteria and confidence scores.

The prompt tells the model not to invent missing facts and to attach source references where evidence exists. This is an instruction to the model, not a guarantee; the next step checks structural consistency.

### Step 5 — The validator checks the generated JSON

**Files:** `agents/validator.py`, `graph/nodes.py`

This stage uses deterministic code and the BRD JSON Schema. It checks the schema, requirement IDs, duplicate IDs, and whether requirement confidence values are numeric and between 0 and 1.

- **If there are errors:** the workflow records a failed validation stage and skips reasoning and planning.
- **If validation passes:** the validated JSON becomes the input to the next stage.

The reported score is a simple structural score based on the number of errors and warnings. It is **not** an LLM confidence score and does not independently establish that every requirement is factually correct. The code currently leaves some reference checks as a TODO.

### Step 6 — The reasoning agent analyzes the validated requirements

**Files:** `agents/reasoning_agent.py`, `prompts/reasoning_prompt.py`

The model receives the validated BRD JSON and returns a structured analysis. The prompt asks it to identify business processes, actors, dependencies, tasks, system interactions, automation opportunities, required tools, and required capabilities. It is told to refer to requirement IDs and source references and to separate supported conclusions from inferences.

This is analysis generated by the model; it does not change the validated BRD itself.

### Step 7 — The workflow planner proposes an ordered plan

**Files:** `agents/workflow_planner.py`, `services/workflow_service.py`, `prompts/planner_prompt.py`

The planner asks the model to produce workflow nodes and dependency edges. The Python validation function checks that node IDs exist and are unique, edges refer to known nodes, and no node depends on itself. It then uses topological sorting to calculate an execution order. If it detects invalid JSON or an invalid graph, the planner retries up to three times.

A valid result is a **proposed plan**. The current graph does not run the tasks in that plan.

### Step 8 — The agent identifier matches capabilities

**Files:** `agents/agent_identifier.py`, `graph/nodes.py`

This is a deterministic catalog lookup, not another LLM call. It compares the reasoning output's `required_capabilities` against the capabilities listed in a fixed catalog and returns entries that match exactly (ignoring case).

This produces a list of relevant catalog entries. It does not dynamically create, deploy, or execute new agents.

### Step 9 — The workflow records usage and saves the session

**Files:** `graph/nodes.py`, `services/token_tracker.py`, `services/persistence.py`, `agents/supervisor.py`

Every model call is recorded with token counts and an estimated cost. Workflow nodes append audit events that include the timestamp, agent, action, session ID, and document ID.

After the graph completes, the supervisor saves the session and generated JSON to local JSON files under the configured storage directory. This repository is a simple local-development persistence layer, not a transactional production database.

The upload endpoint returns the session ID, document ID, current stage, and validation report.

## 4. What happens when I ask a chat question?

**Files:** `api/routes.py`, `agents/copilot_agent.py`

1. The UI sends the session ID and question to `POST /api/v1/chat`.
2. The Copilot loads the saved session and the stored knowledge for that document.
3. It provides the model with stored validated/generated JSON, the validation report, the workflow plan, identified agents, and lineage information when available.
4. It adds up to the last eight saved chat messages to the prompt, plus the new question.
5. The model answers using that supplied context. The prompt tells it to say when facts are unavailable and not to claim it performed a new extraction or workflow run.
6. The app saves the chat history and audit event, then returns the answer and usage summary.

The chat feature is intended to explain or query the stored result. It does not reprocess the uploaded document for each question.

## 5. API endpoints

| Method | Endpoint | What it does |
| --- | --- | --- |
| GET | `/health` | Returns a basic health status. |
| POST | `/api/v1/documents` | Uploads and processes a supported document. |
| GET | `/api/v1/sessions/{session_id}` | Returns session status, workflow plan, validation report, identified agents, usage, and audit log. |
| GET | `/api/v1/sessions/{session_id}/knowledge` | Returns saved generated knowledge JSON. |
| POST | `/api/v1/chat` | Answers a question using stored session knowledge. |
| GET | `/api/v1/sessions/{session_id}/usage` | Returns token usage for a session. |

## 6. Where to look in the code

| Path | Responsibility |
| --- | --- |
| `ui/app.py` | Streamlit upload, result display, and chat UI. |
| `api/main.py` | Creates the FastAPI application and health endpoint. |
| `api/routes.py` | HTTP endpoints, upload validation, and API responses. |
| `api/dependencies.py` | Creates shared supervisor and Copilot instances. |
| `agents/supervisor.py` | Starts extraction, invokes the graph, and persists final state. |
| `services/extractor_service.py` | Adapter around the existing document extractor. |
| `extractor.py` | Actual file parsing, OCR, embedded-file extraction, and recursive processing. |
| `graph/workflow_graph.py` | Defines the order and branching of the workflow stages. |
| `graph/nodes.py` | Connects each agent to LangGraph state and records audit transitions. |
| `agents/json_generator.py` | Asks the model to turn extracted content into BRD JSON. |
| `agents/validator.py` | Performs deterministic schema and requirement-ID checks. |
| `agents/reasoning_agent.py` | Generates structured reasoning from validated BRD JSON. |
| `agents/workflow_planner.py` | Generates and retries workflow plans. |
| `services/workflow_service.py` | Validates workflow dependency graphs and orders nodes. |
| `agents/agent_identifier.py` | Matches capabilities against a fixed agent catalog. |
| `agents/copilot_agent.py` | Answers follow-up questions from stored state. |
| `services/azure_openai_service.py` | Sends chat-completion requests and tracks usage. |
| `services/persistence.py` | Saves and loads local JSON records. |
| `services/lineage_service.py` | Builds and searches the source-file lineage graph. |
| `services/token_tracker.py` | Aggregates token usage and estimated cost. |
| `state/document_state.py`, `state/workflow_state.py` | Define the data passed between stages. |
| `schemas/brd_schema.py` | Describes the expected BRD JSON structure. |
| `config.py` | Application settings and storage defaults. |

## 7. Run it locally

The repository contains a Streamlit UI and a FastAPI backend. From the project root:

1. Create and activate a Python virtual environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Configure the Azure OpenAI endpoint, API key, API version, and deployment using environment variables or the project's supported configuration.
4. Start the API: `uvicorn api.main:app --reload`.
5. In another terminal, start the UI: `streamlit run ui/app.py`.

By default the UI calls `http://localhost:8000/api/v1`. Set `BRD_API_URL` if the backend is hosted elsewhere.

Check `/health` to confirm the API process has started. A healthy endpoint alone does not prove the model credentials or full document pipeline work; upload a small test document to verify those.

## 8. Important limitations to know

- **Model output can be wrong.** Schema validation catches structural issues, not all factual errors.
- **Workflow plan is not task execution.** The planner returns an ordered plan; the graph stops after planning and catalog-based agent identification.
- **Some source checks are incomplete.** The validator has TODO comments for deeper reference validation.
- **Local JSON storage is for development.** The persistence implementation itself recommends database transactions and per-session locking for production.
- **Upload processing is synchronous.** Large documents can keep the HTTP request open; the route comments recommend a background job for production.
- **External links may not be accessible.** Downloads depend on the link being reachable and any necessary permissions/configuration.
- **Costs are estimates.** They depend on configured per-token prices and may be zero if those prices remain at their defaults.
- **Do not expose credentials.** Keep Azure OpenAI secrets out of source control. Before using this application, move any hard-coded credentials in `services/azure_openai_service.py` to environment-based settings, rotate any key that has been committed, and remove the committed secret from the code/history as appropriate.

## 9. One-sentence mental model

**The app extracts a BRD, converts it into checked structured data, analyzes that data to propose a dependency-ordered workflow and relevant agent capabilities, saves the result, and lets you ask questions about it.**
