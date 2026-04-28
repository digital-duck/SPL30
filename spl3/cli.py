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
# spl3 text2mermaid                                                   #
# ------------------------------------------------------------------ #

@main.command("text2mermaid")
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
@click.option("--preview", is_flag=True, default=False,
              help="Open diagram in browser preview.")
def cmd_text2mermaid(description, description_opt, adapter, model, style, output, validate, preview):
    """Generate Mermaid flowchart from natural language workflow description.

    This creates a visual representation of the workflow that can be reviewed
    and edited before converting to SPL code.

    \b
    Examples:
      spl3 text2mermaid "build a review agent that refines text until quality > 0.8"
      spl3 text2mermaid --description "research workflow" -o research.mmd
      spl3 text2mermaid "parallel code review" --style flowchart --preview
    """
    import re as _re
    from pathlib import Path

    try:
        from spl.adapters import get_adapter
    except ImportError:
        raise click.ClickException("spl adapters not available")

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

    prompt = f"""Convert this workflow description into a Mermaid {style} diagram.

Workflow Description:
{desc_text}

Generate a clear, well-structured Mermaid diagram that shows:
- Process steps as rectangular nodes
- Decision points as diamond nodes
- Loops and iterations with feedback edges
- Parallel processes as separate branches
- Clear flow direction with arrows

Use descriptive node labels and follow Mermaid syntax exactly.
Output only the Mermaid diagram code, no explanations.

Example format:
```mermaid
{style} TD
    A[Start] --> B[Process Input]
    B --> C{{Decision}}
    C -->|Yes| D[Action]
    C -->|No| E[Alternative]
    D --> F[End]
    E --> F
```
"""

    result = asyncio.run(llm.generate(prompt, **({"model": model} if model else {})))
    mermaid_text = result if isinstance(result, str) else getattr(result, "content", str(result))

    # Extract mermaid code from markdown if present
    if "```mermaid" in mermaid_text:
        mermaid_match = _re.search(r"```mermaid\s*\n(.*?)\n```", mermaid_text, _re.DOTALL)
        if mermaid_match:
            mermaid_text = mermaid_match.group(1).strip()

    # Basic validation
    if validate:
        if not any(keyword in mermaid_text for keyword in ["flowchart", "graph", "sequenceDiagram"]):
            click.echo("Warning: Generated text may not be valid Mermaid syntax", err=True)

    # Output
    if output:
        Path(output).write_text(mermaid_text, encoding="utf-8")
        click.echo(f"Mermaid diagram written to: {output}")
        if preview:
            import webbrowser
            # Create temporary HTML file for preview
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
</head>
<body>
    <div class="mermaid">
{mermaid_text}
    </div>
    <script>mermaid.initialize({{startOnLoad:true}});</script>
