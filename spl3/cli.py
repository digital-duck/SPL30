"""SPL 3.0 CLI: spl

Commands:
  spl register <path>             Register workflows from .spl file(s) into Hub registry
  spl run <file.spl>              Run an orchestrator workflow
  spl describe <file.spl>         Generate a plain-English functional specification
  spl registry list               List registered workflows (local + Hub)
  spl peers list                  List peer Hubs and their workflow counts
  spl peers add <url>             Add a peer Hub (peering handshake)
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import click

_log = logging.getLogger("spl.cli")

_SPL_LOG_DIR = Path.home() / ".spl" / "logs"


# ---------------------------------------------------------------------------
# Run-log helpers (parity with spl-go / spl-ts)
# ---------------------------------------------------------------------------

class _CapturingAdapter:
    """Thin wrapper that records the last prompt/model sent to the LLM."""
    def __init__(self, inner):
        self._inner = inner
        self.last_prompt = ""
        self.last_model = ""

    def __getattr__(self, name):
        return getattr(self._inner, name)

    async def generate(self, prompt: str = "", model: str = "", **kwargs):
        self.last_prompt = prompt
        self.last_model = model or getattr(self._inner, "default_model", "")
        return await self._inner.generate(prompt, model=model, **kwargs)


def _write_run_log(
    stem: str,
    adapter_name: str,
    model_name: str,
    source: str,
    last_prompt: str,
    result,
    started_at: datetime,
) -> Path:
    """Write a rich markdown run log matching spl-go / spl-ts format. Returns the log path."""
    _SPL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts_file  = started_at.strftime("%Y%m%d-%H%M%S")
    ts_human = started_at.strftime("%Y-%m-%d %H:%M:%S")

    filename = f"{stem}-{adapter_name}-{ts_file}.md"
    log_path = _SPL_LOG_DIR / filename

    # Support both WorkflowResult (spl3) and SPLResult / GenerationResult (spl2)
    in_tok  = (getattr(result, "total_input_tokens",  None)
               or getattr(result, "input_tokens",  0) or 0)
    out_tok = (getattr(result, "total_output_tokens", None)
               or getattr(result, "output_tokens", 0) or 0)
    latency = (getattr(result, "total_latency_ms",    None)
               or getattr(result, "latency_ms",    0) or 0)
    output  = (getattr(result, "committed_value", None)
               or getattr(result, "content", "") or "")

    lines = [
        f"# SPL Run: {stem}",
        "",
        f"- **Adapter:** {adapter_name}",
        f"- **Model:** {model_name}",
        f"- **Tokens:** {in_tok} in / {out_tok} out",
        f"- **Latency:** {latency:.0f}ms",
        f"- **Timestamp:** {ts_human}",
        "",
        "## SPL Source",
        "",
        "```spl",
        source.rstrip(),
        "```",
    ]

    if last_prompt:
        lines += ["", "## Final Prompt", "", "```prompt", last_prompt.rstrip(), "```"]

    lines += ["", "## Output", "", "```output", output.rstrip(), "```"]

    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


@click.group()
@click.option("--hub", default=None, envvar="SPL3_HUB", help="Momagrid Hub URL")
@click.option("--verbose", "-v", is_flag=True)
@click.pass_context
def main(ctx, hub, verbose):
    """SPL 3.0 — Declarative Structured Prompt Language."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    ctx.ensure_object(dict)
    ctx.obj["hub"] = hub


# ------------------------------------------------------------------ #
# spl run                                                             #
# ------------------------------------------------------------------ #

@main.command()
@click.argument("spl_file")
@click.option("--adapter", default="ollama", show_default=True)
@click.option("--model", default=None, show_default=True)
@click.option("--param", "-p", multiple=True, help="key=value workflow INPUT params")
@click.option(
    "--log-prompts", default=None, metavar="DIR",
    help=(
        "Write each fully-assembled prompt to DIR/<fn>_NNN.md before it is sent "
        "to the model. Each file contains a metadata header (model, max_tokens, "
        "temperature) followed by the raw prompt body — ready to paste into "
        "Google AI Studio, HuggingFace Chat, or any other playground."
    ),
)
@click.option("--tools", "tools_module", default=None, metavar="FILE",
              help="Python module to load as CALL-able tools (e.g. tools/my_tools.py).")
@click.option("--claude-allowed-tools", "allowed_tools", default=None, metavar="TOOLS",
              help="Comma-separated tools for the claude_cli adapter (e.g. WebSearch,Bash).")
@click.pass_context
def run(ctx, spl_file, adapter, model, param, log_prompts, tools_module, allowed_tools):
    """Run an orchestrator .spl workflow with workflow composition."""
    from pathlib import Path
    from spl3.registry import LocalRegistry
    from spl3._loader import load_workflows_from_file

    # Parse params: key=value pairs
    params = {}
    for p in param:
        if "=" not in p:
            raise click.BadParameter(f"Expected key=value, got: {p}")
        k, v = p.split("=", 1)
        params[k.strip()] = v.strip()

    path = Path(spl_file)
    if not path.exists():
        raise click.ClickException(f"File not found: {path}")

    hub_url = ctx.obj.get("hub")

    asyncio.run(_run_workflow(path, adapter, model, params, hub_url, log_prompts,
                              tools_module, allowed_tools))


async def _run_workflow(path, adapter_name, model, params, hub_url, log_prompts=None,
                        tools_module=None, allowed_tools=None):
    from spl3.registry import LocalRegistry, FederatedRegistry
    from spl3.composer import WorkflowComposer

    try:
        from spl3.executor import Executor
        from spl3.adapters import get_adapter
    except ImportError:
        raise click.ClickException("spl-llm 2.0 not installed: pip install spl-llm>=2.0.0")

    started_at = datetime.now()

    # Build registry: load all .spl files in the same directory
    local = LocalRegistry()
    local.load_dir(path.parent)
    click.echo(f"Registry: {local.list()}")

    # Optionally attach Hub registry
    registry = local
    if hub_url:
        from spl3.hub_registry import HubRegistry
        hub_reg = HubRegistry(hub_url)
        from spl3.registry import FederatedRegistry
        registry = FederatedRegistry(local, hub_reg)
        click.echo(f"Hub registry: {hub_url}")

    # Propagate --model into workflow @model param so USING MODEL @model picks it up.
    # Only set if the user hasn't already passed --param model=... explicitly.
    if model and "model" not in params:
        params["model"] = model

    # Build executor and attach composer for CALL workflow_name() dispatch
    adapter_kwargs = {"model": model} if model else {}
    if allowed_tools:
        adapter_kwargs["allowed_tools"] = [t.strip() for t in allowed_tools.split(",")]
    _inner_adapter = get_adapter(adapter_name, **adapter_kwargs)
    capturing = _CapturingAdapter(_inner_adapter)
    executor = Executor(adapter=capturing)
    executor.composer = WorkflowComposer(registry, executor)
    if log_prompts:
        executor.prompt_log_dir = log_prompts
        click.echo(f"Prompt logging → {log_prompts}/")

    # Load tools module (or auto-load tools.py from .spl directory)
    if tools_module:
        from spl.tools import load_tools_module
        loaded = load_tools_module(tools_module)
        for tool_name, tool_fn in loaded.items():
            executor.register_tool(tool_name, tool_fn)
        click.echo(f"Loaded {len(loaded)} tool(s) from {tools_module}")
    else:
        auto_tools = path.parent / "tools.py"
        if auto_tools.exists():
            from spl.tools import load_tools_module
            loaded = load_tools_module(str(auto_tools))
            for tool_name, tool_fn in loaded.items():
                executor.register_tool(tool_name, tool_fn)
            click.echo(f"Auto-loaded {len(loaded)} tool(s) from {auto_tools}")

    # Parse the file — needed for function registration and PROMPT fallback
    from spl.lexer import Lexer
    from spl.ast_nodes import CreateFunctionStatement, PromptStatement
    from spl3.parser import SPL3Parser
    from spl3._loader import load_workflows_from_file

    source = path.read_text(encoding="utf-8")
    _tokens = Lexer(source).tokenize()
    _program = SPL3Parser(_tokens).parse()

    # Register CREATE FUNCTION definitions so prompt templates are expanded
    for _stmt in _program.statements:
        if isinstance(_stmt, CreateFunctionStatement):
            executor.functions.register(_stmt)

    stem = path.stem.replace("-", "_")
    defns = load_workflows_from_file(path)

    if defns:
        # ── SPL 3.0 WORKFLOW path ──────────────────────────────────────────
        target = next((d for d in defns if d.name == stem), defns[-1])
        click.echo(f"Running workflow: {target.name}({list(params)})")

        result = await executor.execute_workflow(target.ast_node, params=params)

        resolved_model = capturing.last_model or model or ""
        click.echo(f"\nStatus:  {result.status}")
        click.echo(f"Output:  {result.committed_value or '(no COMMIT)'}")
        click.echo(f"LLM calls: {result.total_llm_calls}  "
                   f"Latency: {result.total_latency_ms:.0f}ms")
        log_result = result

    else:
        # ── SPL 2.0 PROMPT fallback ────────────────────────────────────────
        prompts = [s for s in _program.statements if isinstance(s, PromptStatement)]
        if not prompts:
            raise click.ClickException(
                f"No WORKFLOW or PROMPT definitions found in {path}"
            )

        from spl.analyzer import Analyzer
        analysis = Analyzer().analyze(_program)
        spl2_results = await executor.execute_program(analysis, params=params)

        for r in spl2_results:
            click.echo(f"\nStatus:     complete")
            click.echo(f"Output:     {getattr(r, 'content', '') or '(no output)'}")
            click.echo(f"LLM calls:  1")
            click.echo(f"Latency:    {getattr(r, 'latency_ms', 0):.0f}ms")
            toks_in  = getattr(r, "input_tokens",  0)
            toks_out = getattr(r, "output_tokens", 0)
            if toks_in:
                click.echo(f"Tokens:     {toks_in} in / {toks_out} out")

        resolved_model = capturing.last_model or model or getattr(spl2_results[0], "model", "") if spl2_results else model or ""
        log_result = spl2_results[-1] if spl2_results else None

    if log_result is not None:
        log_path = _write_run_log(
            stem=stem,
            adapter_name=adapter_name,
            model_name=resolved_model,
            source=source,
            last_prompt=capturing.last_prompt,
            result=log_result,
            started_at=started_at,
        )
        click.echo(f"Log:     {log_path}")


