"""Page 1: Text-to-SPL compiler.

Compile a natural language description into SPL 2.0, inspect the generated
code, provide runtime inputs, and execute — all persisted to knowledge.db.

Each (description → SPL) pair is saved under a logical name.  Re-using the
same name auto-increments the version, so you can iterate on a description
without losing previous attempts.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import streamlit as st
from streamlit_ace import st_ace

sys.path.insert(0, str(Path(__file__).parent.parent))
import db
import code_rag_bridge as rag
import spl3_rag_bridge as spl3_rag

db.init_db()

SCRIPTS_DIR = Path(__file__).parent.parent / "data" / "scripts"
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

ADAPTERS = [
    "ollama",
    "claude_cli",
    "anthropic",
    "openai",
    "openrouter",
    "google",
    "deepseek",
    "qwen",
    "bedrock",
    "vertex",
    "azure_openai",
]

# Default model options per adapter (first entry = default)
MODELS: dict[str, list[str]] = {
    "ollama":      ["gemma3", "llama3.2", "mistral", "phi3", "qwen2.5-coder", "deepseek-coder"],
    "claude_cli":  ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
    "anthropic":   ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
    "openai":      ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "openrouter":  ["meta-llama/llama-3.3-70b-instruct", "google/gemini-2.0-flash-001", "anthropic/claude-sonnet-4-6"],
    "google":      ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    "deepseek":    ["deepseek-chat", "deepseek-coder"],
    "qwen":        ["qwen-max", "qwen-plus", "qwen-turbo"],
    "bedrock":     ["us.amazon.nova-pro-v1:0", "us.anthropic.claude-3-5-sonnet-20241022-v2:0"],
    "vertex":      ["gemini-2.0-flash-001", "gemini-1.5-pro-002", "gemini-1.5-flash-002"],
    "azure_openai":["gpt-4o", "gpt-4o-mini"],
}

EXAMPLES = {
    "auto":     "classify user intent and route to the right handler",
    "prompt":   "summarize a document with a 2000 token budget",
    "workflow": "build a review agent that drafts, critiques, and refines text until quality > 0.8",
}


def _parse_run_output(stdout: str) -> dict:
    """Extract metrics and LLM output from spl run stdout."""
    lines = stdout.splitlines()
    meta: dict[str, str] = {}
    output_lines: list[str] = []
    in_output = False

    for line in lines:
        s = line.strip()
        # Separator bars (60 = or - signs)
        if s and all(c == "=" for c in s) and len(s) >= 20:
            if in_output:
                in_output = False
            continue
        if s and all(c == "-" for c in s) and len(s) >= 20:
            in_output = True
            continue
        # Skip markdown code fences that spl run wraps output in
        if s.startswith("```"):
            continue
        if in_output:
            output_lines.append(line)
        elif s.startswith("Model: "):
            meta["model"] = s[7:]
        elif s.startswith("Tokens: "):
            parts = s[8:].split(" in / ")
            meta["tokens_in"] = parts[0]
            meta["tokens_out"] = parts[1].replace(" out", "") if len(parts) > 1 else ""
        elif s.startswith("Latency: "):
            meta["latency"] = s[9:]
        elif s.startswith("Cost: "):
            meta["cost"] = s[6:]
        elif s.startswith("LLM Calls: "):
            meta["llm_calls"] = s[11:]
        elif s.startswith("Status: "):
            meta["status"] = s[8:]

    return {"meta": meta, "output": "\n".join(output_lines).strip()}


def _slugify(text: str) -> str:
    """Derive a snake_case name from a description (first 4 meaningful words)."""
    stop = {"a", "an", "the", "with", "for", "to", "of", "and", "or", "that", "until"}
    clean = re.sub(r"[^\w\s]", "", text.lower())
    words = [w for w in clean.split() if w not in stop]
    return "_".join(words[:4]) or "script"


# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Text-to-SPL", layout="wide")
st.header("Generate SPL from Text")
st.caption("Compile a natural language description into SPL 2.0, then run it.")

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    with st.expander("Compiler (text2spl)", expanded=False):
        c_adapter = st.selectbox("Adapter", ADAPTERS, index=ADAPTERS.index("claude_cli"), key="c_adapter")
        c_models = MODELS.get(c_adapter or "", [])
        c_model = st.selectbox("Model", c_models, key="c_model") if c_models else st.text_input("Model", key="c_model")
        st.caption(f"`{c_adapter}` / `{c_model}`")
        use_code_rag = st.checkbox(
            "Use Code-RAG",
            value=True,
            key="use_code_rag",
            help="Inject similar examples from the Code-RAG store into the compiler prompt. Uncheck to compile from scratch.",
        )

    with st.expander("Runtime (spl run)", expanded=False):
        r_adapter = st.selectbox("Adapter", ADAPTERS, index=0, key="r_adapter")
        r_models = MODELS.get(r_adapter or "", [])
        r_model = st.selectbox("Model", r_models, key="r_model") if r_models else st.text_input("Model", key="r_model")
        st.caption(f"`{r_adapter}` / `{r_model}`")

    mode = st.radio(
        "Mode",
        ["auto", "prompt", "workflow"],
        key="mode",
        help=(
            "**prompt** — single GENERATE statement  ·  "
            "**workflow** — multi-step with control flow  ·  "
            "**auto** — LLM decides the best form"
        ),
    )

    with st.expander("Sample Texts", expanded=False):
        st.markdown("**Prompts**")
        sample_prompts = [
            "say hello in 5 most popular languages in the world",
            "summarize a document with a 2000 token budget",
            "translate a product description into French, German, and Japanese",
            "extract key action items and owners from a meeting transcript",
            "rate the sentiment of a customer review and explain the reasoning",
        ]
        for n, text in enumerate(sample_prompts):
            st.write(f"{n+1}. {text}")

        st.markdown("**Workflows**")
        sample_workflows = [
            "classify user intent and route to the right handler",
            "build a review agent that drafts, critiques, and refines text until quality > 0.8",
            "research a topic, generate a structured report, and check it for factual consistency",
            "triage a support ticket: classify severity, suggest a response, and escalate if critical",
            "generate a blog post outline, expand each section, then produce an SEO-optimized title",
        ]
        for n, text in enumerate(sample_workflows):
            st.write(f"{n+1}. {text}")


# ── Session state ──────────────────────────────────────────────────────────────

for key, default in [
    ("spl_code", None),
    ("spl_file", None),
    ("script_id", None),
    ("compile_error", None),
    ("saved_name", None),
    ("saved_version", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Two-column layout ──────────────────────────────────────────────────────────

left, _, right = st.columns([4, 0.4, 7])

with left:
    # ── Description ────────────────────────────────────────────────────────────

    description = st.text_area(
        "Description",
        placeholder=EXAMPLES.get(mode or "", ""),
        height=120,
        key="description",
    )

    # ── Script name + version preview ──────────────────────────────────────────

    desc_val = description.strip() or EXAMPLES.get(mode or "", "")
    suggested = _slugify(desc_val)

    name_input = st.text_input(
        "Script name",
        value=suggested,
        key="script_name",
        help=(
            "Logical name for this script (snake_case recommended).  "
            "Leave blank to auto-derive from the description.  "
            "Re-using the same name creates a new version instead of overwriting."
        ),
    )
    effective_name = name_input.strip() or suggested
    cur_v = db.current_version(effective_name)

    chk_col, btn_col, rst_col = st.columns([3, 2, 2])
    with chk_col:
        overwrite = st.checkbox(
            "Overwrite",
            value=False,
            disabled=(cur_v is None),
            key="overwrite",
            help="When checked, the latest saved version is updated in-place instead of creating a new one.",
        )
    with btn_col:
        compile_clicked = st.button("Compile", type="primary", key="btn_compile")
    with rst_col:
        if st.button("Reset", key="btn_reset"):
            reset_keys = {"spl_code", "spl_file", "script_id", "compile_error",
                          "saved_name", "saved_version", "description", "script_name"}
            for k in list(st.session_state.keys()):
                if k in reset_keys or (isinstance(k, str) and k.startswith("param_")):
                    del st.session_state[k]
            st.rerun()

    if overwrite and cur_v is not None:
        st.caption(f"Will overwrite: **{effective_name}** v{cur_v}")
    else:
        next_v = 1 if cur_v is None else cur_v + 1
        st.caption(
            f"Will save as: **{effective_name}**  "
            f"{'v1 (new)' if next_v == 1 else f'v{next_v} (revision of v{next_v - 1})'}"
        )

    if compile_clicked:
        desc = desc_val
        if not desc:
            st.warning("Enter a description first.")
        else:
            file_version = cur_v if (overwrite and cur_v) else (1 if cur_v is None else cur_v + 1)
            spl_file = SCRIPTS_DIR / f"{effective_name}_v{file_version}_{uuid.uuid4().hex[:6]}.spl"
            cmd = [
                "spl", "text2spl", desc,
                "--mode", mode,
                "--no-validate",
                "-o", str(spl_file),
                "--adapter", c_adapter,
                "-m", c_model,
            ]
            if not use_code_rag:
                cmd.append("--no-code-rag")

            with st.spinner("Compiling…"):
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if spl_file.exists():
                spl_code = spl_file.read_text()
                script_id = db.save_script(
                    name=effective_name,
                    description=desc,
                    mode=mode or "auto",
                    spl_code=spl_code,
                    spl_file=str(spl_file),
                    compiler_adapter=c_adapter,
                    compiler_model=c_model or None,
                    overwrite=overwrite,
                )
                st.session_state.update(
                    spl_code=spl_code,
                    spl_file=str(spl_file),
                    script_id=script_id,
                    compile_error=None,
                    saved_name=effective_name,
                    saved_version=file_version,
                )
            else:
                st.session_state.update(
                    spl_code=None,
                    spl_file=None,
                    script_id=None,
                    compile_error=proc.stderr or proc.stdout or "Generation failed.",
                )

    if st.session_state.compile_error:
        st.error(st.session_state.compile_error)

btn_run: bool = False

with right:
    # ── Generated SPL ───────────────────────────────────────────────────────────

    if st.session_state.spl_code:
        saved = st.session_state.saved_name
        ver = st.session_state.saved_version
        # st.subheader(f"{saved} v{ver}")
        with st.expander(f"Generated SPL code: {saved} v{ver}", expanded=True):
            edited_spl = st_ace(
                value=st.session_state.spl_code,
                language="sql",
                theme="monokai",
                height=300,
                key="ace_spl_code",
                auto_update=True,
            )
            if edited_spl and edited_spl != st.session_state.spl_code:
                st.session_state.spl_code = edited_spl
                if st.session_state.spl_file:
                    Path(st.session_state.spl_file).write_text(edited_spl)

        c1, c2 = st.columns([1, 8])
        with c1:
            btn_run = st.button("Run", type="primary", key="btn_run")

        with c2:

            # Determine which RAG sources are available
            _rag_sources: list[tuple[str, list[dict]]] = []
            if rag.is_available() and rag.count() > 0:
                _rag_sources.append(("knowledge.db Code-RAG", rag.query(desc_val, top_k=4)))
            if spl3_rag.is_available():
                _rag_sources.append(("SPL3 Cookbook RAG", spl3_rag.query(desc_val, top_k=3)))

            if _rag_sources:
                with st.expander("RAG context used for compilation", expanded=False):
                    for src_label, hits in _rag_sources:
                        st.caption(f"**Source: {src_label}**")
                        if not hits:
                            st.caption("No similar examples found.")
                        else:
                            for i, h in enumerate(hits, 1):
                                sim = max(0.0, (1.0 - h["score"]) * 100)
                                st.markdown(
                                    f"**#{i}** · similarity {sim:.1f}% · `{h['source']}`  \n"
                                    f"{h['description']}"
                                )
                                st_ace(
                                    value=h["spl_source"],
                                    language="sql",
                                    theme="monokai",
                                    readonly=True,
                                    height=200,
                                    key=f"ace_rag_{src_label}_{i}",
                                    auto_update=True,
                                )
                                if i < len(hits):
                                    st.divider()
                        st.divider()
    else:
        st.info("Generated SPL will appear here after compilation.")

# ── Inputs + Run (full width, below columns) ───────────────────────────────────

if st.session_state.spl_code:
    # Detect runtime INPUT params — extract all @names from INPUT line(s)
    # e.g. "INPUT @languages LIST, @greeting TEXT DEFAULT 'hello'" → ["languages", "greeting"]
    input_lines = re.findall(r"\bINPUT\b[^\n;]+", st.session_state.spl_code, re.IGNORECASE)
    inputs: list[str] = []
    for line in input_lines:
        inputs.extend(re.findall(r"@(\w+)", line))
    if not inputs:
        # Fallback: PROMPT-style SELECT @param
        inputs = re.findall(r"\bSELECT\s+@(\w+)", st.session_state.spl_code, re.IGNORECASE)

    if inputs:
        st.subheader("Inputs")
        placeholder = "\n".join(f"@{p} := " for p in inputs)
        st.text_area(
            "Inputs",
            placeholder=placeholder,
            key="param_assignments",
            height=max(80, len(inputs) * 40),
            label_visibility="collapsed",
        )

    def _parse_assignments(text: str) -> dict[str, str]:
        """Parse '@name := value' lines into a dict."""
        result: dict[str, str] = {}
        for line in text.splitlines():
            m = re.match(r"\s*@(\w+)\s*:=\s*(.*)", line)
            if m:
                result[m.group(1)] = m.group(2).strip()
        return result

    if btn_run:
        run_cmd = ["spl", "run", st.session_state.spl_file, "--adapter", r_adapter, "-m", r_model]

        raw_assignments = st.session_state.get("param_assignments", "") or ""
        effective_params = _parse_assignments(raw_assignments)

        # Long values (>200 chars) go via --dataset NAME=FILE to avoid arg length issues
        tmp_files: list[str] = []
        for k, v in effective_params.items():
            if not v.strip():
                continue
            if len(v) > 200:
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, encoding="utf-8"
                )
                tmp.write(v)
                tmp.close()
                tmp_files.append(tmp.name)
                run_cmd += ["--dataset", f"{k}={tmp.name}"]
            else:
                run_cmd += ["-p", f"{k}={v}"]

        t0 = time.time()
        with st.spinner("Running…"):
            run_proc = subprocess.run(
                run_cmd, capture_output=True, text=True, timeout=300
            )
        latency_ms = int((time.time() - t0) * 1000)

        for f in tmp_files:
            try:
                Path(f).unlink()
            except OSError:
                pass

        db.save_execution(
            script_id=st.session_state.script_id,
            input_params=effective_params,
            output=run_proc.stdout,
            return_code=run_proc.returncode,
            run_adapter=r_adapter,
            run_model=r_model or None,
            latency_ms=latency_ms,
        )

        if run_proc.returncode != 0 and run_proc.stderr.strip():
            st.error(run_proc.stderr)
        elif run_proc.stdout.strip():
            parsed = _parse_run_output(run_proc.stdout)
            meta = parsed["meta"]
            out_col, meta_col = st.columns([10, 1])
            with out_col:
                st.subheader("Output")
                if parsed["output"]:
                    st.markdown(
                        f"<div style='white-space:pre-wrap;word-wrap:break-word;"
                        f"font-family:monospace;font-size:0.85rem'>"
                        f"{parsed['output']}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.text(run_proc.stdout)
            with meta_col:
                if meta:
                    model_label = "LLM Calls" if "llm_calls" in meta else "Model"
                    model_value = meta.get("llm_calls") or meta.get("model", "—")
                    st.markdown(
                        f"<table style='font-size:0.78rem;border-collapse:collapse'>"
                        f"<tr><td style='color:#888'>{model_label}</td></tr>"
                        f"<tr><td style='padding-bottom:6px'><b>{model_value}</b></td></tr>"
                        f"<tr><td style='color:#888'>In</td></tr>"
                        f"<tr><td style='padding-bottom:6px'><b>{meta.get('tokens_in','—')}</b></td></tr>"
                        f"<tr><td style='color:#888'>Out</td></tr>"
                        f"<tr><td style='padding-bottom:6px'><b>{meta.get('tokens_out','—')}</b></td></tr>"
                        f"<tr><td style='color:#888'>Latency</td></tr>"
                        f"<tr><td><b>{meta.get('latency','—')}</b></td></tr>"
                        f"</table>",
                        unsafe_allow_html=True,
                    )
        else:
            st.info("No output returned.")
