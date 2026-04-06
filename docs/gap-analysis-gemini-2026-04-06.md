# SPL 3.0 Gap Analysis: Roadmap vs. Implementation

**Date:** April 6, 2026  
**Status:** Internal Review  
**Author:** Gemini CLI  
**Context:** Grounding the DODA (Design Once, Deploy Anywhere) vision for the ArXiv:2604 preprint and production deployment on Intel Mini-PC / Momagrid.

---

## Executive Summary

The core orchestration layer for SPL 3.0 (workflow composition, `CALL PARALLEL`, and the `WorkflowInvocationEvent` model) is implemented and stable. However, there are significant gaps in the **Physical Layer** (`splc`) and **Multi-Modal Integration** required to fulfill the "Forest" evolution described in the project roadmap.

## 1. Multi-Modal Support (Priority: High / ArXiv Requirement)

**Current Status:** Grammar and type system defined. Execution is text-only.

| Gap | Description | Impact |
|:---|:---|:---|
| **Adapter Implementation** | `LiquidAdapter` (LFM-2) and other adapters do not yet implement the `MultiModalMixin` or `generate_multimodal`. | Cannot run `vision.analyze()` or `audio.listen()` on local LFM models. |
| **Executor Integration** | `SPL3Executor` passes `IMAGE/AUDIO/VIDEO` params as strings (paths) but lacks the logic to trigger multimodal-specific adapter methods. | Multimodal parameters are ignored or treated as plain text in the execution loop. |
| **Codec Layer** | Missing `spl/codecs/` to handle raw data (PIL, WAV, MP4) → `ContentPart` (base64/URL) conversion. | Developers must manually handle base64 encoding in the logic layer. |
| **MMU Budgeting** | The `WITH BUDGET` optimizer does not yet account for Multi-Modal Units (MMU) for media encoders. | Inaccurate token/cost attribution for multimodal workflows. |

## 2. `splc` Compiler Expansion (Priority: High / DODA Vision)

**Current Status:** Scaffolding exists for Go/Python/LangGraph targets. No hardware awareness.

| Gap | Description | Impact |
|:---|:---|:---|
| **Hardware-Aware Targeting** | `splc` lacks logic to detect node silicon (Intel iGPU, Apple Metal, NVIDIA) and auto-select quantization. | The "Java Moment" is currently manual; developers must specify quantization and runtime profiles. |
| **Go + OpenVINO** | The `--target go` backend does not yet include the CGO bindings for OpenVINO high-density inference. | Intel Mini-PCs cannot yet reach their theoretical maximum batch throughput for banking/batch services. |
| **Swift + Metal** | No backend for Apple M4/M5 Unified Memory architectures. | Performance on Apple Silicon is limited to generic Python/Ollama execution. |
| **Dynamic Fallback** | The "Resolute Path" (local → sparse → cloud) is not embedded in the compiled artifact. | Workflows are not resilient to local hardware failure or resource exhaustion. |

## 3. Snap Inference & Ubuntu 26.04 (Priority: Deferred)

**Current Status:** Concept defined in ROADMAP.md.

- **Status:** Implementation is delayed until late April 2026 to align with the **Ubuntu 26.04 "Resolute Raccoon"** release.
- **Dependency:** Waiting for the final stable schema of the `inference-snap` interface to ensure immutable weights and logic can be bundled effectively.

## 4. text2SPL & Tooling Gaps

| Gap | Description | Impact |
|:---|:---|:---|
| **Agentic Pattern RAG** | The RAG store is populated with SPL 2.0 single-workflow recipes. | `text2spl` struggle to generate multi-workflow orchestrator patterns from NL intent. |
| **`spl test` Pipeline** | Mocking logic for multi-workflow `CALL` chains and multimodal input/output is not fully implemented. | End-to-end testing of complex orchestrators requires a live Hub and real models. |

---

## Immediate Implementation Roadmap

Based on the ArXiv submission timeline and the "Forest" deployment goals:

1.  **Phase 1 (Multimodal):** Implement `generate_multimodal` in `LiquidAdapter` and create `spl/codecs/` for automated media-to-base64 conversion.
2.  **Phase 2 (`splc` Expansion):** Prototype the `go + OpenVINO` target to demonstrate production-grade batch inference on the Intel Mini-PC fleet.
3.  **Phase 3 (Pattern Library):** Seed the RAG store with native SPL 3.0 agentic patterns (e.g., orchestrator workflows using `CALL PARALLEL`).
