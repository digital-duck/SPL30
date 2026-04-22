"""Page 0: Text-to-Mermaid — visual intent validation.

Converts a natural language workflow description into a Mermaid diagram for
human approval before passing it to the Text2SPL compiler.  This catches
structural errors (wrong branching, missing loops, wrong agent boundaries)
early — before expensive SPL generation and splc compilation.

Pipeline:
  description → [LLM] → Mermaid diagram → user approves/refines
                                                    │
                                          session_state["mermaid_approved"]
                                                    │
                                         Text2SPL page reads it as context
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st
from streamlit_ace import st_ace

sys.path.insert(0, str(Path(__file__).parent.parent))
import db

db.init_db()

DIAGRAMS_DIR = Path(__file__).parent.parent / "data" / "diagrams"
DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────

ADAPTERS = [
    "claude_cli",
    "anthropic",
    "ollama",
    "openai",
    "openrouter",
    "google",
    "deepseek",
    "qwen",
]

MODELS: dict[str, list[str]] = {
    "claude_cli":  ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
    "anthropic":   ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
    "ollama":      ["gemma3", "llama3.2", "mistral", "phi3", "qwen2.5-coder"],
    "openai":      ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "openrouter":  ["meta-llama/llama-3.3-70b-instruct", "google/gemini-2.0-flash-001"],
    "google":      ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    "deepseek":    ["deepseek-chat", "deepseek-coder"],
    "qwen":        ["qwen-max", "qwen-plus"],
}

DIAGRAM_TYPES = ["auto", "flowchart TD", "flowchart LR", "sequenceDiagram", "stateDiagram-v2"]

EXAMPLES = [
    "build a self-refine agent that drafts, critiques, and refines until approved or 5 iterations",
    "triage a support ticket: classify severity, suggest a response, escalate if critical",
    "research a topic, summarize findings, check for factual consistency, then publish",
    "classify user intent and route to the correct handler workflow",
    "extract action items from a meeting transcript and assign owners",
]

# ── LLM prompt ─────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert at converting natural language descriptions of AI agent workflows
into Mermaid diagrams that will be used to generate SPL (Structured Prompt Language) code.

SPL concept → Mermaid node shape mapping:
  INPUT params        → parallelogram  [/text/]
  GENERATE (LLM call) → rectangle      [text]
  EVALUATE (decision) → diamond        {text}
  WHILE loop          → back-edge arrow with label
  CALL (tool/proc)    → rounded rect   ([text])
  COMMIT / RETURN     → parallelogram  [/text/]
  EXCEPTION handler   → hexagon        {{text}}
  Parallel branches   → subgraph block

Rules:
- Output ONLY valid Mermaid source, no prose, no code fences.
- Use flowchart TD for most workflows, flowchart LR for simple 2-3 step prompts,
  sequenceDiagram when multiple named agents interact.
- Label edges with data names or conditions (e.g. -- approved --> or -- @result -->).
- Show INPUT params as the first node(s).
- Show the final RETURN/COMMIT as the last node.
- Keep node labels concise (≤6 words).
"""

_GENERATE_PROMPT = """\
Convert this description to a Mermaid diagram.

Description: {description}

Output only the Mermaid source (no fences, no explanation).
"""

_REFINE_PROMPT = """\
Refine this Mermaid diagram based on the feedback below.

Original description: {description}

Current diagram:
{diagram}

Feedback: {feedback}

Output only the updated Mermaid source (no fences, no explanation).
"""

# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_mermaid(text: str) -> str:
    """Strip markdown code fences if the LLM wrapped the output."""
    text = text.strip()
    # Remove ```mermaid ... ``` or ``` ... ```
    m = re.search(r"```(?:mermaid)?\s*\n?([\s\S]+?)\n?```", text)
    if m:
        return m.group(1).strip()
    return text


def _mermaid_live_url(diagram: str) -> str:
    """Return a mermaid.live deep-link for the diagram."""
    payload = json.dumps({"code": diagram, "mermaid": {"theme": "default"}})
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"https://mermaid.live/edit#{encoded}"


def _render_mermaid(diagram: str, height: int = 500) -> None:
    """Render a Mermaid diagram in Streamlit via mermaid.js CDN."""
    escaped = diagram.replace("`", "&#96;").replace("\\", "\\\\")
    html = f"""
    <div id="mermaid-container" style="background:#fff;padding:16px;border-radius:8px;
         border:1px solid #e0e0e0;min-height:{height}px;">
      <pre class="mermaid" style="text-align:center;">{escaped}</pre>
    </div>
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{ startOnLoad: true, theme: 'default',
                            securityLevel: 'loose', logLevel: 'error' }});
      await mermaid.run();
    </script>
    """
    st.components.v1.html(html, height=height + 40, scrolling=True)


