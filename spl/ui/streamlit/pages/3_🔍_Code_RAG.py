"""Page 3: Code-RAG — manage the text2SPL retrieval-augmented generation store."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

sys.path.insert(0, str(Path(__file__).parent.parent))
import code_rag_bridge as rag
import db
import spl3_rag_bridge as spl3_rag

db.init_db()

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Code-RAG", layout="wide")
st.header("Code-RAG Knowledge Base")
st.caption(
    "Retrieval-augmented generation store for the text2SPL compiler — "
    "each indexed (description → SPL) pair improves future compilations."
)

if not rag.is_available():
    st.error(
        "**chromadb is not installed.** Code-RAG is unavailable.\n\n"
        "```\npip install chromadb\n```\n\n"
        f"Error: `{rag.import_error()}`"
    )
    st.stop()

n_rag = rag.count()
scripts = db.get_scripts()
n_scripts = len(scripts)

# ── Sidebar: Stats + Seed/Export ──────────────────────────────────────────────

with st.sidebar:
    st.divider()
    st.markdown("**Stats**")
    st.metric("Pairs in Code-RAG", n_rag)
    st.metric("Scripts in knowledge.db", n_scripts)
    st.metric("Coverage", f"{min(n_rag, n_scripts)}/{n_scripts}" if n_scripts else "—")

    st.divider()
    with st.expander("Seed & Export", expanded=False):
        st.markdown("**Seed from Cookbook (knowledge.db)**")
        st.caption("Index all 37 cookbook recipes as few-shot examples.")
        if st.button("Import Cookbook", use_container_width=True, key="btn_import_cookbook"):
            with st.spinner("Indexing cookbook recipes…"):
                added, msg = rag.seed_cookbook()
            if added >= 0:
                st.success(msg)
            else:
                st.error(msg)

        st.markdown("**Export for Fine-tuning**")
        st.caption("Download all pairs as JSONL.")
        jsonl_data = rag.export_jsonl()
        st.download_button(
            "Download JSONL",
            data=jsonl_data or "",
            file_name="code_rag_pairs.jsonl",
            mime="application/jsonl",
            disabled=(n_rag == 0),
            use_container_width=True,
            key="btn_download_jsonl",
        )

# ── SPL3 Cookbook RAG ─────────────────────────────────────────────────────────

st.subheader("SPL3 Cookbook RAG")
st.caption(
    "SPL3's dedicated RAG store (ChromaDB) populated from SPL v2.0 cookbook recipes. "
    "Used by `splc` for few-shot compilation context."
)

spl3_col1, spl3_col2 = st.columns([2, 3])
with spl3_col1:
    if spl3_rag.is_available():
        n_spl3 = spl3_rag.count()
        st.metric("SPL3 Cookbook recipes", n_spl3)
        st.caption(f"Store: `{spl3_rag.chroma_dir()}`")
    else:
        st.warning("SPL3 RAG store not indexed.")
        err = spl3_rag.import_error()
        if err:
            st.caption(f"Error: {err}")

with spl3_col2:
    if not spl3_rag.is_available():
        if st.button("Index SPL3 Cookbook", key="btn_spl3_seed"):
            with st.spinner("Indexing cookbook recipes into SPL3 RAG store…"):
                c, msg = spl3_rag.seed_cookbook()
            if c >= 0:
                st.success(msg)
            else:
                st.error(msg)
            st.rerun()
    else:
        spl3_q_col, spl3_k_col = st.columns([4, 1])
        with spl3_q_col:
            spl3_query = st.text_input(
                "Search SPL3 cookbook",
                placeholder="e.g. iterative self-improvement",
                key="spl3_search_query",
                label_visibility="collapsed",
            )
        with spl3_k_col:
            spl3_k = st.slider("k", 1, 10, 5, key="spl3_k")

        if spl3_query.strip():
            spl3_hits = spl3_rag.query(spl3_query.strip(), top_k=spl3_k)
            if not spl3_hits:
                st.info("No results.")
            else:
                for h in spl3_hits:
                    sim = max(0.0, (1.0 - h["score"]) * 100)
                    with st.expander(
                        f"**{h['name']}**  · {h['category']}  · similarity {sim:.1f}%",
                        expanded=False,
                    ):
                        st.caption(h["description"])
                        st.code(h["spl_source"], language="sql")

        col_rseed, _ = st.columns([2, 4])
        with col_rseed:
            if st.button("Re-index SPL3 Cookbook", key="btn_spl3_reseed"):
                with st.spinner("Re-indexing…"):
                    c, msg = spl3_rag.seed_cookbook()
                if c >= 0:
                    st.success(msg)
                else:
                    st.error(msg)
                st.rerun()

st.divider()

# ── Search ─────────────────────────────────────────────────────────────────────

st.subheader("knowledge.db Code-RAG")
st.caption(
    "Find similar examples from the knowledge.db Code-RAG store. "
    "Lower score = more similar (cosine distance)."
)

q_col, k_col = st.columns([4, 1])
with q_col:
    query_text = st.text_input(
        "Description",
        placeholder="e.g. summarize a document with a 2000 token budget",
        label_visibility="collapsed",
        key="search_query",
    )
with k_col:
    top_k = st.slider("Top-k", min_value=1, max_value=20, value=10, key="top_k")

if query_text.strip():
    if n_rag == 0:
        st.info("Store is empty — seed it with cookbook recipes first.")
    else:
        results = rag.query(query_text.strip(), top_k=top_k)
        if not results:
            st.info("No results.")
        else:
            results_df = pd.DataFrame([
                {
                    "#": i,
                    "similarity%": f"{max(0.0, (1.0 - r['score']) * 100):.1f}",
                    "name": r.get("name") or "",
                    "source": r.get("source") or "",
                    "description": r["description"][:80],
                }
                for i, r in enumerate(results, 1)
            ])

            gb_s = GridOptionsBuilder.from_dataframe(results_df)
            gb_s.configure_selection(selection_mode="single", use_checkbox=False)
            gb_s.configure_pagination(paginationAutoPageSize=False, paginationPageSize=10)
            gb_s.configure_default_column(resizable=True, sortable=True)
            grid_opts_s = gb_s.build()

            resp_s = AgGrid(
                results_df,
                gridOptions=grid_opts_s,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                use_container_width=True,
                height=380,
                key="rag_search_grid",
            )

            sel_s = resp_s["selected_rows"]
            if sel_s is None:
                sel_s = []
            elif isinstance(sel_s, pd.DataFrame):
                sel_s = sel_s.to_dict("records")

            if sel_s:
                sel_idx = int(sel_s[0]["#"]) - 1
                r = results[sel_idx]
                st.markdown(f"**Description:** {r['description']}")
                if r.get("name"):
                    st.caption(f"name={r['name']}  category={r.get('category', '')}")
                st.code(r["spl_source"], language="sql")
            else:
                st.info("Click a row to view the SPL code.")

# ── Push from knowledge.db ─────────────────────────────────────────────────────

st.divider()
st.subheader("Push from knowledge.db")
st.caption(
    "Promote scripts from the knowledge base into the Code-RAG store. "
    "`auto_capture` in `~/.spl/config.yaml` may have already added some; "
    "use this to add the rest or re-index after edits."
)

if not scripts:
    st.info("No scripts in knowledge.db yet.")
    st.stop()

rows = []
for s in scripts:
    indexed = rag.is_indexed(s["description"])
    rows.append({
        "name": s["name"],
        "v": s["version"],
        "mode": s["mode"],
        "in_rag": "yes" if indexed else "—",
        "description": s["description"][:70],
        "_id": s["id"],
        "_description": s["description"],
        "_spl_code": s["spl_code"],
        "_name": s["name"],
    })

display_df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows])

gb_p = GridOptionsBuilder.from_dataframe(display_df)
gb_p.configure_selection(selection_mode="single", use_checkbox=False)
gb_p.configure_pagination(paginationAutoPageSize=False, paginationPageSize=10)
gb_p.configure_default_column(resizable=True, sortable=True)
grid_opts_p = gb_p.build()

resp_p = AgGrid(
    display_df,
    gridOptions=grid_opts_p,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    use_container_width=True,
    height=380,
    key="push_grid",
)

not_indexed = [r for r in rows if r["in_rag"] == "—"]
bulk_col, _ = st.columns([2, 6])
with bulk_col:
    if not_indexed:
        if st.button(f"Push all {len(not_indexed)} un-indexed script(s)", key="btn_push_all"):
            ok = err = 0
            for r in not_indexed:
                success, _ = rag.add(
                    description=r["_description"],
                    spl_source=r["_spl_code"],
                    name=r["_name"],
                    source="knowledge_db",
                )
                if success:
                    ok += 1
                else:
                    err += 1
            st.success(f"Pushed {ok} script(s)." + (f"  {err} error(s)." if err else ""))
            st.rerun()
    else:
        st.success("All knowledge.db scripts are already in Code-RAG.")

sel_p = resp_p["selected_rows"]
if sel_p is None:
    sel_p = []
elif isinstance(sel_p, pd.DataFrame):
    sel_p = sel_p.to_dict("records")

if sel_p:
    sel_name_p = sel_p[0]["name"]
    sel_ver_p = int(sel_p[0]["v"])
    r_sel = next((r for r in rows if r["name"] == sel_name_p and r["v"] == sel_ver_p), None)
    if r_sel:
        push_col, info_col = st.columns([2, 6])
        with push_col:
            if st.button(f"Push  {r_sel['name']} v{r_sel['v']}", key=f"btn_push_{r_sel['_id']}"):
                success, msg = rag.add(
                    description=r_sel["_description"],
                    spl_source=r_sel["_spl_code"],
                    name=r_sel["_name"],
                    source="knowledge_db",
                )
                if success:
                    st.success("Pushed.")
                else:
                    st.error(msg)
                st.rerun()
        with info_col:
            st.caption(f"RAG status: {r_sel['in_rag']}")