# ------------------------------------------------------------------ #
# spl registry                                                        #
# ------------------------------------------------------------------ #

@main.group()
def registry():
    """Manage the workflow registry."""


@registry.command("list")
@click.pass_context
def registry_list(ctx):
    """List all registered workflows."""
    hub_url = ctx.obj.get("hub")
    if hub_url:
        from spl3.hub_registry import HubRegistry
        reg = HubRegistry(hub_url)
        workflows = reg.list()
        click.echo(f"Hub {hub_url}: {len(workflows)} workflow(s)")
        for wf in workflows:
            click.echo(f"  {wf}")
    else:
        click.echo("No --hub specified. Use --hub <url> to query Hub registry.")


@main.command()
@click.argument("path")
@click.pass_context
def register(ctx, path):
    """Register workflows from a .spl file or directory into the Hub."""
    from pathlib import Path
    from spl3.registry import LocalRegistry

    hub_url = ctx.obj.get("hub")
    if not hub_url:
        raise click.ClickException("--hub <url> required for spl register")

    local = LocalRegistry()
    p = Path(path)
    if p.is_dir():
        count = local.load_dir(p)
    else:
        count = local.load_file(p)

    from spl3.hub_registry import HubRegistry
    hub_reg = HubRegistry(hub_url)

    # Push each workflow definition to the Hub
    from spl3.registry import WorkflowDefinition
    registered = 0
    for name in local.list():
        defn: WorkflowDefinition = local.get(name)
        try:
            hub_reg.register(defn.name, defn.source_text)
            click.echo(f"  Registered: {name}")
            registered += 1
        except Exception as e:
            click.echo(f"  Failed {name}: {e}", err=True)

    click.echo(f"\nRegistered {registered}/{count} workflow(s) on {hub_url}")


# ------------------------------------------------------------------ #
# spl peers                                                           #
# ------------------------------------------------------------------ #

@main.group()
def peers():
    """Manage Hub-to-Hub peering."""


