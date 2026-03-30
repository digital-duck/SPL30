# SPL 3.0 — Momagrid as Compute OS

**SPL 3.0** extends SPL 2.0 with native workflow-to-workflow composition,
making the Momagrid Hub the orchestration backbone for multi-agent pipelines.

## The Vision

SPL is a synthesized programming language of three paradigms:

| Layer | Source | SPL construct |
|---|---|---|
| Data | SQL | SELECT, WITH, GENERATE (≈ query) |
| Logic | Python | CALL, @spl_tool, types |
| Orchestration | Linux shell | WORKFLOW composition |

SPL 2.0 covered the first two layers fully.
SPL 3.0 closes the third: `.spl` workflows compose like shell commands in a pipeline —
**declarative, testable, and portable across the Momagrid compute OS**.

## Momagrid as Compute OS

| OS concept | Momagrid equivalent |
|---|---|
| CPU core | Single GPU node |
| OS kernel | Momagrid Hub (schedules, IPC, workflow call stack) |
| Process | Running SPL WORKFLOW |
| System call | `CALL workflow_name()` → Hub dispatch |
| Shared memory | Hub workflow register (OUTPUT between call frames) |
| LAN | Single Hub + its GPU nodes |
| Internet (WAN) | Hub-to-Hub peering |
| Compute currency | Moma Points |

**SPL is the application layer** — same `.spl` file whether it runs locally,
on a LAN grid, or routes through a peer Hub on Oracle Cloud.

## What's New in SPL 3.0

### 1. Workflow-to-Workflow Composition

```sql
WORKFLOW code_pipeline
    INPUT: @spec TEXT
    OUTPUT: @final TEXT
DO
    CALL generate_code(@spec) INTO @code
    CALL review_code(@code)   INTO @feedback
    CALL test_code(@code)     INTO @test_result
    WHILE @quality < 0.9 DO
        CALL improve_code(@code, @feedback, @test_result) INTO @code
        GENERATE quality_judge(@code) INTO @quality
    END
    COMMIT @code
END
```

`CALL` already means "deterministic, synchronous, testable" — reused for workflow
dispatch. The callee may contain `GENERATE` internally; from the caller's perspective
the dispatch is deterministic.

### 2. Hub Workflow Registry

The Momagrid Hub maintains a workflow registry (name → definition).
`CALL workflow_name()` resolves via the Hub using the existing POST /tasks protocol
extended with a `"type": "workflow"` field — no new infrastructure needed.

### 3. Status → Exception Channel

OUTPUT is the data channel (single typed value).
Non-`complete` COMMIT status raises a typed exception in the calling scope:

```sql
CALL generate_code(@spec) INTO @code
EXCEPTION WHEN RefusalToAnswer THEN
    COMMIT 'Generation refused.' WITH status = 'blocked'
END
```

### 4. Hub-to-Hub Peering

Each Hub is an autonomous compute domain. Peering connects domains across WAN:
Oracle Cloud free tier becomes the first public peer Hub — identical protocol,
`peer_hub` routing field on the task payload.

### 5. IMPORT Directive

```sql
IMPORT 'lib/code_agents.spl'

WORKFLOW orchestrator
    INPUT: @spec TEXT
    OUTPUT: @result TEXT
DO
    CALL generate_code(@spec) INTO @result
END
```

### 6. CALL PARALLEL

```sql
CALL PARALLEL
    review_code(@code) INTO @feedback,
    test_code(@code)   INTO @test_result
END
```

Hub dispatches both sub-workflows concurrently to different nodes —
same mechanism as the existing multi-node task dispatch.

## Architecture

```
+---------------------------------------------+
|  SPL 3.0 Application Layer                  |
|  .spl workflows + IMPORT + CALL PARALLEL    |
+---------------------------------------------+
|  Momagrid Hub (Compute OS Kernel)           |
|  workflow registry | task queue | IPC       |
+--------------+------------------------------+
|  LAN nodes   |  Hub-to-Hub peering (WAN)    |
|  GPU nodes   |  Oracle Cloud / public Hubs  |
+--------------+------------------------------+
```

## Repository Layout

```
spl3/
    registry.py        # WorkflowRegistry (name -> definition)
    composer.py        # Workflow-to-workflow CALL dispatch
    hub_registry.py    # Hub-backed registry via REST
    peer.py            # Hub-to-Hub peering
    status.py          # COMMIT status -> EXCEPTION mapping

specs/
    grammar-additions.ebnf   # EBNF delta over SPL 2.0

cookbook/
    code_pipeline/     # generate -> review -> test -> improve (orchestrator)
    research_pipeline/ # search -> analyze -> summarize -> validate

docs/
    future-work.md     # Design notes and open questions

tests/
    test_registry.py
    test_composer.py
    test_status_mapping.py
    test_peer.py
```

## Quick Start

```bash
# Install (builds on spl-llm 2.0)
pip install -e ".[dev]"

# Register workflows with local registry
spl3 register cookbook/code_pipeline/

# Run an orchestrator workflow
spl3 run cookbook/code_pipeline/code_pipeline.spl \
    --adapter ollama --model gemma3 \
    --param spec="Write a Python function to parse JSON"

# Run with Hub registry (Momagrid)
spl3 run cookbook/code_pipeline/code_pipeline.spl \
    --adapter momagrid --hub http://localhost:8080
```

## Status

**SPL 3.0 is in design/scaffolding phase** (2026-03-30).
SPL 2.0 foundation: [arXiv](https://arxiv.org/abs/2602.21257)
Design notes: `docs/future-work.md`

## License

Apache 2.0
