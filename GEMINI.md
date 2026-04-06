# GEMINI.md - SPL 3.0 Project Context

## Project Overview
**SPL 3.0 (Semantic Programming Language)** is a synthesized programming language designed for multi-agent orchestration, framing the **Momagrid Hub** as a "Compute OS". It extends SPL 2.0 with native workflow-to-workflow composition, enabling complex agentic pipelines to be defined declaratively.

### Core Paradigms
- **Data (SQL):** `SELECT`, `WITH`, `GENERATE` (query-like LLM calls).
- **Logic (Python):** `CALL`, `@spl_tool`, typed variables, deterministic functions.
- **Orchestration (Linux):** Workflow pipelines, `IMPORT`, `CALL PARALLEL`, status-to-exception mapping.

### Key Architectural Concepts
- **Momagrid Hub:** The kernel that schedules tasks, manages IPC, and maintains the workflow call stack.
- **Workflow-to-Workflow Composition:** `CALL workflow_name()` allows one workflow to invoke another, with parameters and return values.
- **Event-Driven Execution:** `WorkflowInvocationEvent` ensures concurrency isolation and provides a queryable call tree (parent/child lineage).
- **Federated Registry:** A hybrid registry (`LocalRegistry` + `HubRegistry`) that resolves workflow definitions locally or via peer Hubs.
- **Code-RAG:** A specialized RAG index (`spl/code_rag.py`) that uses cookbook recipes as few-shot templates for Text2SPL generation.

## Technical Stack
- **Language:** Python 3.11+
- **Foundation:** `spl-llm >= 2.0.0` (Lexer, Parser, Executor, Adapters)
- **CLI:** `click`
- **Networking:** `httpx` (Hub/Peer communication)
- **Ecosystem (`dd-*` libs):**
  - `dd-llm`: Multi-provider LLM client.
  - `dd-vectordb`: Vector store (FAISS/Chroma) for Code-RAG.
  - `dd-db`: Database abstraction (SQLite/Postgres).
  - `dd-cache`: Disk/Memory caching.

## Key Directories & Files
- `spl/`: Core implementation.
  - `executor.py`: `SPL3Executor` (extends SPL 2.0 with new types and `CALL PARALLEL`).
  - `registry.py`: Workflow management (`LocalRegistry`, `FederatedRegistry`).
  - `composer.py`: Orchestrates multi-workflow dispatch.
  - `cli.py`: Main entry point (`spl` command).
  - `types.py`: Extended type system (`INT`, `FLOAT`, `NONE`, `SET`, `IMAGE`, `AUDIO`, `VIDEO`).
  - `code_rag.py`: Logic for indexing and querying SPL recipes.
- `cookbook/`: Reference implementations of agentic workflows (e.g., `code_pipeline`, `arxiv_morning_brief`).
- `specs/`: Grammar extensions (`grammar-additions.ebnf`) and versioned specs.
- `docs/`: Technical documentation and design notes (`ROADMAP.md`, `FEATURES.md`).
- `tests/`: Project tests using `pytest`.

## Development Workflows

### Building and Installation
```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Running Workflows
```bash
# Run a local .spl file
spl run cookbook/code_pipeline/code_pipeline.spl --param spec="Write a hello world in Python"

# Run with a specific Hub
spl run my_workflow.spl --hub http://localhost:8080
```

### Testing
- **Unit/Integration Tests:** Run via `pytest`.
- **Pipeline-level Tests:** Use `spl test <file_or_dir>`. This looks for `.test.yaml` files alongside `.spl` workflows.
  ```yaml
  # Example .test.yaml
  - name: "basic generation"
    params: { spec: "Hello world" }
    assert:
      contains: ["print"]
      status: complete
  ```

### Code-RAG Management
```bash
# Seed the index from the cookbook
spl code-rag seed cookbook/
# Query the index for patterns
spl code-rag query "How do I implement a judge-retry loop?"
```

## Coding Conventions
- **Extension, not replacement:** `SPL3Executor` must maintain backward compatibility with SPL 2.0.
- **Clean dependencies:** Prefer `dd-*` ecosystem libraries over bespoke wrappers for LLM, DB, and RAG tasks.
- **Strict Typing:** Leverage `SPL3Type` for parameter coercion and multimodal handling.
- **Idempotency:** Rely on `event_id` in `WorkflowInvocationEvent` for stable execution across retries.
- **Validation:** Every new feature should include both unit tests in `tests/` and a representative recipe in `cookbook/` with a corresponding `.test.yaml`.