</body>
</html>"""
            preview_path = Path(output).with_suffix('.html')
            preview_path.write_text(html_content, encoding="utf-8")
            webbrowser.open(f"file://{preview_path.absolute()}")
            click.echo(f"Preview opened in browser: {preview_path}")
    else:
        click.echo(mermaid_text)


# ------------------------------------------------------------------ #
# spl3 mermaid2spl                                                    #
# ------------------------------------------------------------------ #

@main.command("mermaid2spl")
@click.argument("mermaid_file")
@click.option("--output", "-o", default=None, metavar="FILE",
              help="Write generated SPL to FILE.")
@click.option("--validate/--no-validate", default=True, show_default=True,
              help="Validate generated SPL syntax.")
@click.option("--template", default="workflow", show_default=True,
              type=click.Choice(["workflow", "function"]),
              help="Base SPL template type.")
@click.option("--pattern-hints", default=None, metavar="HINTS",
              help="Comma-separated hints for SPL patterns (e.g., 'linear,parallel').")
def cmd_mermaid2spl(mermaid_file, output, validate, template, pattern_hints):
    """Generate SPL workflow from Mermaid flowchart diagram.

    Converts a Mermaid flowchart into executable SPL code, mapping visual
    elements to SPL constructs like GENERATE, EVALUATE, WHILE, and CALL PARALLEL.

    \b
    Examples:
      spl3 mermaid2spl workflow.mmd -o workflow.spl
      spl3 mermaid2spl diagram.mmd --template function --validate
      spl3 mermaid2spl review.mmd --pattern-hints "iterative,quality-gate"
    """
    import re as _re
    from pathlib import Path

    # Read Mermaid file
    if not Path(mermaid_file).exists():
        raise click.ClickException(f"Mermaid file not found: {mermaid_file}")

    mermaid_content = Path(mermaid_file).read_text(encoding="utf-8")

    # Basic Mermaid parsing - extract nodes and connections
    nodes = {}
    edges = []

    # Parse flowchart nodes: A[Label] or A{Decision} or A(Process)
    node_pattern = r'(\w+)(?:\[(.*?)\]|\{(.*?)\}|\((.*?)\))'
    for match in _re.finditer(node_pattern, mermaid_content):
        node_id = match.group(1)
        label = match.group(2) or match.group(3) or match.group(4) or node_id

        # Determine node type from syntax
        if match.group(3):  # {label} = decision
            node_type = "decision"
        elif any(keyword in label.lower() for keyword in ["start", "begin"]):
            node_type = "start"
        elif any(keyword in label.lower() for keyword in ["end", "finish", "return"]):
            node_type = "end"
        else:
            node_type = "process"

        nodes[node_id] = {"label": label, "type": node_type}

    # Parse edges: A --> B or A -->|label| B
    edge_pattern = r'(\w+)\s*(?:-->|->)\s*(?:\|([^|]*)\|\s*)?(\w+)'
    for match in _re.finditer(edge_pattern, mermaid_content):
        from_node = match.group(1)
        edge_label = match.group(2)
        to_node = match.group(3)
        edges.append({"from": from_node, "to": to_node, "label": edge_label})

    # Generate SPL based on structure
    workflow_name = Path(mermaid_file).stem.replace("-", "_")

    # Detect patterns
    has_loops = any(
        any(e2["from"] == edge["to"] and e2["to"] == edge["from"] for e2 in edges)
        for edge in edges
    )

    has_decisions = any(node["type"] == "decision" for node in nodes.values())
    has_parallel = len([n for n in nodes.values() if n["type"] == "process"]) > 3

    # Build SPL
    spl_lines = []

    if template == "workflow":
        spl_lines.extend([
            f"WORKFLOW {workflow_name}",
            "  INPUT @input TEXT",
            "  OUTPUT @result TEXT",
            "DO"
        ])

        # Add variables
        for node_id, node in nodes.items():
            if node["type"] == "process":
                var_name = _re.sub(r'\W+', '_', node["label"].lower())
                spl_lines.append(f"  @{var_name} := '';")

        # Add main logic
        process_nodes = [n for n in nodes.values() if n["type"] == "process"]
        decision_nodes = [n for n in nodes.values() if n["type"] == "decision"]

        if has_loops and decision_nodes:
            # Iterative pattern
            spl_lines.extend([
                "  @iteration := 0;",
                "  @max_iterations := 3;",
                "",
                "  WHILE @iteration < @max_iterations DO",
                "    DO"
            ])

            for node in process_nodes[:2]:  # Main processes
                var_name = _re.sub(r'\W+', '_', node["label"].lower())
                func_name = _re.sub(r'\W+', '_', node["label"].lower()).strip('_')
                # Avoid reserved keywords
                if func_name in ['input', 'output', 'result', 'return', 'end', 'do', 'while', 'evaluate', 'when', 'then', 'else']:
                    func_name = f"process_{func_name}"
                spl_lines.append(f"      GENERATE {func_name}(@input) INTO @{var_name};")

            # Add decision logic
            if decision_nodes:
                decision = decision_nodes[0]
                spl_lines.extend([
                    f"      EVALUATE @{var_name}",
                    f"        WHEN contains('complete') THEN",
                    f"          RETURN @{var_name} WITH status = 'complete';",
                    f"        ELSE",
                    f"          @iteration := @iteration + 1;",
                    "      END;"
                ])

            spl_lines.extend([
                "    END;",
                "  END;",
            ])

        elif has_decisions:
            # Conditional pattern
            for node in process_nodes:
                var_name = _re.sub(r'\W+', '_', node["label"].lower())
                func_name = _re.sub(r'\W+', '_', node["label"].lower()).strip('_')
                # Avoid reserved keywords
                if func_name in ['input', 'output', 'result', 'return', 'end', 'do', 'while', 'evaluate', 'when', 'then', 'else']:
                    func_name = f"process_{func_name}"
                spl_lines.append(f"  GENERATE {func_name}(@input) INTO @{var_name};")

            if decision_nodes:
                decision = decision_nodes[0]
                spl_lines.extend([
                    f"  EVALUATE @{var_name}",
                    f"    WHEN contains('condition') THEN",
                    f"      @result := 'path_a';",
                    f"    ELSE",
                    f"      @result := 'path_b';",
                    "  END;"
                ])

        elif has_parallel:
            # Parallel pattern
            spl_lines.append("  CALL PARALLEL")
            for i, node in enumerate(process_nodes[:3]):  # Limit to 3 parallel
                var_name = _re.sub(r'\W+', '_', node["label"].lower())
                func_name = _re.sub(r'\W+', '_', node["label"].lower()).strip('_')
                # Avoid reserved keywords
                if func_name in ['input', 'output', 'result', 'return', 'end', 'do', 'while', 'evaluate', 'when', 'then', 'else']:
                    func_name = f"process_{func_name}"
                comma = "," if i < min(2, len(process_nodes) - 1) else ""
                spl_lines.append(f"    {func_name}(@input) INTO @{var_name}{comma}")
            spl_lines.append("  END")

        else:
            # Linear pattern
            for node in process_nodes:
                var_name = _re.sub(r'\W+', '_', node["label"].lower())
                func_name = _re.sub(r'\W+', '_', node["label"].lower()).strip('_')
                # Avoid reserved keywords
                if func_name in ['input', 'output', 'result', 'return', 'end', 'do', 'while', 'evaluate', 'when', 'then', 'else']:
                    func_name = f"process_{func_name}"
                spl_lines.append(f"  GENERATE {func_name}(@input) INTO @{var_name};")

        spl_lines.extend([
            "  RETURN @result;",
            "END;"
        ])

    else:  # function template
        func_name = workflow_name
        spl_lines.extend([
            f"CREATE FUNCTION {func_name}(input TEXT) RETURNS TEXT AS $$",
            f"Process the input through {workflow_name} workflow.",
            "$$;"
        ])

    spl_code = "\n".join(spl_lines)

    # Basic validation
    if validate:
        try:
            # Simple syntax check
            if not any(keyword in spl_code for keyword in ["WORKFLOW", "CREATE FUNCTION"]):
                click.echo("Warning: Generated code may not be valid SPL", err=True)
        except Exception as e:
            click.echo(f"Validation warning: {e}", err=True)

    # Output
    if output:
        Path(output).write_text(spl_code, encoding="utf-8")
        click.echo(f"SPL code written to: {output}")

        # Also generate .mmd file for reference
        mmd_output = Path(output).with_suffix('.mmd')
        mmd_output.write_text(mermaid_content, encoding="utf-8")
        click.echo(f"Mermaid reference saved to: {mmd_output}")
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
# spl3 splc                                                           #
# ------------------------------------------------------------------ #

from spl3.splc.cli import splc as _splc_command
main.add_command(_splc_command, name="splc")


if __name__ == "__main__":
    main()
