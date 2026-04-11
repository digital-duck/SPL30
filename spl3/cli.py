"""SPL 3.0 CLI: spl

Commands:
  spl register <path>       Register workflows from .spl file(s) into Hub registry
  spl run <file.spl>        Run an orchestrator workflow
  spl registry list         List registered workflows (local + Hub)
  spl peers list            List peer Hubs and their workflow counts
  spl peers add <url>       Add a peer Hub (peering handshake)
"""

import asyncio
import logging

import click

_log = logging.getLogger("spl.cli")


@click.group()
@click.option("--hub", default=None, envvar="SPL3_HUB", help="Momagrid Hub URL")
@click.option("--verbose", "-v", is_flag=True)
@click.pass_context
def main(ctx, hub, verbose):
    """SPL 3.0 — Momagrid as Compute OS."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    ctx.ensure_object(dict)
    ctx.obj["hub"] = hub


# ------------------------------------------------------------------ #
# spl run                                                             #
# ------------------------------------------------------------------ #

@main.command()
@click.argument("spl_file")
@click.option("--adapter", default="ollama", show_default=True)
@click.option("--model", default="gemma3", show_default=True)
@click.option("--param", "-p", multiple=True, help="key=value workflow INPUT params")
@click.pass_context
def run(ctx, spl_file, adapter, model, param):
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

    asyncio.run(_run_workflow(path, adapter, model, params, hub_url))


async def _run_workflow(path, adapter_name, model, params, hub_url):
    from spl3.registry import LocalRegistry, FederatedRegistry
    from spl3.composer import WorkflowComposer

    try:
        from spl3.executor import Executor
        from spl3.adapters import get_adapter
    except ImportError:
        raise click.ClickException("spl-llm 2.0 not installed: pip install spl-llm>=2.0.0")

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

    # Build executor and attach composer for CALL workflow_name() dispatch
    adapter = get_adapter(adapter_name, model=model)
    executor = Executor(adapter=adapter)
    executor.composer = WorkflowComposer(registry, executor)

    # Find the top-level workflow in the file (last defined, or named 'main')
    from spl3._loader import load_workflows_from_file
    defns = load_workflows_from_file(path)
    if not defns:
        raise click.ClickException(f"No WORKFLOW definitions found in {path}")

    # Prefer a workflow named after the file stem, or take the last one
    stem = path.stem.replace("-", "_")
    target = next((d for d in defns if d.name == stem), defns[-1])
    click.echo(f"Running workflow: {target.name}({list(params)})")

    result = await executor.execute_workflow(target.ast_node, params=params)

    click.echo(f"\nStatus:  {result.status}")
    click.echo(f"Output:  {result.committed_value or '(no COMMIT)'}")
    click.echo(f"LLM calls: {result.total_llm_calls}  "
               f"Latency: {result.total_latency_ms:.0f}ms")


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
@click.option("--model", default="gemma3", show_default=True)
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

    adapter = get_adapter(adapter_name, model=model)
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
              help="Optional cookbook_catalog.json for richer descriptions.")
def code_rag_seed(cookbook_dir, storage_dir, catalog):
    """Seed the Code-RAG index from a cookbook directory.

    Indexes all .spl files as (description, SPL source) pairs.
    If --catalog is provided, uses its descriptions instead of file headers.

    \b
    Example:
      spl code-rag seed cookbook/code_pipeline/ --storage-dir .spl/code_rag
    """
    from spl3.code_rag import CodeRAGStore
    store = CodeRAGStore(storage_dir=storage_dir)

    if catalog:
        count = store.seed_from_catalog(catalog)
    else:
        count = store.seed_from_dir(cookbook_dir)

    click.echo(f"Seeded {count} workflow(s) into Code-RAG store at {storage_dir}")
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


@cmd_code_rag.command("stats")
@click.option("--storage-dir", default=".spl/code_rag", show_default=True)
def code_rag_stats(storage_dir):
    """Show Code-RAG index statistics."""
    from spl3.code_rag import CodeRAGStore
    store = CodeRAGStore(storage_dir=storage_dir)
    click.echo(f"Code-RAG store: {storage_dir}")
    click.echo(f"  Indexed pairs: {store.count()}")
