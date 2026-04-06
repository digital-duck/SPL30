"""Page 2: Review — browse and manage the text2SPL knowledge base."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from streamlit_ace import st_ace

sys.path.insert(0, str(Path(__file__).parent.parent))
import db

db.init_db()


def _parse_run_output(stdout: str) -> dict:
    """Extract metrics and LLM output from spl run stdout."""
    lines = stdout.splitlines()
    meta: dict[str, str] = {}
    output_lines: list[str] = []
    in_output = False

    for line in lines:
        s = line.strip()
        if s and all(c == "=" for c in s) and len(s) >= 20:
            if in_output:
                in_output = False
            continue
        if s and all(c == "-" for c in s) and len(s) >= 20:
            in_output = True
            continue
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

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Review", layout="wide")
st.header("Review: text2SPL Knowledge Base")
st.caption(
    "All generated scripts and execution history — "
    "a growing dataset for self-improving the text2SPL compiler."
)

scripts = db.get_scripts()

# ── Sidebar: Export / Import ───────────────────────────────────────────────────

with st.sidebar:
    st.divider()
    with st.expander("Export / Import", expanded=False):
        st.markdown("**Export**")
        if scripts:
            yaml_data = db.export_knowledge()
            st.download_button(
                label="Download YAML",
                data=yaml_data,
                file_name="text2spl_knowledge.yaml",
                mime="text/yaml",
                use_container_width=True,
                key="btn_download_yaml",
            )
        else:
            st.button("Download YAML", disabled=True, use_container_width=True, key="btn_download_yaml")

        st.markdown("**Import**")
        uploaded = st.file_uploader(
            "Upload YAML",
            type=["yaml", "yml"],
            label_visibility="collapsed",
            key="file_uploader_yaml",
        )
        if uploaded is not None:
            if st.button("Import", use_container_width=True, key="btn_import_yaml"):
                yaml_str = uploaded.read().decode("utf-8")
                added_s, added_e = db.import_knowledge(yaml_str)
                st.success(f"Imported {added_s} script(s), {added_e} execution(s).")
                st.rerun()

if not scripts:
    st.info("No scripts yet. Go to **Text-to-SPL** to generate your first script.")
    st.stop()

# ── Scripts table ──────────────────────────────────────────────────────────────

st.subheader(f"Scripts ({len(scripts)})")

scripts_df = pd.DataFrame([
    {
        "name": s["name"],
        "v": s["version"],
        "mode": s["mode"],
        "compiler": f"{s['compiler_adapter'] or ''} / {s['compiler_model'] or 'default'}",
        "description": s["description"],
        "created_at": s["created_at"],
    }
    for s in scripts
])

gb = GridOptionsBuilder.from_dataframe(scripts_df)
gb.configure_selection(selection_mode="single", use_checkbox=False)
gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=10)
gb.configure_default_column(resizable=True, sortable=True, filter=True)
grid_opts = gb.build()

resp = AgGrid(
    scripts_df,
    gridOptions=grid_opts,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    use_container_width=True,
    height=380,
    key="scripts_grid",
)

sel_rows = resp["selected_rows"]
# Normalize to list-of-dicts regardless of aggrid version
if sel_rows is None:
    sel_rows = []
elif isinstance(sel_rows, pd.DataFrame):
    sel_rows = sel_rows.to_dict("records")

if not sel_rows:
    st.info("Click a row to view script details and execution history.")
    st.stop()

sel_name = sel_rows[0]["name"]
sel_ver = int(sel_rows[0]["v"])
selected = next((s for s in scripts if s["name"] == sel_name and s["version"] == sel_ver), None)
if not selected:
    st.stop()

# ── Script detail ──────────────────────────────────────────────────────────────

st.subheader(f"{selected['name']} v{selected['version']}")
st.write("##### Description")
st.code(selected["description"])

col_code, col_meta = st.columns([3, 1])
with col_code:
    st.write("##### SPL code")
    st_ace(
        value=selected["spl_code"],
        language="sql",
        theme="monokai",
        readonly=True,
        height=280,
        key=f"ace_review_{selected['id']}",
        auto_update=True,
    )
with col_meta:
    with st.expander("Metadata", expanded=False):
        st.json({
            "name": selected["name"],
            "version": selected["version"],
            "mode": selected["mode"],
            "description": selected["description"],
            "compiler_adapter": selected["compiler_adapter"],
            "compiler_model": selected["compiler_model"] or "(default)",
            "spl_file": selected["spl_file"],
            "created_at": selected["created_at"],
        })

# ── Execution history ──────────────────────────────────────────────────────────

executions = db.get_executions(selected["id"])
n = len(executions)
st.subheader(f"Execution History ({n} run{'s' if n != 1 else ''})")

if not executions:
    st.info("This script has not been executed yet.")
    st.stop()

exec_df = pd.DataFrame([
    {
        "run #": i,
        "adapter": e["run_adapter"] or "",
        "model": e["run_model"] or "(default)",
        "latency_ms": e["latency_ms"],
        "rc": e["return_code"],
        "created_at": e["created_at"],
    }
    for i, e in enumerate(executions, 1)
])

gb2 = GridOptionsBuilder.from_dataframe(exec_df)
gb2.configure_selection(selection_mode="single", use_checkbox=False)
gb2.configure_pagination(paginationAutoPageSize=False, paginationPageSize=10)
gb2.configure_default_column(resizable=True, sortable=True)
grid_opts2 = gb2.build()

resp2 = AgGrid(
    exec_df,
    gridOptions=grid_opts2,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    use_container_width=True,
    height=320,
    key=f"exec_grid_{selected['id']}",
)

sel_exec = resp2["selected_rows"]
if sel_exec is None:
    sel_exec = []
elif isinstance(sel_exec, pd.DataFrame):
    sel_exec = sel_exec.to_dict("records")

if not sel_exec:
    st.info("Click a row to view run details.")
    st.stop()

sel_run_num = int(sel_exec[0]["run #"])
ex = executions[sel_run_num - 1]

params = db.decode_params(ex["input_params"])
if params:
    st.markdown("**Inputs**")
    pcols = st.columns(min(len(params), 2))
    for j, (k, v) in enumerate(params.items()):
        with pcols[j % len(pcols)]:
            st.text_area(f"@{k}", value=v, disabled=True, key=f"ex_{ex['id']}_{k}", height=100)

if ex["output"] and ex["output"].strip():
    parsed = _parse_run_output(ex["output"])
    meta = parsed["meta"]
    out_col, meta_col = st.columns([10, 1])
    with out_col:
        st.subheader("Output")
        if parsed["output"]:
            st.markdown(
                f"<div style='white-space:pre-wrap;word-wrap:break-word;"
                f"font-family:monospace;font-size:0.85rem'>{parsed['output']}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.text(ex["output"])
    with meta_col:
        if meta:
            model_label = "LLM Calls" if "llm_calls" in meta else "Model"
            model_value = meta.get("llm_calls") or meta.get("model", "—")
            st.markdown(
                f"<table style='font-size:0.78rem;border-collapse:collapse'>"
                f"<tr><td style='color:#888'>{model_label}</td></tr>"
                f"<tr><td style='padding-bottom:6px'><b>{model_value}</b></td></tr>"
                f"<tr><td style='color:#888'>In</td></tr>"
                f"<tr><td style='padding-bottom:6px'><b>{meta.get('tokens_in', '—')}</b></td></tr>"
                f"<tr><td style='color:#888'>Out</td></tr>"
                f"<tr><td style='padding-bottom:6px'><b>{meta.get('tokens_out', '—')}</b></td></tr>"
                f"<tr><td style='color:#888'>Latency</td></tr>"
                f"<tr><td><b>{meta.get('latency', '—')}</b></td></tr>"
                f"</table>",
                unsafe_allow_html=True,
            )
else:
    st.caption("(no output)")