@peers.command("list")
@click.pass_context
def peers_list(ctx):
    """List peer Hubs."""
    hub_url = ctx.obj.get("hub")
    if not hub_url:
        raise click.ClickException("--hub <url> required")
    import httpx
    try:
        resp = httpx.get(f"{hub_url}/peer/list", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for peer in data.get("peers", []):
            click.echo(f"  {peer['url']}  tier={peer.get('tier','?')}  "
                       f"workflows={len(peer.get('workflows',[]))}")
    except Exception as e:
        raise click.ClickException(str(e))


@peers.command("add")
@click.argument("peer_url")
@click.pass_context
def peers_add(ctx, peer_url):
    """Add a peer Hub (peering handshake)."""
    hub_url = ctx.obj.get("hub")
    if not hub_url:
        raise click.ClickException("--hub <url> required")
    import httpx
    try:
        resp = httpx.post(
            f"{hub_url}/peer/add",
            json={"peer_url": peer_url},
            timeout=15,
        )
        resp.raise_for_status()
        click.echo(f"Peering established: {hub_url} <-> {peer_url}")
    except Exception as e:
        raise click.ClickException(str(e))


# ------------------------------------------------------------------ #
# spl test                                                            #
# ------------------------------------------------------------------ #

@main.command("test")
@click.argument("spl_file_or_dir")
@click.option("--adapter", default="ollama", show_default=True)
@click.option("--model", default=None, show_default=True)
@click.option("--verbose", "-v", is_flag=True)
@click.pass_context
def cmd_test(ctx, spl_file_or_dir, adapter, model, verbose):
    """Run pipeline-level tests for .spl workflows.

    Looks for test fixtures alongside .spl files:
      generate_code.spl          — workflow under test
      generate_code.test.yaml    — test cases (inputs + expected assertions)

    Test YAML format:
    \b
      - name: "basic generation"
        params:
          spec: "Write a hello-world function in Python"
        assert:
          contains: ["def ", "print"]
          status: complete
    """
    from pathlib import Path
    path = Path(spl_file_or_dir)
    if path.is_dir():
        spl_files = list(path.rglob("*.spl"))
    else:
        spl_files = [path]

    if not spl_files:
        click.echo("No .spl files found.")
        return

    asyncio.run(_run_tests(spl_files, adapter, model, verbose))


async def _run_tests(spl_files, adapter_name, model, verbose):
    import yaml
    from spl3.registry import LocalRegistry

    try:
        from spl3.executor import Executor
        from spl3.adapters import get_adapter
    except ImportError:
        raise click.ClickException("spl-llm 2.0 not installed: pip install spl-llm>=2.0.0")

    adapter_kwargs = {"model": model} if model else {}
    adapter = get_adapter(adapter_name, **adapter_kwargs)
    executor = Executor(adapter=adapter)

    total = passed = failed = skipped = 0

    for spl_file in sorted(spl_files):
        test_file = spl_file.with_suffix("").with_suffix(".test.yaml")
        if not test_file.exists():
            _log.debug("No test file for %s — skipping", spl_file.name)
            continue

        from spl3._loader import load_workflows_from_file
        defns = load_workflows_from_file(spl_file)
        if not defns:
            continue

        cases = yaml.safe_load(test_file.read_text(encoding="utf-8")) or []
        target = defns[-1]
        click.echo(f"\n{spl_file.name} [{target.name}]  ({len(cases)} test(s))")

        for case in cases:
            total += 1
            name = case.get("name", f"case-{total}")
            params = case.get("params", {})
            assertions = case.get("assert", {})

            try:
                result = await executor.execute_workflow(target.ast_node, params=params)
                output = str(result.committed_value or "")
                status = result.status

                ok = True
                failures = []
                for fragment in assertions.get("contains", []):
                    if fragment not in output:
                        ok = False
                        failures.append(f"output missing {fragment!r}")
                expected_status = assertions.get("status")
                if expected_status and status != expected_status:
                    ok = False
                    failures.append(f"status={status!r}, expected={expected_status!r}")

                if ok:
                    passed += 1
                    click.echo(f"  ✓ {name}")
                else:
                    failed += 1
                    click.echo(f"  ✗ {name}: {'; '.join(failures)}")
                    if verbose:
                        click.echo(f"    output: {output[:200]}")
            except Exception as exc:
                failed += 1
                click.echo(f"  ✗ {name}: {exc}")

    skipped = total - passed - failed
    click.echo(
        f"\n{'─'*50}\n"
        f"Results: {passed} passed, {failed} failed, {skipped} skipped  ({total} total)"
    )
    if failed:
        raise SystemExit(1)


# ------------------------------------------------------------------ #
# spl code-rag                                                        #
# ------------------------------------------------------------------ #

@main.group("code-rag")
def cmd_code_rag():
    """Manage the Code-RAG index for Text2SPL."""


@cmd_code_rag.command("seed")
@click.argument("cookbook_dir", default="cookbook")
@click.option("--storage-dir", default=".spl/code_rag", show_default=True,
              help="Directory for the RAG vector store.")
@click.option("--catalog", default=None,
              help="Seed from cookbook_catalog.json (curated one-liner descriptions).")
@click.option("--from-specs", is_flag=True, default=False,
              help=(
                  "Seed using Section 0 from describe-generated *-spec.md files. "
                  "Gives the richest SPL-aware descriptions. Run 'code-rag describe-all' first."
              ))
@click.option("--all-active/--no-filter", default=True, show_default=True,
              help="When seeding from catalog, skip inactive/disabled entries.")
def code_rag_seed(cookbook_dir, storage_dir, catalog, from_specs, all_active):
    """Seed the Code-RAG index from a cookbook directory.

    Three seeding modes (in increasing description quality):

    \b
    1. Default — file header comments as descriptions:
         spl3 code-rag seed cookbook/

    \b
    2. Catalog — curated one-liner descriptions from cookbook_catalog.json:
         spl3 code-rag seed --catalog cookbook/cookbook_catalog.json

    \b
    3. Specs — rich SPL-aware Section 0 from describe-generated spec files (best):
         spl3 code-rag describe-all cookbook/ --adapter claude_cli
         spl3 code-rag seed cookbook/ --from-specs
    """
    from spl3.code_rag import CodeRAGStore
    store = CodeRAGStore(storage_dir=storage_dir)

    if from_specs:
        count = store.seed_from_specs(cookbook_dir)
        click.echo(f"Seeded {count} workflow(s) from describe-spec files under {cookbook_dir}")
    elif catalog:
        count = store.seed_from_catalog(catalog, only_active=all_active)
        click.echo(f"Seeded {count} workflow(s) from catalog {catalog}")
    else:
        count = store.seed_from_dir(cookbook_dir)
        click.echo(f"Seeded {count} workflow(s) from directory {cookbook_dir}")

    click.echo(f"Total indexed: {store.count()}")


@cmd_code_rag.command("query")
@click.argument("query_text")
@click.option("--storage-dir", default=".spl/code_rag", show_default=True)
@click.option("--top-k", default=3, show_default=True)
def code_rag_query(query_text, storage_dir, top_k):
    """Query the Code-RAG index and print matching SPL examples."""
    from spl3.code_rag import CodeRAGStore
    store = CodeRAGStore(storage_dir=storage_dir)
    hits = store.retrieve(query_text, top_k=top_k)
    if not hits:
        click.echo("No results.")
        return
    for i, hit in enumerate(hits, 1):
        click.echo(f"\n── Example {i} (score={hit['score']:.3f}) ─────────────────")
        click.echo(f"Description: {hit['description']}")
        click.echo(hit["spl_source"][:500])


@cmd_code_rag.command("describe-all")
@click.argument("cookbook_dir", default="cookbook")
@click.option("--adapter", default="ollama", show_default=True,
              help="LLM adapter used to generate each spec.")
@click.option("--model", default=None, metavar="MODEL")
@click.option("--spec-dir", default=None, metavar="DIR",
              help="Write all spec files to DIR instead of alongside each .spl file.")
@click.option("--catalog", default=None,
              help="Restrict to active recipes listed in cookbook_catalog.json.")
@click.option("--skip-existing", is_flag=True, default=True, show_default=True,
              help="Skip recipes that already have a -spec.md file.")
def code_rag_describe_all(cookbook_dir, adapter, model, spec_dir, catalog, skip_existing):
    """Batch-generate describe specs for all canonical cookbook recipes.

    Runs 'spl3 describe' on each .spl file and writes a *-spec.md alongside it
    (or to --spec-dir). After this completes, run:

    \b
      spl3 code-rag seed cookbook/ --from-specs

    to index the rich Section 0 descriptions into the RAG store.

    \b
    Examples:
      spl3 code-rag describe-all cookbook/ --adapter claude_cli
      spl3 code-rag describe-all cookbook/ --adapter claude_cli --catalog cookbook/cookbook_catalog.json
    """
    import json as _json

    cookbook_path = Path(cookbook_dir)
    if not cookbook_path.is_dir():
        raise click.ClickException(f"Not a directory: {cookbook_dir}")

    # Build candidate file list
    if catalog:
        catalog_data = _json.loads(Path(catalog).read_text(encoding="utf-8"))
        entries = catalog_data if isinstance(catalog_data, list) else catalog_data.get("recipes", [])
        spl_files = []
        for entry in entries:
            if not entry.get("is_active", True):
                continue
            if entry.get("approval_status", "approved") in ("disabled", "rejected"):
                continue
            if "args" in entry and len(entry["args"]) > 2:
                # args[2] is project-root-relative, e.g. "./cookbook/05_.../self_refine.spl"
                p = Path(entry["args"][2].lstrip("./"))
                if p.exists():
                    spl_files.append(p)
    else:
        # All .spl files under cookbook_dir, excluding generated variants
        spl_files = [
            p for p in sorted(cookbook_path.rglob("*.spl"))
            if "generated-" not in str(p)
        ]

    total = len(spl_files)
    click.echo(f"Describing {total} recipe(s) with adapter={adapter} ...")

    try:
        from spl3.adapters import get_adapter
    except ImportError:
        raise click.ClickException("spl-llm 2.0 not installed: pip install spl-llm>=2.0.0")

    adapter_kwargs = {"model": model} if model else {}
    llm = get_adapter(adapter, **adapter_kwargs)

    done = skipped = failed = 0
    for spl_file in spl_files:
        stem = spl_file.stem
        if spec_dir:
            out_dir = Path(spec_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            spec_path = out_dir / f"{stem}-spec.md"
        else:
            spec_path = spl_file.parent / f"{stem}-spec.md"

        if skip_existing and spec_path.exists():
            click.echo(f"  [skip]  {spl_file.name}  (spec exists)")
            skipped += 1
            continue

        try:
            source = spl_file.read_text(encoding="utf-8")
            prompt = _DESCRIBE_PROMPT.format(source=source)
            result = asyncio.run(llm.generate(
                prompt, **({"model": model} if model else {})
            ))
            spec_text = result if isinstance(result, str) else getattr(result, "content", str(result))
            spec_path.write_text(spec_text, encoding="utf-8")
            click.echo(f"  [ok]    {spl_file.name}  -> {spec_path.name}")
            done += 1
        except Exception as exc:
            click.echo(f"  [fail]  {spl_file.name}: {exc}", err=True)
            failed += 1

    click.echo(f"\nDone: {done} generated, {skipped} skipped, {failed} failed  ({total} total)")
    if done:
        click.echo("\nNext step — seed RAG from specs:")
        click.echo(f"  spl3 code-rag seed {cookbook_dir} --from-specs")


@cmd_code_rag.command("stats")
@click.option("--storage-dir", default=".spl/code_rag", show_default=True)
def code_rag_stats(storage_dir):
    """Show Code-RAG index statistics."""
    from spl3.code_rag import CodeRAGStore
    store = CodeRAGStore(storage_dir=storage_dir)
    click.echo(f"Code-RAG store: {storage_dir}")
    click.echo(f"  Indexed pairs: {store.count()}")


# ------------------------------------------------------------------ #
# spl3 text2spl                                                       #
# ------------------------------------------------------------------ #

@main.command("text2spl")
@click.argument("description", required=False, default=None)
@click.option("--description", "-d", "description_opt", default=None, metavar="TEXT_OR_FILE",
              help="Natural language description, a file path, or a -spec.md file "
                   "(Section 0 is extracted automatically).")
@click.option("--adapter", default=None, metavar="NAME",
              help="Compiler adapter (default: ollama).")
@click.option("--model", "-m", default=None, metavar="MODEL",
              help="Compiler model.")
@click.option("--mode", type=click.Choice(["auto", "prompt", "workflow"]),
              default="auto", show_default=True,
              help="Generation mode.")
@click.option("--validate/--no-validate", default=True, show_default=True,
              help="Validate generated SPL code.")
@click.option("--output", "-o", default=None, metavar="FILE",
              help="Write generated SPL to FILE.")
def cmd_text2spl(description, description_opt, adapter, model, mode, validate, output):
    """Compile natural language DESCRIPTION into SPL 3.0 code.

    DESCRIPTION may be:
      - a literal string passed as a positional argument or via --description
      - a path to a plain text / markdown file (full file used as description)
      - a path to a *-spec.md file (Section 0 is extracted automatically)

    \b
    Examples:
      spl3 text2spl "summarize a document with a 2000 token budget"
      spl3 text2spl --description flow-splc-python_pocketflow-spec.md --mode workflow -o agent.spl
      spl3 text2spl "build a review agent" --mode workflow -o review.spl
      spl3 text2spl "classify intent" --adapter ollama -m gemma3
    """
    import re as _re
    from spl.text2spl import Text2SPL
    from spl.adapters import get_adapter

    # Resolve description: --description option takes precedence over positional arg
    raw = description_opt or description
    if not raw:
        raise click.UsageError(
            "Provide a description as a positional argument or via --description."
        )

    # If it looks like a file path, read it
    candidate = Path(raw)
    if candidate.exists() and candidate.is_file():
        content = candidate.read_text(encoding="utf-8")
        # If it's a -spec.md, extract Section 0
        if candidate.name.endswith("-spec.md") or candidate.suffix == ".md":
            # Match "## 0. ..." up to the next "## " heading or end of file
            m = _re.search(
                r"^##\s*0\..*?\n(.*?)(?=^##\s|\Z)",
                content,
                _re.MULTILINE | _re.DOTALL,
            )
            if m:
                section0 = m.group(1).strip()
                click.echo(f"Extracted Section 0 from {candidate.name} "
                           f"({len(section0)} chars)", err=True)
                raw = section0
            else:
                click.echo(f"No 'Section 0' heading found in {candidate.name} — "
                           "using full file content.", err=True)
                raw = content.strip()
        else:
            raw = content.strip()

    adapter = adapter or "ollama"
    try:
        llm = get_adapter(adapter, **({"model": model} if model else {}))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    compiler = Text2SPL(adapter=llm)
    try:
        spl_code = asyncio.run(compiler.compile(raw, mode=mode))
    except Exception as exc:
        raise click.ClickException(f"Compilation failed: {exc}") from exc

    if validate:
        valid, message = Text2SPL.validate_output(spl_code)
        if not valid:
            if output:
                Path(output).write_text(spl_code, encoding="utf-8")
                click.echo(f"Written to {output} (with validation errors — review and fix)")
            else:
                click.echo(spl_code)
            click.echo(f"Warning: {message}", err=True)
            raise SystemExit(1)

    if output:
        Path(output).write_text(spl_code, encoding="utf-8")
        click.echo(f"Written to {output}")
    else:
        click.echo(spl_code)


# ------------------------------------------------------------------ #
# Mermaid Syntax Post-Processor                                        #
# ------------------------------------------------------------------ #

def fix_mermaid_syntax(mermaid_text, style="flowchart"):
    """
    Rule-based post-processor to fix common LLM Mermaid syntax errors.

    Handles:
    - Single braces {Decision} → Double braces {{Decision}}
    - Wrong arrows -> → Correct arrows -->
    - Missing diagram declaration
    """
    import re

    lines = mermaid_text.strip().split('\n')
    fixed_lines = []

    # Ensure diagram declaration
    has_declaration = any(line.strip().startswith(('flowchart', 'graph', 'sequenceDiagram')) for line in lines)
    if not has_declaration:
        fixed_lines.append(f"{style} TD")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith(('flowchart', 'graph', 'sequenceDiagram')):
            fixed_lines.append(line)
            continue

        # Fix arrow syntax: -> becomes -->
        line = re.sub(r'(?<!-)->(?!>)', '-->', line)

        # Fix single braces to double braces for decisions: {text} → {{text}}
        # This is the critical fix for the reported error
        # Only replace single braces, avoid creating triple braces
        line = re.sub(r'([A-Z])\{([^}]+)\}(?!\})', r'\1{{\2}}', line)

        # Add proper indentation
        if line and not line.startswith('    '):
            line = "    " + line

        fixed_lines.append(line)

    return '\n'.join(fixed_lines)

def fix_node_syntax(text, node_map, node_id_counter):
    """Fix individual node syntax"""
    import re

    text = text.strip()
    if not text:
        return text

    # Already properly formatted node: A[Label] or A{{Label}}
    if re.match(r'^[A-Z]\[.*\]$', text) or re.match(r'^[A-Z]\{\{.*\}\}$', text):
        return text

    # Decision node with proper ID but wrong braces: A{Label}
    decision_match = re.match(r'^([A-Z])\{([^}]+)\}$', text)
    if decision_match:
        node_id, label = decision_match.groups()
        return f"{node_id}{{{{{label}}}}}"

    # Node with proper ID: A[Label]
    node_match = re.match(r'^([A-Z])\[([^\]]+)\]$', text)
    if node_match:
        return text  # Already correct

    # Unbracketed text - need to assign ID and format
    if text not in node_map:
        node_id = chr(node_id_counter[0])
        node_map[text] = node_id
        node_id_counter[0] += 1
    else:
        node_id = node_map[text]

    # Determine if it should be a decision node (contains question words or ends with ?)
    if any(word in text.lower() for word in ['check', 'verify', 'validate', '?', 'ok', 'pass', 'fail', 'approved', 'decision']):
        return f"{node_id}{{{{{text}}}}}"
    else:
        return f"{node_id}[{text}]"


# ------------------------------------------------------------------ #
# spl3 text2mmd                                                       #
# ------------------------------------------------------------------ #

@main.command("text2mmd")
@click.argument("description", required=False, default=None)
@click.option("--description", "-d", "description_opt", default=None, metavar="TEXT_OR_FILE",
              help="Natural language workflow description or file path.")
@click.option("--adapter", default="ollama", show_default=True, metavar="NAME",
              help="LLM adapter to use.")
@click.option("--model", "-m", default=None, metavar="MODEL",
              help="Model override for the adapter.")
@click.option("--style", default="flowchart", show_default=True,
              type=click.Choice(["flowchart", "graph", "sequence"]),
              help="Mermaid diagram style.")
@click.option("--output", "-o", default=None, metavar="FILE",
              help="Write generated Mermaid to FILE.")
@click.option("--validate/--no-validate", default=True, show_default=True,
              help="Validate generated Mermaid syntax.")
@click.option("--preview", is_flag=True, default=True,
              help="Open diagram in browser preview.")
@click.option("--save-markdown", "--save-md", is_flag=True, default=True,
              help="Save as .md file with mermaid code blocks (VS Code compatible).")
@click.option("--save-html", is_flag=True, default=True,
              help="Save as .html file for browser viewing.")
@click.option("--save-png", is_flag=True, default=True,
              help="Save as .png image file using headless browser.")
@click.option("--out-dir", default=None, metavar="DIR",
              help="Output directory (default: $HOME/.spl/mermaid).")
@click.option("--no-defaults", is_flag=True, default=False,
              help="Disable default --save-html, --save-markdown, --preview.")
def cmd_text2mmd(description, description_opt, adapter, model, style, output, validate, preview, save_markdown, save_html, save_png, out_dir, no_defaults):
    """Generate Mermaid flowchart from natural language workflow description.

    This creates a visual representation of the workflow that can be reviewed
    and edited before converting to SPL code.

    \b
    Examples:
      spl3 text2mmd "build a review agent that refines text until quality > 0.8"
      spl3 text2mmd --description "research workflow" -o research.mmd
      spl3 text2mmd "parallel code review" --style flowchart --preview
    """
    import re as _re
    import sys
    import os
    from pathlib import Path

    try:
        from spl.adapters import get_adapter
    except ImportError:
        raise click.ClickException("spl adapters not available")

    # Handle --no-defaults flag
    if no_defaults:
        save_html = False
        save_markdown = False
        save_png = False
        preview = False

    # Setup output directory
    if out_dir is None:
        out_dir = Path.home() / ".spl" / "mermaid"
    else:
        out_dir = Path(out_dir)

    # Create output directory if it doesn't exist
    out_dir.mkdir(parents=True, exist_ok=True)

    # Setup default output file if not provided
    if output is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = out_dir / f"workflow_{timestamp}.mmd"
    else:
        # If output provided, use it but place in out_dir if it's just a filename
        output_path = Path(output)
        if not output_path.is_absolute() and output_path.parent == Path('.'):
            output = out_dir / output_path
        else:
            output = output_path

    # --description option takes precedence over positional arg
    raw = description_opt or description
    if not raw:
        raise click.ClickException("DESCRIPTION is required (positional arg or --description)")

    # Check if it's a file path
    if Path(raw).exists():
        desc_text = Path(raw).read_text(encoding="utf-8")
    else:
        desc_text = raw

    # Generate Mermaid diagram
    llm = get_adapter(adapter, **{"model": model} if model else {})

    prompt = f"""Create a valid Mermaid {style} diagram from this workflow description.

Workflow Description:
{desc_text}

MANDATORY SYNTAX RULES:
1. Node format: A[Label Text] where A is ID, Label Text is in square brackets
2. Decision format: C{{{{Decision Text}}}} - MUST use DOUBLE braces, never single braces
3. Connections: A --> B or A -->|label| B
4. Start with: {style} TD

CORRECT Examples:
- Process node: A[Start], B[Process Data], C[Generate Output]
- Decision node: D{{{{Quality OK?}}}}, E{{{{Approved?}}}}
- Connections: A --> B, C -->|Yes| D, C -->|No| E

WRONG Examples (DO NOT USE):
- C{{Decision}} ❌ (single braces)
- Process Input ❌ (no brackets/ID)
- A[Start] -> B ❌ (use --> not ->)

Generate ONLY the diagram code. No explanations. Follow the format exactly:

```mermaid
{style} TD
    A[Start] --> B[Process Request]
    B --> C{{{{Quality Check}}}}
    C -->|Pass| D[Approve]
    C -->|Fail| E[Reject]
    D --> F[End]
    E --> F[End]
```"""

    result = asyncio.run(llm.generate(prompt, **({"model": model} if model else {})))
    mermaid_text = result if isinstance(result, str) else getattr(result, "content", str(result))

    # Extract mermaid code from markdown if present
    if "```mermaid" in mermaid_text:
        mermaid_match = _re.search(r"```mermaid\s*\n(.*?)\n```", mermaid_text, _re.DOTALL)
        if mermaid_match:
            mermaid_text = mermaid_match.group(1).strip()

    # Apply rule-based post-processing to fix common LLM syntax errors
    mermaid_text = fix_mermaid_syntax(mermaid_text, style)

    # Enhanced validation
    if validate:
        validation_errors = []

        # Check for basic Mermaid syntax
        if not any(keyword in mermaid_text for keyword in ["flowchart", "graph", "sequenceDiagram"]):
            validation_errors.append("Missing diagram type (flowchart, graph, or sequenceDiagram)")

        # Check for common syntax errors
        lines = mermaid_text.split('\n')
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            # Check for unquoted node labels with spaces
            if '-->' in line:
                # Extract parts around arrows
                parts = _re.split(r'\\s*(?:-->|->)\\s*', line)
                for part in parts:
                    part = part.strip()
                    # Skip edge labels in pipes |label|
                    if '|' in part and not (part.startswith('|') and part.endswith('|')):
                        continue
                    # Check for unbracketed labels with spaces
                    if ' ' in part and not (_re.match(r'\\w+\\[.*\\]', part) or _re.match(r'\\w+\\{.*\\}', part)):
                        validation_errors.append("Line " + str(i) + ": Node '" + part + "' has spaces but no brackets - use A[" + part + "]")

            # Check for single braces instead of double braces for decisions
            if '{' in line and '{{' not in line:
                validation_errors.append("Line " + str(i) + ": Decision nodes should use double braces {{ }} not single braces { }")

        # Check for circular references to Start
        if 'Start' in mermaid_text and '-->' in mermaid_text:
            # Look for patterns like "End --> Start" or "end --> Start"
            if _re.search(r'(?:End|end|F)\\s*-->\\s*(?:Start|start|A)', mermaid_text):
                validation_errors.append("Circular reference detected: workflow loops back to Start")

        if validation_errors:
            click.echo("Mermaid syntax warnings:", err=True)
            for error in validation_errors:
                click.echo("  - " + error, err=True)
            click.echo("Note: These may cause rendering issues in browsers", err=True)

    # Main .mmd output
    Path(output).write_text(mermaid_text, encoding="utf-8")
    click.echo("Mermaid diagram written to: " + str(output))

    output_path = Path(output)
    base_name = output_path.stem
    output_dir = output_path.parent

    # Generate additional formats
    additional_files = []

    # Markdown format for VS Code preview
    if save_markdown:
        cmd_line = ' '.join(['spl3', 'text2mmd'] + sys.argv[2:])
        title = base_name.title().replace('_', ' ').replace('-', ' ')

        markdown_content = "# " + title + " Workflow\n\n"
        markdown_content += "Generated with [SPL](https://github.com/digital-duck/SPL) using: `" + cmd_line + "`\n\n"
        markdown_content += "## Mermaid Diagram\n\n"
        markdown_content += "```mermaid\n" + mermaid_text + "\n```\n\n"
        markdown_content += "## Usage Options\n\n"
        markdown_content += "### For SPL Development\n"
        markdown_content += "1. Review the workflow diagram above\n"
        markdown_content += "2. Edit the mermaid code if needed\n"
        markdown_content += "3. Generate SPL code: `spl3 mmd2spl " + str(output) + " -o " + base_name + ".spl`\n"
        markdown_content += "4. Validate: `spl3 validate " + base_name + ".spl`\n\n"
        markdown_content += "### For General Use\n"
        markdown_content += "1. Use the `.mmd` file with any Mermaid-compatible tool\n"
        markdown_content += "2. Copy the diagram code for documentation, presentations, or websites\n"
        markdown_content += "3. Edit the visual workflow and regenerate as needed\n\n"
        markdown_content += "---\n\n"
        markdown_content += "**Learn more**: [SPL Repository](https://github.com/digital-duck/SPL) | [Documentation](https://github.com/digital-duck/SPL#readme)\n"
        md_path = output_dir / (base_name + ".md")
        md_path.write_text(markdown_content, encoding="utf-8")
        additional_files.append("Markdown (VS Code): " + str(md_path))

    # HTML format for browser viewing
    if save_html or preview:
        title = base_name.title().replace('_', ' ').replace('-', ' ')
        filename = Path(output).name

        # Build HTML content with proper escaping
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            '    <meta charset="UTF-8">',
            '    <title>' + title + ' - Mermaid Workflow</title>',
            '    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>',
            "    <style>",
            "        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }",
            "        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }",
            "        .header { border-bottom: 2px solid #eee; margin-bottom: 20px; padding-bottom: 10px; }",
            "        .mermaid { text-align: center; margin: 20px 0; min-height: 200px; }",
            "        .footer { margin-top: 20px; padding-top: 10px; border-top: 1px solid #eee; color: #666; font-size: 0.9em; }",
            "        .raw-code { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 4px; padding: 15px; margin: 20px 0; font-family: 'Courier New', monospace; white-space: pre-wrap; }",
            "        .error-info { background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; padding: 15px; margin: 20px 0; }",
            "    </style>",
            "</head>",
            "<body>",
            '    <div class="container">',
            '        <div class="header">',
            "            <h1>" + title + " Workflow</h1>",
            '            <p><strong>Generated with <a href="https://github.com/digital-duck/SPL" target="_blank">SPL</a></strong></p>',
            "            <p><strong>File:</strong> " + filename + " | <strong>Style:</strong> " + style + " | <strong>Adapter:</strong> " + adapter + "</p>",
            "        </div>",
            '        <div id="mermaid-container" class="mermaid">',
            mermaid_text,
            "        </div>",
            '        <div id="error-container" class="error-info" style="display: none;">',
            "            <h3>⚠️ Mermaid Syntax Error</h3>",
            "            <p>The diagram couldn't be rendered. This often happens due to:</p>",
            "            <ul>",
            "                <li>Invalid node naming (spaces without brackets)</li>",
            "                <li>Incorrect edge syntax</li>",
            "                <li>Circular references</li>",
            "            </ul>",
            "            <p><strong>Generated Code:</strong></p>",
            '            <div class="raw-code">' + mermaid_text + "</div>",
            "            <p>Please edit the <code>" + filename + "</code> file to fix syntax issues.</p>",
            "        </div>",
            '        <div class="footer">',
            "            <p><strong>Usage Options:</strong></p>",
            "            <p><strong>For SPL:</strong> Generate code with <code>spl3 mmd2spl " + filename + " -o " + base_name + ".spl</code></p>",
            "            <p><strong>For General Use:</strong> Copy diagram code for documentation, presentations, or other Mermaid tools</p>",
            '            <hr style="margin: 20px 0;">',
            '            <p><strong>About SPL:</strong> <a href="https://github.com/digital-duck/SPL" target="_blank">GitHub Repository</a> |',
            '               <a href="https://github.com/digital-duck/SPL#readme" target="_blank">Documentation</a></p>',
            '            <p><small>Visual workflow programming • General purpose workflow visualization tool</small></p>',
            "        </div>",
            "    </div>",
            "    <script>",
            "        mermaid.initialize({",
            "            startOnLoad: true,",
            "            theme: 'default',",
            "            securityLevel: 'loose',",
            "            errorLevel: 'warn'",
            "        });",
            "        window.addEventListener('error', function(e) {",
            "            if (e.message && e.message.toLowerCase().includes('mermaid')) {",
            "                document.getElementById('mermaid-container').style.display = 'none';",
            "                document.getElementById('error-container').style.display = 'block';",
            "            }",
            "        });",
            "        setTimeout(function() {",
            "            const container = document.getElementById('mermaid-container');",
            "            if (container && (container.innerHTML.includes('Syntax error') || container.innerHTML.includes('Parse error'))) {",
            "                container.style.display = 'none';",
            "                document.getElementById('error-container').style.display = 'block';",
            "            }",
            "        }, 2000);",
            "    </script>",
            "</body>",
            "</html>"
        ]
        html_content = "\n".join(html_parts)
        html_path = output_dir / (base_name + ".html")
        html_path.write_text(html_content, encoding="utf-8")
        additional_files.append("HTML (Browser): " + str(html_path))

        if preview:
            import webbrowser
            webbrowser.open("file://" + str(html_path.absolute()))
            click.echo("Preview opened in browser: " + str(html_path))

    # PNG format for images/presentations
    if save_png:
        png_path = output_dir / (base_name + ".png")
        try:
            png_generated = False
            import subprocess

            # Create a simple HTML for PNG generation
            png_html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>body{margin:0;padding:20px;background:white;font-family:Arial,sans-serif}
.mermaid{text-align:center}</style></head>
<body><div class="mermaid">""" + mermaid_text + """</div>
<script>mermaid.initialize({startOnLoad:true,theme:'default',securityLevel:'loose'});</script>
</body></html>"""

            png_html_path = output_dir / (base_name + "_temp.html")
            png_html_path.write_text(png_html, encoding="utf-8")

            # Try Chrome/Chromium browsers
            for chrome_cmd in ["google-chrome", "chromium-browser", "chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]:
                try:
                    result = subprocess.run([
                        chrome_cmd, "--headless", "--disable-gpu",
                        "--window-size=1200,800", "--screenshot=" + str(png_path),
                        "file://" + str(png_html_path.absolute())
                    ], capture_output=True, timeout=30)

                    if result.returncode == 0 and png_path.exists():
                        png_html_path.unlink()  # Clean up
                        additional_files.append("PNG Image: " + str(png_path))
                        png_generated = True
                        break
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue

            # Clean up temp file
            if png_html_path.exists():
                png_html_path.unlink()

            if not png_generated:
                click.echo("Warning: PNG generation requires Chrome/Chromium browser", err=True)

        except Exception as e:
            click.echo("Warning: PNG generation failed: " + str(e), err=True)

    # Report additional files
    if additional_files:
        click.echo("Additional formats generated:")
        for file_desc in additional_files:
            click.echo("  - " + file_desc)

    # Summary
    click.echo("\nAll files saved to: " + str(output_dir))


# ------------------------------------------------------------------ #
# spl3 mmd2spl                                                    #
# ------------------------------------------------------------------ #

@main.command("mmd2spl")
@click.argument("mermaid_file")
@click.option("--adapter", default="ollama", show_default=True, metavar="NAME",
              help="LLM adapter to use.")
@click.option("--model", "-m", default=None, metavar="MODEL",
              help="Model override for the adapter.")
@click.option("--output", "-o", default=None, metavar="FILE",
              help="Write generated SPL to FILE.")
@click.option("--validate/--no-validate", default=True, show_default=True,
              help="Validate generated SPL syntax.")
@click.option("--template", default="workflow", show_default=True,
              type=click.Choice(["workflow", "function"]),
              help="Base SPL template type.")
@click.option("--pattern-hints", default=None, metavar="HINTS",
              help="Comma-separated hints for SPL patterns (e.g., 'react,self_refine').")
def cmd_mmd2spl(mermaid_file, adapter, model, output, validate, template, pattern_hints):
    """Generate SPL workflow from Mermaid flowchart diagram.

    Converts a Mermaid flowchart into executable SPL code using an LLM, mapping
    visual elements to SPL constructs like GENERATE, EVALUATE, WHILE, and CALL PARALLEL.

    \b
    Examples:
      spl3 mmd2spl workflow.mmd -o workflow.spl
      spl3 mmd2spl diagram.mmd --adapter claude_cli --model claude-sonnet-4-6 -o agent.spl
      spl3 mmd2spl review.mmd --adapter gemini_cli --model gemini-3-flash-preview -o review.spl
      spl3 mmd2spl diagram.mmd --template function --validate
    """
    import re as _re
    from pathlib import Path
    from spl.adapters import get_adapter
    from spl.text2spl import Text2SPL

    # Read Mermaid file
    mermaid_path = Path(mermaid_file)
    if not mermaid_path.exists():
        raise click.ClickException(f"Mermaid file not found: {mermaid_file}")

    mermaid_content = mermaid_path.read_text(encoding="utf-8")
    workflow_name = mermaid_path.stem.replace("-", "_")

    # Build LLM adapter
    try:
        llm = get_adapter(adapter, **{"model": model} if model else {})
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    # Build prompt
    hints_clause = f"\nPattern hints: {pattern_hints}" if pattern_hints else ""
    template_clause = (
        "Generate a WORKFLOW ... DO ... END block."
        if template == "workflow"
        else "Generate a CREATE FUNCTION ... AS $$ ... $$ block."
    )

    prompt = f"""Convert the following Mermaid flowchart into valid SPL 3.0 code.

Mermaid diagram:
```mermaid
{mermaid_content}
```

Target template: {template_clause}{hints_clause}

STRICT SPL SYNTAX RULES:

1. TYPES: Use TEXT, INTEGER, FLOAT, BOOL only. Never use STRING.

2. CREATE FUNCTION must be TOP-LEVEL (before the WORKFLOW block, never inside DO...END):
   CREATE FUNCTION <name>(<param> TEXT) RETURNS TEXT AS $$
   <natural language prompt instructions using {{param}} placeholders>
   $$;

3. WORKFLOW structure:
   WORKFLOW {workflow_name}
     INPUT @<name> TEXT [, ...]
     OUTPUT @<name> TEXT
   DO
     ...statements...
   END;

4. Statements inside DO...END:
   - GENERATE <fn>(@arg1, @arg2) INTO @var;
   - CALL <tool>(@arg) INTO @var;
   - EVALUATE @var
       WHEN contains('<text>') THEN
         ...
       ELSE
         ...
     END;
   - WHILE @i < @max DO ... END;
   - RETURN @var WITH status = 'complete';
   - @var := <expr>;
   - CALL PARALLEL
       <fn1>(@arg) INTO @var1,
       <fn2>(@arg) INTO @var2
     END;

5. FORBIDDEN — never use these:
   - No comments of any kind (no //, no --, no #)
   - No BREAK keyword (use RETURN inside EVALUATE to exit loops)
   - No STRING type (use TEXT)
   - No CREATE FUNCTION inside a WORKFLOW body

6. Loop exit pattern (ReAct): use RETURN inside EVALUATE, not BREAK:
   WHILE @iteration < @max_iterations DO
     GENERATE DecideAction(@query, @context) INTO @action;
     EVALUATE @action
       WHEN contains('answer') THEN
         GENERATE AnswerQuestion(@query, @context) INTO @answer;
         RETURN @answer WITH status = 'complete';
       ELSE
         CALL web_search(@query) INTO @results;
         @context := @context + "\\n" + @results;
         @iteration := @iteration + 1;
     END;
   END;

Map each Mermaid node/edge to the most appropriate SPL construct:
- Decision diamonds {{...}} -> EVALUATE ... WHEN ... ELSE ... END
- Loops (back-edges) -> WHILE ... DO ... END with RETURN for early exit
- Process boxes [...] -> GENERATE or CALL
- Parallel branches -> CALL PARALLEL ... END

Output ONLY the raw SPL code - no markdown fences, no explanation.
"""

    click.echo(f"Generating SPL from {mermaid_path.name} using {adapter}...", err=True)
    try:
        result = asyncio.run(llm.generate(prompt))
        spl_code = result.content.strip()
    except Exception as exc:
        raise click.ClickException(f"LLM generation failed: {exc}") from exc

    # Strip accidental markdown fences
    spl_code = _re.sub(r'^```[a-zA-Z]*\n?', '', spl_code, flags=_re.MULTILINE)
    spl_code = _re.sub(r'\n?```$', '', spl_code, flags=_re.MULTILINE).strip()

    # Validate
    if validate:
        valid, message = Text2SPL.validate_output(spl_code)
        if not valid:
            if output:
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                Path(output).write_text(spl_code, encoding="utf-8")
                click.echo(f"Written to {output} (with validation errors - review and fix)")
            else:
                click.echo(spl_code)
            click.echo(f"Warning: {message}", err=True)
            raise SystemExit(1)

    # Output
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(spl_code, encoding="utf-8")
        click.echo(f"SPL written to: {output}")
    else:
        click.echo(spl_code)



# ------------------------------------------------------------------ #
# spl3 validate                                                       #
# ------------------------------------------------------------------ #

@main.command("validate")
@click.argument("spl_file")
def cmd_validate(spl_file):
    """Validate SPL syntax of SPL_FILE."""
    from pathlib import Path
    from spl.lexer import Lexer
    from spl3.parser import SPL3Parser

    path = Path(spl_file)
    if not path.exists():
        raise click.ClickException(f"File not found: {path}")
    source = path.read_text(encoding="utf-8")
    try:
        tokens = Lexer(source).tokenize()
        SPL3Parser(tokens).parse()
        click.echo(f"OK: {path}")
    except Exception as exc:
        raise click.ClickException(f"Parse error: {exc}") from exc


# ------------------------------------------------------------------ #
# spl3 explain                                                        #
# ------------------------------------------------------------------ #

@main.command("explain")
@click.argument("spl_file")
def cmd_explain(spl_file):
    """Show execution plan for SPL_FILE (no LLM call)."""
    from pathlib import Path
    from spl.lexer import Lexer
    from spl.analyzer import Analyzer
    from spl.optimizer import Optimizer
    from spl.explain import explain_plans
    from spl3.parser import SPL3Parser

    path = Path(spl_file)
    if not path.exists():
        raise click.ClickException(f"File not found: {path}")
    source = path.read_text(encoding="utf-8")
    try:
        tokens = Lexer(source).tokenize()
        ast = SPL3Parser(tokens).parse()
        analysis = Analyzer().analyze(ast)
        plans = Optimizer().optimize(analysis)
        click.echo(explain_plans(plans))
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


# ------------------------------------------------------------------ #
# spl3 describe                                                       #
# ------------------------------------------------------------------ #

_DESCRIBE_PROMPT = """\
You are an expert in SPL (Structured Prompt Language), a declarative language for orchestrating
LLM workflows. SPL key constructs are:

  WORKFLOW <name>          — declares a named orchestration workflow
  INPUT @<var> <TYPE>      — input parameter declaration with optional default (:= value)
  OUTPUT @<var> <TYPE>     — output variable declaration
  CREATE FUNCTION <name>   — defines a reusable prompt template with {{parameter}} slots
  GENERATE <fn>(...) INTO @<var>   — calls an LLM using a prompt function, stores result
  CALL <tool>(...) INTO @<var>     — invokes a side-effect tool (e.g. write_file, http_get)
  WHILE <cond> DO ... END  — loop until condition is false
  EVALUATE @<var> WHEN <pattern> THEN ... ELSE ... END  — branch on variable content
  LOGGING <msg> LEVEL <INFO|DEBUG|WARN|ERROR>  — emit a structured log message
  RETURN @<var> WITH <k>=<v>, ...  — return value with metadata (status, iteration count, etc.)
  EXCEPTION WHEN <Type> THEN ...   — catch named exception types
  Exception types: MaxIterationsReached, BudgetExceeded, HallucinationDetected,
                   QualityBelowThreshold, ContextLengthExceeded, ModelOverloaded

Read the following SPL script and produce a functional specification in plain English.

Structure your output as Markdown with these sections IN ORDER:

## 0. High-level Description
Write 4-6 sentences of flowing prose (no bullet points) that form a self-contained description
rich enough to serve as a prompt for regenerating this workflow from scratch.
IMPORTANT: anchor your description using the SPL construct names above wherever they apply.
Cover ALL of the following that are present in the script:
- Pattern or technique (e.g. "self-refine", "map-reduce", "chain-of-thought")
- Every CREATE FUNCTION — name, role, and any notable prompt convention (sentinel tokens,
  scoring instructions, output format constraints)
- Control flow expressed in SPL terms: WHILE condition, EVALUATE branch, RETURN metadata
- Multi-model or multi-role design (which INPUT param drives each model choice)
- CALL side-effects (file writes, external tools) and LOGGING strategy
- Resource-limit strategy: EXCEPTION types handled and what each does

## 1. Purpose
One sentence summarising what the script accomplishes for the end user.

## 2. Inputs
A Markdown table — columns: Parameter | Default | Description.
List every INPUT variable declared in the workflow.

## 3. Process
Numbered steps in plain language following actual execution order.

## 4. Error Handling
Bullet list of each EXCEPTION case and the workflow's response.

## 5. Output
What is returned, including status codes and any metadata fields.

SPL Script:
```spl
{source}
```

Write the specification now.
"""


@main.command("describe")
@click.argument("spl_path")
@click.option("--adapter", default="ollama", show_default=True,
              help="LLM adapter to use for generation.")
@click.option("--model", default=None, metavar="MODEL",
              help="Model override for the adapter.")
@click.option("--spec-dir", default=None, metavar="DIR",
              help="Directory to write the spec file (default: same dir as input).")
def cmd_describe(spl_path, adapter, model, spec_dir):
    """Generate a plain-English functional specification for a .spl file or folder.

    \b
    SPL_PATH can be:
      - a single .spl file  → spec named <stem>-spec.md
      - a folder            → all *.spl files in the folder are gathered and
                              described together as one recipe unit;
                              spec named <folder>-spec.md

    \b
    Examples:
      spl3 describe cookbook/05_self_refine/self_refine.spl
      spl3 describe cookbook/63_parallel_code_review/
      spl3 describe my_workflow.spl --adapter claude_cli --spec-dir docs/specs
    """
    path = Path(spl_path)
    if not path.exists():
        raise click.ClickException(f"Path not found: {path}")

    if path.is_dir():
        spl_files = sorted(path.glob("*.spl"))
        if not spl_files:
            raise click.ClickException(f"No .spl files found in {path}")
        # Concatenate all sources with file headers so the LLM sees the full recipe
        parts = []
        for f in spl_files:
            parts.append(f"-- File: {f.name}\n" + f.read_text(encoding="utf-8"))
        source = "\n\n".join(parts)
        stem = path.resolve().name          # folder name → spec stem
        spec_parent = path
        click.echo(f"Describing {len(spl_files)} .spl file(s) in {path.name}/: "
                   f"{', '.join(f.name for f in spl_files)}")
    else:
        source = path.read_text(encoding="utf-8")
        stem = path.stem
        spec_parent = path.parent
        click.echo(f"Generating spec for {path.name} ...")

    prompt = _DESCRIBE_PROMPT.format(source=source)

    try:
        from spl3.adapters import get_adapter
    except ImportError:
        raise click.ClickException("spl-llm 2.0 not installed: pip install spl-llm>=2.0.0")

    llm = get_adapter(adapter, **{"model": model} if model else {})
    result = asyncio.run(llm.generate(prompt, **({"model": model} if model else {})))
    spec_text = result if isinstance(result, str) else getattr(result, "content", str(result))

    spec_filename = f"{stem}-spec.md"
    if spec_dir:
        out_dir = Path(spec_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        spec_path = out_dir / spec_filename
    else:
        spec_path = spec_parent / spec_filename

    spec_path.write_text(spec_text, encoding="utf-8")
    click.echo(f"Spec written to: {spec_path}")


# ------------------------------------------------------------------ #
# spl3 compare                                                        #
# ------------------------------------------------------------------ #

@main.command("compare")
@click.argument("file1")
@click.argument("file2")
@click.option("--adapter", default="ollama", show_default=True,
              help="LLM adapter to use for semantic analysis.")
@click.option("--model", default=None, metavar="MODEL",
              help="Model override for the adapter.")
@click.option("--output", "-o", default=None, metavar="FILE",
              help="Write comparison report to FILE.")
@click.option("--format", default="markdown", show_default=True,
              type=click.Choice(["markdown", "json", "text"]),
              help="Output format for comparison report.")
@click.option("--focus", default="all", show_default=True,
              type=click.Choice(["all", "structure", "logic", "quality", "syntax"]),
              help="Focus comparison on specific aspects.")
@click.option("--diff", is_flag=True, default=False,
              help="Include mechanical line-by-line diff (like git diff).")
@click.option("--diff-only", is_flag=True, default=False,
              help="Show only mechanical diff, skip semantic analysis.")
@click.option("--diff-style", default="unified", show_default=True,
              type=click.Choice(["unified", "context", "side-by-side"]),
              help="Style for mechanical diff output.")
@click.option("--no-color", is_flag=True, default=False,
              help="Disable colored diff output.")
def cmd_compare(file1, file2, adapter, model, output, format, focus, diff, diff_only, diff_style, no_color):
    """Perform semantic and/or mechanical comparison between two files.

    Analyzes and compares the content, structure, logic, and quality
    of two files using LLM-powered semantic analysis and/or traditional
    line-by-line diff. Works with any text-based files including .mmd, .md, .spl, .txt, etc.

    \b
    Examples:
      spl3 compare workflow1.mmd workflow2.mmd
      spl3 compare claude_output.md ollama_output.md --focus quality
      spl3 compare old_spec.md new_spec.md -o comparison_report.md --diff
      spl3 compare chart1.mmd chart2.mmd --diff-only --diff-style side-by-side
      spl3 compare file1.spl file2.spl --adapter claude_cli --diff --format json
    """
    from pathlib import Path
    import json as _json
    import difflib
    import sys

    # Validate input files
    path1 = Path(file1)
    path2 = Path(file2)

    if not path1.exists():
        raise click.ClickException(f"File not found: {file1}")
    if not path2.exists():
        raise click.ClickException(f"File not found: {file2}")

    # Read file contents
    content1 = path1.read_text(encoding="utf-8")
    content2 = path2.read_text(encoding="utf-8")

    # Generate mechanical diff if requested
    mechanical_diff = ""
    if diff or diff_only:
        lines1 = content1.splitlines(keepends=True)
        lines2 = content2.splitlines(keepends=True)

        if diff_style == "unified":
            diff_lines = list(difflib.unified_diff(
                lines1, lines2,
                fromfile=f"a/{path1.name}",
                tofile=f"b/{path2.name}",
                lineterm=""
            ))

            if not no_color and sys.stdout.isatty():
                # Add ANSI color codes for terminal output
                colored_diff = []
                for line in diff_lines:
                    if line.startswith('+++') or line.startswith('---'):
                        colored_diff.append(f"\033[1m{line}\033[0m")  # Bold
                    elif line.startswith('@@'):
                        colored_diff.append(f"\033[36m{line}\033[0m")  # Cyan
                    elif line.startswith('+'):
                        colored_diff.append(f"\033[32m{line}\033[0m")  # Green
                    elif line.startswith('-'):
                        colored_diff.append(f"\033[31m{line}\033[0m")  # Red
                    else:
                        colored_diff.append(line)
                mechanical_diff = "\n".join(colored_diff)
            else:
                mechanical_diff = "\n".join(diff_lines)

        elif diff_style == "context":
            diff_lines = list(difflib.context_diff(
                lines1, lines2,
                fromfile=f"a/{path1.name}",
                tofile=f"b/{path2.name}",
                lineterm=""
            ))
            mechanical_diff = "\n".join(diff_lines)

        elif diff_style == "side-by-side":
            # Create side-by-side diff
            differ = difflib.HtmlDiff()
            if format == "markdown":
                # For markdown, create a simple side-by-side table
                side_by_side_lines = []
                side_by_side_lines.append(f"| {path1.name} | {path2.name} |")
                side_by_side_lines.append("|---|---|")

                # Get line-by-line differences
                for i, (line1, line2) in enumerate(zip(lines1, lines2)):
                    line1_clean = line1.rstrip('\n\r').replace('|', '\\|')
                    line2_clean = line2.rstrip('\n\r').replace('|', '\\|')
                    if line1 != line2:
                        side_by_side_lines.append(f"| **{line1_clean}** | **{line2_clean}** |")
                    else:
                        side_by_side_lines.append(f"| {line1_clean} | {line2_clean} |")

                # Handle different file lengths
                max_len = max(len(lines1), len(lines2))
                for i in range(min(len(lines1), len(lines2)), max_len):
                    if i < len(lines1):
                        line1_clean = lines1[i].rstrip('\n\r').replace('|', '\\|')
                        side_by_side_lines.append(f"| **{line1_clean}** | *[missing]* |")
                    else:
                        line2_clean = lines2[i].rstrip('\n\r').replace('|', '\\|')
                        side_by_side_lines.append(f"| *[missing]* | **{line2_clean}** |")

                mechanical_diff = "\n".join(side_by_side_lines)
            else:
                # For other formats, use simple text side-by-side
                mechanical_diff = differ.make_file(
                    lines1, lines2,
                    fromdesc=path1.name,
                    todesc=path2.name
                )

        # If no differences found
        if not mechanical_diff.strip() or mechanical_diff == "\n".join([f"--- a/{path1.name}", f"+++ b/{path2.name}"]):
            mechanical_diff = "No mechanical differences found - files are identical."

    # Handle diff-only mode
    if diff_only:
        if output:
            output_path = Path(output)
            output_path.write_text(mechanical_diff, encoding="utf-8")
            click.echo(f"Mechanical diff written to: {output_path}")
        else:
            click.echo(mechanical_diff)
        return

    # Determine file types for context
    ext1 = path1.suffix.lower()
    ext2 = path2.suffix.lower()

    # Build comparison prompt based on focus
    focus_prompts = {
        "all": "Provide a comprehensive comparison covering structure, logic, quality, and syntax.",
        "structure": "Focus on architectural and organizational differences.",
        "logic": "Focus on logical flow, decision points, and process sequences.",
        "quality": "Focus on completeness, sophistication, and best practices.",
        "syntax": "Focus on syntax correctness, formatting, and technical accuracy."
    }

    prompt = f"""Compare these two files semantically and provide a detailed analysis.

**File 1**: {path1.name} ({ext1})
**File 2**: {path2.name} ({ext2})
**Focus**: {focus_prompts[focus]}

**File 1 Content:**
```
{content1}
```

**File 2 Content:**
```
{content2}
```

Please provide a structured comparison analysis with the following sections:

## Summary
Brief overview of the main differences and which file is stronger overall.

## Content Analysis
### File 1 Strengths
- Key advantages and well-implemented aspects

### File 2 Strengths
- Key advantages and well-implemented aspects

### Common Elements
- Shared concepts, structures, or approaches

## Detailed Comparison
### Structure & Organization
Compare the overall structure, flow, and organization.

### Logic & Completeness
Analyze logical flow, decision points, error handling, and completeness.

### Quality & Sophistication
Evaluate complexity, depth, best practices, and professional quality.

### Syntax & Technical Accuracy
Review syntax correctness, formatting, and technical implementation.

## Recommendations
1. **Best Choice**: Which file is better and why
2. **Improvements**: Specific suggestions to enhance the weaker file
3. **Hybrid Approach**: How to combine strengths from both files

## Scoring
Rate each file (1-10) on:
- Structure: [File1]/10, [File2]/10
- Logic: [File1]/10, [File2]/10
- Quality: [File1]/10, [File2]/10
- Overall: [File1]/10, [File2]/10

Provide actionable insights for choosing between or improving these files."""

    try:
        from spl3.adapters import get_adapter
    except ImportError:
        raise click.ClickException("spl-llm 2.0 not installed: pip install spl-llm>=2.0.0")

    llm = get_adapter(adapter, **{"model": model} if model else {})

    if diff:
        click.echo(f"Comparing {path1.name} vs {path2.name} using {adapter} (semantic + mechanical diff)...")
    else:
        click.echo(f"Comparing {path1.name} vs {path2.name} using {adapter}...")

    result = asyncio.run(llm.generate(prompt, **({"model": model} if model else {})))
    comparison_text = result if isinstance(result, str) else getattr(result, "content", str(result))

    # Format output based on requested format
    if format == "json":
        # Extract key metrics for JSON (simplified structure)
        json_output = {
            "files": {
                "file1": {"name": path1.name, "type": ext1},
                "file2": {"name": path2.name, "type": ext2}
            },
            "analysis": {
                "summary": comparison_text.split("## Content Analysis")[0].replace("## Summary", "").strip(),
                "full_report": comparison_text
            },
            "metadata": {
                "adapter": adapter,
                "model": model or "default",
                "focus": focus,
                "timestamp": datetime.now().isoformat(),
                "includes_diff": diff,
                "diff_style": diff_style if diff else None
            }
        }

        if diff and mechanical_diff:
            json_output["mechanical_diff"] = {
                "style": diff_style,
                "content": mechanical_diff
            }

        output_content = _json.dumps(json_output, indent=2)

    elif format == "text":
        # Plain text without markdown formatting
        output_content = comparison_text.replace("#", "").replace("**", "").replace("*", "")

        if diff and mechanical_diff:
            output_content = f"""MECHANICAL DIFF ({diff_style.upper()})
{'=' * 60}

{mechanical_diff}

{'=' * 60}

SEMANTIC ANALYSIS
{'=' * 60}

{output_content}"""

    else:  # markdown (default)
        # Add metadata header
        output_content = f"""# File Comparison Report

**Files Compared:**
- File 1: `{path1.name}` ({ext1})
- File 2: `{path2.name}` ({ext2})
- **Adapter:** {adapter}
- **Model:** {model or 'default'}
- **Focus:** {focus}
- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{f"- **Includes Diff:** {diff_style} style" if diff else ""}

---

{comparison_text}

{f'''
---

## Mechanical Diff ({diff_style.title()} Style)

```diff
{mechanical_diff}
```
''' if diff and mechanical_diff else ""}

---

*Generated by SPL semantic comparison tool*
"""

    # Output results
    if output:
        output_path = Path(output)
        output_path.write_text(output_content, encoding="utf-8")
        click.echo(f"Comparison report written to: {output_path}")
    else:
        click.echo(output_content)


# ------------------------------------------------------------------ #
# spl3 show                                                           #
# ------------------------------------------------------------------ #

@main.command("show")
@click.option("--adapter", is_flag=False, flag_value="__list_all__", default=None,
              help="List all adapters (no value) or specify adapter name")
@click.option("--model", is_flag=True, default=False,
              help="List available models (requires --adapter <name>)")
@click.option("--tool", is_flag=False, flag_value="__list_all__", default=None,
              metavar="NAME",
              help="List all stdlib tools (no value) or show detail for a specific tool")
def cmd_show(adapter, model, tool):
    """List available adapters, models, and stdlib tools.

    \b
    Examples:
      spl3 show --adapter                     # List all available adapters
      spl3 show --adapter ollama --model      # List models for ollama adapter
      spl3 show --adapter claude_cli --model  # List models for claude_cli adapter
      spl3 show --tool                        # List all stdlib tools
      spl3 show --tool web_search             # Show detail for a specific tool
    """
    import sys
    from spl3.adapters import list_adapters, get_adapter

    # Case 1: --adapter used as flag (list all adapters)
    if adapter == "__list_all__":
        if model:
            raise click.ClickException("Cannot use --model when listing all adapters")

        adapter_list = list_adapters()
        if not adapter_list:
            click.echo("No adapters available")
            return

        click.echo("Available adapters:")
        for adapter_name in adapter_list:
            click.echo(f"  {adapter_name}")

        click.echo(f"\nTotal: {len(adapter_list)} adapter(s)")
        click.echo("Use 'spl3 show --adapter <name> --model' to list models for a specific adapter")
        return

    # Case 2: --adapter has value and --model is used
    if adapter and adapter != "__list_all__" and model:
        adapter_list = list_adapters()
        if adapter not in adapter_list:
            available = ", ".join(sorted(adapter_list)) if adapter_list else "(none)"
            raise click.ClickException(f"Unknown adapter '{adapter}'. Available: {available}")

        try:
            adapter_instance = get_adapter(adapter)
            model_list = sorted(adapter_instance.list_models())

            if not model_list:
                click.echo(f"No models available for adapter '{adapter}'")
                return

            click.echo(f"Available models for '{adapter}':")
            for model_name in model_list:
                click.echo(f"  {model_name}")

            click.echo(f"\nTotal: {len(model_list)} model(s)")

        except Exception as e:
            raise click.ClickException(f"Failed to list models for adapter '{adapter}': {e}")
        return

    # Case 3: Invalid combinations
    if model and not adapter:
        raise click.ClickException("--model flag requires --adapter <name> to specify which adapter to query")

    if adapter and not model:
        raise click.ClickException(f"Use --model to list models for adapter '{adapter}', or use --adapter alone to list all adapters")

    # Case: --tool
    if tool is not None:
        from spl.tools import get_global_tools

        # Category order and membership — matches stdlib.py section comments
        _CATEGORIES = [
            ("Type conversion",   ["to_int", "to_float", "to_text", "to_bool"]),
            ("String",            ["upper", "lower", "trim", "ltrim", "rtrim", "length",
                                   "len_val", "substr", "replace", "concat", "instr",
                                   "lpad", "rpad", "split_part", "reverse"]),
            ("Pattern matching",  ["like", "startswith", "endswith", "contains", "regexp_match"]),
            ("Numeric",           ["abs_val", "round_val", "ceil_val", "floor_val",
                                   "mod_val", "power_val", "sqrt_val", "sign_val", "clamp"]),
            ("Conditional",       ["coalesce", "nullif", "iif"]),
            ("Null / empty",      ["isnull", "nvl", "isblank"]),
            ("Text aggregates",   ["word_count", "char_count", "line_count"]),
            ("JSON",              ["json_get", "json_set", "json_keys", "json_pretty",
                                   "json_length"]),
            ("Date / time",       ["now_iso", "date_format_val", "date_diff_days"]),
            ("Hashing",           ["md5_hash", "sha256_hash"]),
            ("List / array",      ["list_get", "list_length", "list_join", "list_contains",
                                   "trim_turns"]),
            ("File I/O",          ["write_file", "read_file", "file_exists", "make_dir",
                                   "path_join"]),
            ("Agentic / Network", ["web_search", "http_get", "run_python"]),
        ]

        all_tools = get_global_tools()

        if tool == "__list_all__":
            # Assign each tool to its category; uncategorised tools go last
            categorised = {name for names in _CATEGORIES for name in names[1]}
            uncategorised = sorted(k for k in all_tools if k not in categorised)

            total = 0
            for cat_name, cat_tools in _CATEGORIES:
                present = [t for t in cat_tools if t in all_tools]
                if not present:
                    continue
                click.echo(f"\n{cat_name}:")
                for name in present:
                    fn = all_tools[name]
                    doc = (fn.__doc__ or "").strip().splitlines()[0]
                    click.echo(f"  {name:<22}  {doc}")
                    total += 1

            if uncategorised:
                click.echo("\nOther:")
                for name in uncategorised:
                    fn = all_tools[name]
                    doc = (fn.__doc__ or "").strip().splitlines()[0]
                    click.echo(f"  {name:<22}  {doc}")
                    total += 1

            click.echo(f"\nTotal: {total} tool(s)  — use 'spl3 show --tool <name>' for detail")
            return

        # --tool <name>: show full docstring
        if tool not in all_tools:
            available = ", ".join(sorted(all_tools))
            raise click.ClickException(
                f"Unknown tool '{tool}'.\nAvailable: {available}"
            )
        fn = all_tools[tool]
        click.echo(f"Tool: {tool}")
        click.echo(f"{'─' * (len(tool) + 6)}")
        click.echo(fn.__doc__ or "(no docstring)")
        return

    # Case 4: No options provided
    raise click.ClickException(
        "Use --adapter to list adapters, --adapter <name> --model to list models, "
        "or --tool to list stdlib tools"
    )


# ------------------------------------------------------------------ #
# spl3 splc                                                           #
# ------------------------------------------------------------------ #

from spl3.splc.cli import splc as _splc_command
main.add_command(_splc_command, name="splc")


if __name__ == "__main__":
    main()
