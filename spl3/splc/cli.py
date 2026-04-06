"""
splc — SPL Compiler CLI
Translates a .spl logical-view script into a physical implementation
in a target language / framework.

Design principle (DODA):
  The .spl file is the invariant logical view.
  splc produces a hardware/framework-specific physical artifact.
  Changing the deployment target only requires re-running splc.

Usage examples:
  # Compile to Go (LLM's pretrained knowledge only)
  splc --spl cookbook/05_self_refine/self_refine.spl --lang go

  # Compile to LangGraph Python with a reference codebase
  splc --spl cookbook/05_self_refine/self_refine.spl --lang python/langgraph \\
       --references https://github.com/langchain-ai/langgraph

  # Compile with multiple references, custom output dir, stronger model
  splc --spl my_workflow.spl --lang python/crewai \\
       --references https://github.com/crewAIInc/crewAI \\
       --references https://github.com/langchain-ai/langchain \\
       --out-dir ./targets/python/crewai \\
       --model claude-opus-4-6

  # Dry-run: print the prompt without calling the LLM
  splc --spl my_workflow.spl --lang go --dry-run

  # Compile without RAG examples (faster, less context)
  splc --spl my_workflow.spl --lang python/langgraph --no-rag
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

# ── Constants ─────────────────────────────────────────────────────────────────

SUPPORTED_LANGS: dict[str, dict] = {
    "go": {
        "label":     "Go (stdlib + Ollama REST API)",
        "ext":       ".go",
        "extras":    ["go.mod"],
        "framework": None,
    },
    "python": {
        "label":     "Python (plain, minimal deps)",
        "ext":       ".py",
        "extras":    ["requirements.txt"],
        "framework": None,
    },
    "python/langgraph": {
        "label":     "Python — LangGraph",
        "ext":       ".py",
        "extras":    ["requirements.txt"],
        "framework": "langgraph",
    },
    "python/crewai": {
        "label":     "Python — CrewAI",
        "ext":       ".py",
        "extras":    ["requirements.txt"],
        "framework": "crewai",
    },
    "python/autogen": {
        "label":     "Python — AutoGen",
        "ext":       ".py",
        "extras":    ["requirements.txt"],
        "framework": "autogen",
    },
    # Planned — not yet implemented
    # "swift":  {...},
    # "snap":   {...},
    # "edge":   {...},
}

SUPPORTED_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-6",
]

SPL30_ROOT    = Path(__file__).resolve().parents[2]   # spl3/splc/cli.py → SPL30/
RAG_STORE_DIR = SPL30_ROOT / "spl3" / "text2spl" / "rag" / ".chroma"


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.command(name="splc", context_settings={"help_option_names": ["-h", "--help"]})

# ── Required ─────────────────────────────────────────────────────────────────
@click.option(
    "--spl", "spl_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    help="Path to the source .spl script (logical view).",
)
@click.option(
    "--lang",
    required=True,
    type=click.Choice(list(SUPPORTED_LANGS), case_sensitive=False),
    help=(
        "Target language / framework. "
        f"Supported: {', '.join(SUPPORTED_LANGS)}."
    ),
)

# ── With defaults ─────────────────────────────────────────────────────────────
@click.option(
    "--out-dir", "out_dir",
    default=None,
    type=click.Path(file_okay=False, writable=True, path_type=Path),
    help=(
        "Output directory for generated files. "
        "Default: targets/<lang>/ relative to the .spl file's parent."
    ),
)
@click.option(
    "--model",
    default="claude-sonnet-4-6",
    type=click.Choice(SUPPORTED_MODELS, case_sensitive=False),
    show_default=True,
    help="Claude model to use for compilation.",
)
@click.option(
    "--rag/--no-rag",
    "use_rag",
    default=True,
    show_default=True,
    help=(
        "Include RAG examples from the text2spl recipe store as few-shot context. "
        "Requires the store to be indexed (run spl3/text2spl/rag/index_recipes.py first)."
    ),
)
@click.option(
    "--rag-k",
    default=3,
    show_default=True,
    type=click.IntRange(1, 10),
    help="Number of RAG examples to include when --rag is on.",
)

# ── Optional ──────────────────────────────────────────────────────────────────
@click.option(
    "--references", "references",
    multiple=True,
    metavar="URL_OR_PATH",
    help=(
        "Reference codebase(s) to ground the LLM's output. "
        "Accepts GitHub URLs or local directory paths. "
        "Repeat to add multiple references. "
        "If omitted, compilation relies on the LLM's pretrained knowledge."
    ),
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing files in --out-dir. Default: abort if files exist.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the compiled prompt without calling the LLM. Useful for debugging.",
)
@click.option(
    "--no-readme",
    is_flag=True,
    default=False,
    help="Skip generating readme.md alongside the implementation.",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    default=False,
    help="Print progress and token counts.",
)
def splc(
    spl_path:   Path,
    lang:       str,
    out_dir:    Path | None,
    model:      str,
    use_rag:    bool,
    rag_k:      int,
    references: tuple[str, ...],
    overwrite:  bool,
    dry_run:    bool,
    no_readme:  bool,
    verbose:    bool,
) -> None:
    """splc — SPL Compiler: translate a .spl logical view into a physical implementation."""

    lang_meta = SUPPORTED_LANGS[lang]

    # ── Resolve output directory ──────────────────────────────────────────────
    if out_dir is None:
        # Default: targets/<lang-slug>/ next to the .spl file
        lang_slug = lang.replace("/", "_")
        out_dir = spl_path.parent / "targets" / lang_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    recipe_name   = spl_path.stem                  # e.g. "self_refine"
    impl_filename = f"{recipe_name}_{lang.replace('/', '_')}{lang_meta['ext']}"
    impl_path     = out_dir / impl_filename
    readme_path   = out_dir / "readme.md"
    manifest_path = out_dir / "splc_manifest.json"

    # ── Overwrite guard ───────────────────────────────────────────────────────
    if not overwrite and impl_path.exists():
        click.echo(
            f"ERROR: {impl_path} already exists. "
            "Use --overwrite to replace it.",
            err=True,
        )
        sys.exit(1)

    spl_source = spl_path.read_text(encoding="utf-8")

    if verbose:
        click.echo(f"splc: {spl_path.name}  →  {lang}  ({lang_meta['label']})")
        click.echo(f"      model={model}  rag={use_rag}(k={rag_k})  refs={len(references)}")

    # ── Fetch references ──────────────────────────────────────────────────────
    ref_context = _fetch_references(references, verbose=verbose)

    # ── RAG few-shot examples ─────────────────────────────────────────────────
    rag_context = ""
    if use_rag:
        rag_context = _fetch_rag_examples(spl_source, lang, k=rag_k, verbose=verbose)

    # ── Build prompt ──────────────────────────────────────────────────────────
    prompt = _build_prompt(
        spl_source   = spl_source,
        spl_filename = spl_path.name,
        lang         = lang,
        lang_meta    = lang_meta,
        ref_context  = ref_context,
        rag_context  = rag_context,
        recipe_name  = recipe_name,
        gen_readme   = not no_readme,
    )

    if dry_run:
        click.echo("=" * 70)
        click.echo("DRY RUN — prompt that would be sent to the LLM:")
        click.echo("=" * 70)
        click.echo(prompt)
        click.echo(f"\n[Prompt length: {len(prompt)} chars / ~{len(prompt)//4} tokens]")
        return

    # ── Call LLM (claude_cli adapter) ─────────────────────────────────────────
    if verbose:
        click.echo(f"Calling {model} ...")

    impl_code, readme_text = _compile(prompt, model=model, verbose=verbose)

    # ── Write output files ────────────────────────────────────────────────────
    impl_path.write_text(impl_code, encoding="utf-8")
    click.echo(f"  Written: {impl_path}")

    if not no_readme and readme_text:
        readme_path.write_text(readme_text, encoding="utf-8")
        click.echo(f"  Written: {readme_path}")

    _write_manifest(
        manifest_path = manifest_path,
        spl_path      = spl_path,
        lang          = lang,
        model         = model,
        references    = list(references),
        use_rag       = use_rag,
        rag_k         = rag_k,
        impl_path     = impl_path,
    )
    click.echo(f"  Written: {manifest_path}")
    click.echo(f"\nsplc done: {spl_path.name} → {lang} [{lang_meta['label']}]")


# ── Reference fetcher ─────────────────────────────────────────────────────────

def _fetch_references(refs: tuple[str, ...], *, verbose: bool) -> str:
    """Fetch reference content from URLs or local paths.

    GitHub repo URLs: fetch README.md + key source files (heuristic top-level *.py/*.go).
    Local paths:      read all source files matching the target extension.
    Returns a formatted block for injection into the prompt.
    """
    if not refs:
        return ""

    parts: list[str] = []
    for ref in refs:
        if verbose:
            click.echo(f"  Fetching reference: {ref}")
        try:
            content = _fetch_one_reference(ref)
            if content:
                parts.append(f"## Reference: {ref}\n\n{content}")
        except Exception as exc:
            click.echo(f"  WARN: could not fetch reference {ref}: {exc}", err=True)

    if not parts:
        return ""

    return "# Reference Codebases\n\n" + "\n\n---\n\n".join(parts)


def _fetch_one_reference(ref: str) -> str:
    """Fetch a single reference. Returns text content."""
    import urllib.request

    if ref.startswith("http://") or ref.startswith("https://"):
        # GitHub URL → convert to raw README fetch
        # e.g. https://github.com/langchain-ai/langgraph
        #   →  https://raw.githubusercontent.com/langchain-ai/langgraph/main/README.md
        raw_url = _github_to_raw_readme(ref)
        with urllib.request.urlopen(raw_url, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")[:8000]  # cap at 8k chars
    else:
        # Local path — read all source files
        p = Path(ref)
        if not p.exists():
            raise FileNotFoundError(f"Reference path not found: {p}")
        if p.is_file():
            return p.read_text(encoding="utf-8")[:8000]
        # Directory: read README + source files
        parts = []
        for readme in sorted(p.glob("README*")):
            parts.append(readme.read_text(encoding="utf-8")[:4000])
        for src in sorted(p.rglob("*.py"))[:5]:   # first 5 source files
            parts.append(f"# {src.name}\n" + src.read_text(encoding="utf-8")[:2000])
        return "\n\n".join(parts)[:10000]


def _github_to_raw_readme(url: str) -> str:
    """Convert a GitHub repo URL to a raw README URL."""
    # https://github.com/owner/repo → https://raw.githubusercontent.com/owner/repo/main/README.md
    url = url.rstrip("/")
    if "github.com" in url and "raw.githubusercontent.com" not in url:
        url = url.replace("github.com", "raw.githubusercontent.com")
        return url + "/main/README.md"
    return url


# ── RAG examples ─────────────────────────────────────────────────────────────

def _fetch_rag_examples(spl_source: str, lang: str, *, k: int, verbose: bool) -> str:
    """Retrieve k similar recipes already compiled to the target lang from the RAG store."""
    if not RAG_STORE_DIR.exists():
        if verbose:
            click.echo("  RAG store not found — skipping few-shot examples.")
            click.echo("  Run: python spl3/text2spl/rag/index_recipes.py")
        return ""

    try:
        spl3_dir = str(SPL30_ROOT / "spl3")
        if spl3_dir not in sys.path:
            sys.path.insert(0, spl3_dir)
        from text2spl.rag.search import search_recipes
    except ImportError:
        if verbose:
            click.echo("  WARN: text2spl.rag not importable — skipping RAG context.")
        return ""

    # Use the SPL source as the query to find similar recipes
    query = _spl_to_query(spl_source)
    if verbose:
        click.echo(f"  RAG query: {query[:60]}...")

    hits = search_recipes(query, k=k)
    if not hits:
        return ""

    lang_label = SUPPORTED_LANGS[lang]["label"]
    parts = [f"# Similar SPL Recipes (few-shot context)\n"
             f"The following recipes implement similar patterns. "
             f"Use them to understand the SPL idioms before generating {lang_label} code.\n"]
    for h in hits:
        parts.append(
            f"## Example: {h.name}  [score={h.score:.3f}]\n"
            f"{h.description}\n\n"
            f"```spl\n{h.spl_source[:2000]}\n```"
        )
    return "\n\n".join(parts)


def _spl_to_query(spl_source: str) -> str:
    """Extract a short natural-language query from a .spl file for RAG retrieval.

    Skips generic header lines ("Recipe Name:", "File:", "Author:") and returns
    the first meaningful description comment or the WORKFLOW name.
    """
    _SKIP_PREFIXES = ("recipe name", "file:", "author:", "date:", "version:")
    for line in spl_source.splitlines():
        stripped = line.strip()
        if not stripped.startswith("--"):
            continue
        text = stripped.lstrip("- ").strip()
        if len(text) < 10:
            continue
        if any(text.lower().startswith(p) for p in _SKIP_PREFIXES):
            continue
        return text
    # Fall back to WORKFLOW name
    import re
    m = re.search(r"WORKFLOW\s+(\w+)", spl_source, re.IGNORECASE)
    return m.group(1).replace("_", " ") if m else "SPL workflow"


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    spl_source:   str,
    spl_filename: str,
    lang:         str,
    lang_meta:    dict,
    ref_context:  str,
    rag_context:  str,
    recipe_name:  str,
    gen_readme:   bool,
) -> str:
    """Construct the full compilation prompt sent to the LLM."""

    readme_instruction = (
        "\n\nAfter the implementation, output a `readme.md` section "
        "(starting with `--- README ---` on its own line) that includes: "
        "setup instructions, run command, expected output pattern, "
        "and a table mapping each SPL construct to its equivalent in the target."
        if gen_readme else ""
    )

    sections = [
        _SYSTEM_PROMPT.format(
            lang_label    = lang_meta["label"],
            lang          = lang,
            recipe_name   = recipe_name,
            spl_filename  = spl_filename,
            readme_instr  = readme_instruction,
        ),
    ]

    if rag_context:
        sections.append(rag_context)

    if ref_context:
        sections.append(ref_context)

    sections.append(
        f"# SPL Source to Compile\n\n"
        f"File: `{spl_filename}`\n\n"
        f"```spl\n{spl_source}\n```\n\n"
        f"Generate the {lang_meta['label']} implementation now."
    )

    return "\n\n---\n\n".join(sections)


_SYSTEM_PROMPT = """\
You are `splc`, the SPL Compiler. Your job is to translate a `.spl` script
(the SPL logical view — declarative, hardware-agnostic) into a working
{lang_label} implementation (the physical view).

Rules:
1. Every SPL construct must map to an equivalent in {lang}. Add a comment
   on each translated block showing the original SPL line(s), e.g.:
   `# SPL: GENERATE critique(@current) INTO @feedback`
2. Preserve ALL workflow semantics: WHILE loops, EVALUATE conditions,
   EXCEPTION handlers, CALL sub-workflows, LOGGING statements.
3. Use only the target language's standard patterns for {lang_label}.
   Do not introduce dependencies not required by the SPL logic.
4. Match the INPUT parameter names, types, and defaults exactly.
5. Output ONLY the implementation file content — no explanation before it.
   The file should be ready to run without modification.
6. Use the recipe name `{recipe_name}` as the basis for file/class/function names.
{readme_instr}

Target: {lang_label}
Source file: {spl_filename}\
"""


# ── LLM caller ───────────────────────────────────────────────────────────────

def _compile(prompt: str, *, model: str, verbose: bool) -> tuple[str, str]:
    """Call the claude_cli adapter and return (implementation, readme)."""
    try:
        from spl.adapters.claude_cli import ClaudeCliAdapter  # type: ignore
    except ImportError:
        click.echo(
            "ERROR: claude_cli adapter not found. "
            "Ensure SPL20 is on PYTHONPATH or spl package is installed.",
            err=True,
        )
        sys.exit(1)

    import asyncio

    adapter = ClaudeCliAdapter(model=model)

    async def _run() -> str:
        result = await adapter.generate(prompt)
        return result.content

    raw = asyncio.run(_run())

    if verbose:
        click.echo(f"  LLM response: {len(raw)} chars")

    # Split implementation from readme (if present)
    if "--- README ---" in raw:
        impl_part, _, readme_part = raw.partition("--- README ---")
        return impl_part.strip(), readme_part.strip()
    return raw.strip(), ""


# ── Manifest writer ───────────────────────────────────────────────────────────

def _write_manifest(
    manifest_path: Path,
    spl_path:      Path,
    lang:          str,
    model:         str,
    references:    list[str],
    use_rag:       bool,
    rag_k:         int,
    impl_path:     Path,
) -> None:
    """Write a splc_manifest.json capturing provenance of the compiled artifact."""
    manifest = {
        "splc_version":    "0.1.0",
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "source": {
            "spl_file":    str(spl_path.resolve()),
            "spl_sha256":  _sha256(spl_path),
        },
        "target": {
            "lang":        lang,
            "label":       SUPPORTED_LANGS[lang]["label"],
            "output_file": str(impl_path.resolve()),
        },
        "compilation": {
            "model":       model,
            "adapter":     "claude_cli",
            "references":  references,
            "rag_enabled": use_rag,
            "rag_k":       rag_k if use_rag else 0,
        },
        "doda_note": (
            "This file is a splc-compiled physical artifact. "
            "The source .spl file is the invariant logical view. "
            "To retarget, run: splc --spl <source.spl> --lang <new-target>"
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    splc()