def _call_llm(prompt: str, adapter: str, model: str | None) -> str:
    """Call the LLM synchronously via the spl adapter layer."""
    try:
        # Import lazily — SPL30 may use spl3 or spl adapter paths
        try:
            from spl3.adapters import get_adapter
        except ImportError:
            from spl.adapters import get_adapter

        kwargs: dict = {}
        if model:
            kwargs["model"] = model

        llm = get_adapter(adapter, **kwargs)

        async def _gen() -> str:
            result = await llm.generate(
                prompt=prompt,
                system=_SYSTEM_PROMPT,
                max_tokens=1024,
                temperature=0.3,
            )
            return result.content

        return asyncio.run(_gen())
    except Exception as exc:
        return f"ERROR: {exc}"


def _save_diagram(description: str, diagram: str, adapter: str, model: str | None,
                  rounds: int) -> Path:
    """Persist an approved diagram to data/diagrams/ for audit trail."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^\w]+", "_", description[:40]).strip("_").lower()
    path = DIAGRAMS_DIR / f"{slug}_{ts}.mmd"
    meta = (
        f"---\n"
        f"description: {description}\n"
        f"adapter: {adapter}\n"
        f"model: {model or 'default'}\n"
        f"rounds: {rounds}\n"
        f"approved: {datetime.now().isoformat()}\n"
        f"---\n\n"
    )
    path.write_text(meta + diagram, encoding="utf-8")
    return path


# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Text2Mermaid", layout="wide")
st.header("Text → Mermaid Diagram")
st.caption(
    "Visualise your workflow intent before generating SPL.  "
    "Approve the diagram to pass it as a structural contract to the Text2SPL compiler."
)

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    with st.expander("LLM Settings", expanded=True):
        adapter = st.selectbox("Adapter", ADAPTERS, key="m_adapter")
        model_opts = MODELS.get(adapter or "", [])
        model = (
            st.selectbox("Model", model_opts, key="m_model")
            if model_opts
            else st.text_input("Model", key="m_model")
        )
        diagram_type = st.selectbox(
            "Diagram type",
            DIAGRAM_TYPES,
            key="m_dtype",
            help=(
                "**auto** — LLM chooses based on description  ·  "
                "**flowchart TD** — top-down, best for most workflows  ·  "
                "**sequenceDiagram** — multi-agent interactions"
            ),
        )
        max_refine = st.number_input(
            "Max refinement rounds", min_value=1, max_value=10, value=5, key="m_maxr"
        )

    with st.expander("Sample descriptions", expanded=False):
        for i, ex in enumerate(EXAMPLES, 1):
            st.write(f"{i}. {ex}")

    # ── Status of approved diagram ─────────────────────────────────────────────
    st.divider()
    if st.session_state.get("mermaid_approved"):
        st.success("Diagram approved ✓")
        st.caption("Text2SPL page will use it as structural context.")
        if st.button("Clear approval", key="btn_clear_approval"):
            for k in ("mermaid_approved", "mermaid_diagram", "mermaid_description",
                      "mermaid_rounds", "mermaid_saved_path"):
                st.session_state.pop(k, None)
            st.rerun()
    else:
        st.info("No diagram approved yet.")

# ── Session state defaults ─────────────────────────────────────────────────────

for key, default in [
    ("mermaid_diagram", ""),
    ("mermaid_approved", False),
    ("mermaid_description", ""),
    ("mermaid_rounds", 0),
    ("mermaid_error", ""),
    ("mermaid_saved_path", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Two-column layout ──────────────────────────────────────────────────────────

left, gap, right = st.columns([4, 0.3, 7])

with left:
    # ── Description ────────────────────────────────────────────────────────────

    description = st.text_area(
        "Workflow description",
        value=st.session_state.get("mermaid_description", ""),
        placeholder=EXAMPLES[0],
        height=130,
        key="m_description",
    )

    type_hint = ""
    if diagram_type != "auto":
        type_hint = f" Use diagram type: {diagram_type}."

    col_gen, col_rst = st.columns([3, 2])
    with col_gen:
        generate_clicked = st.button(
            "Generate diagram", type="primary", key="btn_generate",
            disabled=not description.strip(),
        )
    with col_rst:
        if st.button("Reset", key="btn_reset_m"):
            for k in ("mermaid_diagram", "mermaid_approved", "mermaid_description",
                      "mermaid_rounds", "mermaid_error", "mermaid_saved_path"):
                st.session_state.pop(k, None)
            st.rerun()

    if generate_clicked and description.strip():
        prompt = _GENERATE_PROMPT.format(description=description.strip() + type_hint)
        with st.spinner("Generating diagram…"):
            raw = _call_llm(prompt, adapter, model)
        diagram = _extract_mermaid(raw)
        if diagram.startswith("ERROR:"):
            st.session_state.mermaid_error = diagram
        else:
            st.session_state.update(
                mermaid_diagram=diagram,
                mermaid_description=description.strip(),
                mermaid_rounds=1,
                mermaid_approved=False,
                mermaid_error="",
            )
        st.rerun()

    if st.session_state.mermaid_error:
        st.error(st.session_state.mermaid_error)

    # ── Diagram source editor ───────────────────────────────────────────────────

    if st.session_state.mermaid_diagram:
        st.markdown(f"**Round {st.session_state.mermaid_rounds}** — edit source directly or provide feedback below")

        edited = st_ace(
            value=st.session_state.mermaid_diagram,
            language="markdown",
            theme="monokai",
            height=260,
            key="ace_mermaid",
            auto_update=True,
        )
        if edited and edited != st.session_state.mermaid_diagram:
            st.session_state.mermaid_diagram = edited
            st.session_state.mermaid_approved = False

        # ── Feedback / Refine ───────────────────────────────────────────────────

        st.divider()
        rounds_used = st.session_state.mermaid_rounds
        rounds_left = max_refine - rounds_used

        feedback = st.text_area(
            "Feedback for refinement",
            placeholder="e.g. Add a deduplication check before classification, use sequenceDiagram instead",
            height=90,
            key="m_feedback",
            disabled=(rounds_left <= 0),
        )

        col_ref, col_app = st.columns([3, 3])

        with col_ref:
            refine_clicked = st.button(
                f"Refine ({rounds_left} left)",
                key="btn_refine",
                disabled=(not feedback.strip() or rounds_left <= 0),
            )

        with col_app:
            approve_clicked = st.button(
                "✓ Approve & use in Text2SPL",
                type="primary",
                key="btn_approve",
            )

        if refine_clicked and feedback.strip():
            prompt = _REFINE_PROMPT.format(
                description=st.session_state.mermaid_description,
                diagram=st.session_state.mermaid_diagram,
                feedback=feedback.strip(),
            )
            with st.spinner("Refining…"):
                raw = _call_llm(prompt, adapter, model)
            diagram = _extract_mermaid(raw)
            if diagram.startswith("ERROR:"):
                st.session_state.mermaid_error = diagram
            else:
                st.session_state.update(
                    mermaid_diagram=diagram,
                    mermaid_rounds=rounds_used + 1,
                    mermaid_approved=False,
                    mermaid_error="",
                )
            st.rerun()

        if approve_clicked:
            saved_path = _save_diagram(
                description=st.session_state.mermaid_description,
                diagram=st.session_state.mermaid_diagram,
                adapter=adapter,
                model=model,
                rounds=st.session_state.mermaid_rounds,
            )
            st.session_state.update(
                mermaid_approved=True,
                mermaid_saved_path=str(saved_path),
            )
            st.rerun()

        if st.session_state.mermaid_approved:
            st.success(f"Approved ✓ — saved to `{st.session_state.mermaid_saved_path}`")
            st.info("Navigate to **Text2SPL** — the diagram will be injected as structural context.")

        if rounds_left <= 0 and not st.session_state.mermaid_approved:
            st.warning(f"Max refinement rounds ({max_refine}) reached. Edit directly or approve.")

        # ── mermaid.live link ───────────────────────────────────────────────────

        live_url = _mermaid_live_url(st.session_state.mermaid_diagram)
        st.markdown(f"[Open in mermaid.live ↗]({live_url})", unsafe_allow_html=False)

with right:
    # ── Rendered diagram ────────────────────────────────────────────────────────

    if st.session_state.mermaid_diagram:
        border_color = "#4CAF50" if st.session_state.mermaid_approved else "#e0e0e0"
        label = "✓ Approved" if st.session_state.mermaid_approved else "Preview"
        st.markdown(
            f"<p style='font-weight:600;color:{'#4CAF50' if st.session_state.mermaid_approved else '#555'}'>"
            f"{label}</p>",
            unsafe_allow_html=True,
        )
        _render_mermaid(st.session_state.mermaid_diagram, height=520)
    else:
        st.info("Rendered diagram will appear here after generation.")

# ── Approved diagram history ───────────────────────────────────────────────────

saved_files = sorted(DIAGRAMS_DIR.glob("*.mmd"), reverse=True)
if saved_files:
    with st.expander(f"Approved diagram history ({len(saved_files)})", expanded=False):
        for f in saved_files[:10]:
            content = f.read_text(encoding="utf-8")
            # Extract frontmatter description
            m = re.search(r"description:\s*(.+)", content)
            desc_label = m.group(1).strip() if m else f.stem
            col_a, col_b = st.columns([6, 2])
            with col_a:
                with st.expander(f"`{f.name}`  —  {desc_label[:60]}"):
                    # Strip frontmatter for display
                    body = re.sub(r"^---[\s\S]+?---\n\n", "", content).strip()
                    st.code(body, language="markdown")
                    if st.button("Load into editor", key=f"load_{f.name}"):
                        st.session_state.update(
                            mermaid_diagram=body,
                            mermaid_approved=False,
                            mermaid_description=desc_label,
                            mermaid_rounds=0,
                        )
                        st.rerun()
            with col_b:
                st.caption(f.stat().st_mtime and
                           datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M"))
