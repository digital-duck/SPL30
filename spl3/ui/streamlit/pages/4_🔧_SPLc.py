"""Page 4: SPLc — compile a .spl logical view into a physical implementation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
import spl3_rag_bridge as spl3_rag

# ── Constants ──────────────────────────────────────────────────────────────────

SPL30_ROOT = spl3_rag.spl3_root()
SPL_DIR    = SPL30_ROOT / "spl"
SPLC_CLI   = SPL_DIR / "splc" / "cli.py"

SUPPORTED_LANGS = {
    "go":               "Go (stdlib + Ollama REST API)",
    "python":           "Python (plain, minimal deps)",
    "python/langgraph": "Python — LangGraph",
    "python/crewai":    "Python — CrewAI",
    "python/autogen":   "Python — AutoGen",
    "python/liquid":    "Python — Liquid AI (LFM via Ollama / OpenRouter)",
}

SUPPORTED_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-6",
]

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="SPLc Compiler", layout="wide")
st.header("SPLc — SPL Compiler")
st.caption(
    "Translate a `.spl` logical-view script into a physical implementation "
    "(Go, Python, LangGraph, CrewAI, AutoGen)."
)

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("**DODA Architecture**")
    st.caption(
        "Design Once, Deploy Anywhere: `.spl` = invariant logical view; "
        "`splc` = compiler producing hardware/framework-specific artifacts."
    )
    st.divider()

    if spl3_rag.is_available():
        n = spl3_rag.count()
        st.metric("SPL3 RAG recipes", n)
        st.caption("RAG examples improve compilation quality.")
    else:
        st.warning("SPL3 RAG store not indexed.")
        err = spl3_rag.import_error()
        if err:
            st.caption(f"Error: {err}")
        if st.button("Seed cookbook", key="sidebar_seed"):
            with st.spinner("Indexing…"):
                c, msg = spl3_rag.seed_cookbook()
            if c >= 0:
                st.success(msg)
            else:
                st.error(msg)
            st.rerun()

    st.divider()
    st.markdown("**splc CLI**")
    if SPLC_CLI.exists():
        st.success(f"Found: `spl/splc/cli.py`")
    else:
        st.error(f"Not found: `{SPLC_CLI}`")

# ── Helper: find .spl files ────────────────────────────────────────────────────

@st.cache_data(ttl=10)
def _find_spl_files() -> list[str]:
    cookbook = SPL30_ROOT / "cookbook"
    paths = sorted(cookbook.rglob("*.spl")) if cookbook.exists() else []
    return [str(p) for p in paths]


# ── Session state ──────────────────────────────────────────────────────────────

for key, default in [
    ("splc_output_code", None),
    ("splc_output_readme", None),
    ("splc_manifest", None),
    ("splc_out_dir", None),
    ("splc_error", None),
    ("splc_dry_run_prompt", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Main layout ────────────────────────────────────────────────────────────────

left, _, right = st.columns([4, 0.3, 7])

with left:
    st.subheader("Source")

    # .spl file selection
    spl_files = _find_spl_files()
    use_picker = st.checkbox("Pick from cookbook", value=bool(spl_files), key="use_picker")

    if use_picker and spl_files:
        # Show relative paths for readability
        display_names = [
            str(Path(p).relative_to(SPL30_ROOT)) if str(p).startswith(str(SPL30_ROOT)) else p
            for p in spl_files
        ]
        sel_idx = st.selectbox(
            "SPL file",
            range(len(display_names)),
            format_func=lambda i: display_names[i],
            key="spl_picker",
        )
        spl_path_str = spl_files[sel_idx]
    else:
        spl_path_str = st.text_input(
            "SPL file path",
            placeholder="/path/to/my_workflow.spl",
            key="spl_path_manual",
        )

    if spl_path_str and Path(spl_path_str).exists():
        spl_content = Path(spl_path_str).read_text()
        with st.expander("Preview SPL source", expanded=False):
            st.code(spl_content, language="sql")
    elif spl_path_str:
        st.warning("File not found.")

    st.divider()
    st.subheader("Target")

    lang_keys = list(SUPPORTED_LANGS.keys())
    lang_labels = list(SUPPORTED_LANGS.values())
    lang_idx = st.selectbox(
        "Language / Framework",
        range(len(lang_keys)),
        format_func=lambda i: f"{lang_keys[i]}  —  {lang_labels[i]}",
        key="lang_select",
    )
    lang = lang_keys[lang_idx]

    st.divider()
    st.subheader("References (optional)")
    st.caption("GitHub URLs or local directory paths — one per line.")
    refs_text = st.text_area(
        "References",
        placeholder=(
            "https://github.com/langchain-ai/langgraph\n"
            "/path/to/local/codebase"
        ),
        height=100,
        key="refs_input",
        label_visibility="collapsed",
    )

    st.divider()
    st.subheader("Options")

    model = st.selectbox("Model", SUPPORTED_MODELS, key="model_select")

    col_rag, col_k = st.columns([1, 1])
    with col_rag:
        use_rag = st.checkbox("Use RAG", value=True, key="use_rag",
                              help="Include similar SPL recipes as few-shot context.")
    with col_k:
        rag_k = st.slider("RAG k", 1, 5, 3, key="rag_k",
                          disabled=not st.session_state.get("use_rag", True))

    col_dry, col_ow, col_nor = st.columns(3)
    with col_dry:
        dry_run = st.checkbox("Dry run", value=False, key="dry_run",
                              help="Print prompt only — do not call the LLM.")
    with col_ow:
        overwrite = st.checkbox("Overwrite", value=False, key="overwrite")
    with col_nor:
        no_readme = st.checkbox("No readme", value=False, key="no_readme")

    out_dir_input = st.text_input(
        "Output dir (optional)",
        placeholder="default: <spl_dir>/targets/<lang>/",
        key="out_dir_input",
    )

    st.divider()

    compile_btn = st.button(
        "Compile" if not dry_run else "Dry Run (show prompt)",
        type="primary",
        key="btn_compile",
        disabled=(not spl_path_str or not Path(spl_path_str).exists()),
    )

    if compile_btn:
        st.session_state.update(
            splc_output_code=None,
            splc_output_readme=None,
            splc_manifest=None,
            splc_out_dir=None,
            splc_error=None,
            splc_dry_run_prompt=None,
        )

        # Build command
        cmd = [
            "conda", "run", "-n", "spl2", "--no-capture-output",
            "python", str(SPLC_CLI),
            "--spl", spl_path_str,
            "--lang", lang,
            "--model", model,
        ]

        if not use_rag:
            cmd.append("--no-rag")
        else:
            cmd += ["--rag-k", str(rag_k)]

        refs = [r.strip() for r in refs_text.splitlines() if r.strip()]
        for ref in refs:
            cmd += ["--references", ref]

        if dry_run:
            cmd.append("--dry-run")
        if overwrite:
            cmd.append("--overwrite")
        if no_readme:
            cmd.append("--no-readme")

        resolved_out_dir = out_dir_input.strip() or None
        if resolved_out_dir:
            cmd += ["--out-dir", resolved_out_dir]

        cmd.append("-v")

        with st.spinner(f"Compiling {Path(spl_path_str).name} → {lang}…"):
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=300,
                    cwd=str(SPL30_ROOT),
                )
            except subprocess.TimeoutExpired:
                st.session_state.splc_error = "Compilation timed out (300 s)."
                st.rerun()

        if dry_run:
            st.session_state.splc_dry_run_prompt = proc.stdout or proc.stderr or "(no output)"
        elif proc.returncode == 0:
            # Discover output directory from stdout ("Output: ...")
            out_dir_found: Path | None = None
            for line in proc.stdout.splitlines():
                if line.strip().startswith("Output:"):
                    candidate = line.strip()[len("Output:"):].strip()
                    out_dir_found = Path(candidate) if candidate else None
                    break

            if out_dir_found is None and resolved_out_dir:
                out_dir_found = Path(resolved_out_dir)
            if out_dir_found is None:
                # default path
                lang_slug = lang.replace("/", "_")
                out_dir_found = Path(spl_path_str).parent / "targets" / lang_slug

            st.session_state.splc_out_dir = str(out_dir_found)

            # Load generated files
            if out_dir_found.exists():
                code_files = [
                    f for f in sorted(out_dir_found.iterdir())
                    if f.is_file() and f.suffix in (".go", ".py", ".swift", ".js", ".ts", ".mod")
                ]
                if code_files:
                    st.session_state.splc_output_code = code_files[0].read_text()

                readme_file = out_dir_found / "readme.md"
                if not readme_file.exists():
                    readme_file = out_dir_found / "README.md"
                if readme_file.exists():
                    st.session_state.splc_output_readme = readme_file.read_text()

                manifest_file = out_dir_found / "splc_manifest.json"
                if manifest_file.exists():
                    try:
                        st.session_state.splc_manifest = json.loads(manifest_file.read_text())
                    except json.JSONDecodeError:
                        pass
        else:
            st.session_state.splc_error = proc.stderr or proc.stdout or "Compilation failed."

        st.rerun()


# ── Right panel: output ───────────────────────────────────────────────────────

with right:
    if st.session_state.splc_error:
        st.error("**Compilation error**")
        st.code(st.session_state.splc_error, language="text")

    elif st.session_state.splc_dry_run_prompt:
        st.subheader("Dry-run: assembled prompt")
        st.code(st.session_state.splc_dry_run_prompt, language="text")

    elif st.session_state.splc_output_code or st.session_state.splc_output_readme:
        out_dir_path = st.session_state.splc_out_dir
        if out_dir_path:
            st.success(f"Output directory: `{out_dir_path}`")

        tab_code, tab_readme, tab_manifest = st.tabs(["Code", "README", "Manifest"])

        with tab_code:
            if st.session_state.splc_output_code:
                lang_ext = "go" if lang == "go" else "python"
                st.code(st.session_state.splc_output_code, language=lang_ext)

                # Show all generated files if multiple
                if out_dir_path and Path(out_dir_path).exists():
                    all_code_files = [
                        f for f in sorted(Path(out_dir_path).iterdir())
                        if f.is_file() and f.suffix in (".go", ".py", ".mod", ".txt")
                        and f.name != "readme.md" and f.name != "README.md"
                        and f.name != "splc_manifest.json"
                    ]
                    if len(all_code_files) > 1:
                        st.divider()
                        st.caption("Other generated files:")
                        for f in all_code_files[1:]:
                            with st.expander(f.name, expanded=False):
                                st.code(f.read_text(), language="text")
            else:
                st.info("No code file found in output directory.")

        with tab_readme:
            if st.session_state.splc_output_readme:
                st.markdown(st.session_state.splc_output_readme)
            else:
                st.info("No README generated (use --no-readme to suppress this).")

        with tab_manifest:
            if st.session_state.splc_manifest:
                m = st.session_state.splc_manifest
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**SPL file:** `{Path(m.get('spl_file', '')).name}`")
                    st.markdown(f"**Target:** `{m.get('lang', '—')}`")
                    st.markdown(f"**Model:** `{m.get('model', '—')}`")
                with col2:
                    st.markdown(f"**RAG:** {m.get('rag', '—')} (k={m.get('rag_k', '—')})")
                    st.markdown(f"**Generated:** {m.get('generated_at', '—')}")
                    refs = m.get("references", [])
                    if refs:
                        st.markdown(f"**References:** {', '.join(refs)}")
                st.divider()
                st.caption("Full manifest JSON:")
                st.json(m)
            else:
                st.info("No `splc_manifest.json` found.")

    else:
        st.info(
            "Configure the source `.spl` file and target language on the left, "
            "then click **Compile**."
        )

        # Quick-start tips
        st.divider()
        st.markdown("**Quick start**")
        st.markdown("""
1. Pick a `.spl` file from the cookbook (e.g. `05_self_refine/self_refine.spl`)
2. Choose a target language (e.g. `go`)
3. Optionally add a reference URL for the target framework
4. Click **Compile** — the generated code appears here
5. Switch to **Target Review** (page 5) to browse all compiled artifacts
""")
