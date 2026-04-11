#!/usr/bin/env python3
"""run_all.py — SPL 3.0 Cookbook batch runner.

Mirrors SPL 2.0's run_all.py but for SPL 3.0 multimodal recipes.
Recipes are Python runners (run.py), not `spl run` commands.
The catalog is defined in cookbook/cookbook_catalog.json.

Usage
-----
  cd ~/projects/digital-duck/SPL30

  # List recipes
  python cookbook/run_all.py list
  python cookbook/run_all.py list --tier 1
  python cookbook/run_all.py list --category multimodal
  python cookbook/run_all.py catalog

  # Run active (tier-1) recipes
  python cookbook/run_all.py

  # Run by tier (1=Ollama-only, 2=OpenAI, 3=OpenRouter, 4=all keys)
  python cookbook/run_all.py --tier 1
  python cookbook/run_all.py --tier 2
  python cookbook/run_all.py --tier 1,2      # run tier 1 AND tier 2

  # Run specific recipes by ID
  python cookbook/run_all.py --ids 50,54
  python cookbook/run_all.py --ids 50-55

  # Run all (including inactive) for a full test pass
  python cookbook/run_all.py --all

  # Save output to log
  python cookbook/run_all.py --tier 1 2>&1 | tee cookbook/logs/run_$(date +%Y%m%d_%H%M%S).md

Prerequisites check
-------------------
  python cookbook/run_all.py check           # verify env vars + Ollama models
  python cookbook/run_all.py check --tier 2  # check tier-2 prerequisites only
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import click

COOKBOOK_DIR = Path(__file__).resolve().parent
REPO_ROOT    = COOKBOOK_DIR.parent

MARKERS = {
    "active":    "✅",
    "new":       "🆕",
    "wip":       "🔧",
    "disabled":  "⏸ ",
    "rejected":  "❌",
    "approved":  "✅",
}

TIER_LABELS = {
    1: "Ollama only",
    2: "OpenAI key",
    3: "OpenRouter key",
    4: "OpenAI + OpenRouter + Ollama",
}


# ── Catalog ───────────────────────────────────────────────────────────────────

def load_catalog() -> list[dict]:
    path = COOKBOOK_DIR / "cookbook_catalog.json"
    with open(path) as f:
        data = json.load(f)
    return data["recipes"]


def apply_filters(
    recipes: list[dict],
    category: str,
    status: str,
    tiers: set[int],
    ids: set[str],
    include_inactive: bool,
) -> list[dict]:
    out = []
    for r in recipes:
        if ids and r["id"] not in ids:
            continue
        if not include_inactive and not r.get("is_active"):
            continue
        if category and r.get("category") != category:
            continue
        if status and r.get("approval_status") != status:
            continue
        if tiers and r.get("tier") not in tiers:
            continue
        out.append(r)
    return out


def parse_id_filter(ids: str) -> set[str]:
    result: set[str] = set()
    for part in ids.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            for n in range(int(lo), int(hi) + 1):
                result.add(str(n))
        else:
            result.add(part.lstrip("0") or "0")
    return result


def parse_tier_filter(tiers: str) -> set[int]:
    result: set[int] = set()
    for part in tiers.split(","):
        part = part.strip()
        if part:
            result.add(int(part))
    return result


# ── Prerequisite check ────────────────────────────────────────────────────────

def check_prerequisites(recipes: list[dict]) -> tuple[bool, list[str]]:
    """Check env vars and Ollama models. Returns (all_ok, list_of_issues)."""
    issues: list[str] = []
    needed_envs:   set[str] = set()
    needed_models: set[str] = set()

    for r in recipes:
        for req in r.get("requires", []):
            if req.startswith("env:"):
                needed_envs.add(req[4:])
            elif req.startswith("ollama:"):
                needed_models.add(req[7:])

    for var in sorted(needed_envs):
        if not os.environ.get(var):
            issues.append(f"  ✗  env {var} not set")
        else:
            print(f"  ✓  env {var} SET")

    if needed_models:
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
            available = {m["name"] for m in resp.json().get("models", [])}
            for model in sorted(needed_models):
                if model in available:
                    print(f"  ✓  ollama {model} available")
                else:
                    # Partial match (e.g. "gemma4" matches "gemma4:e4b")
                    base = model.split(":")[0]
                    matches = [m for m in available if m.startswith(base)]
                    if matches:
                        print(f"  ~  ollama {model} → using {matches[0]}")
                    else:
                        issues.append(f"  ✗  ollama {model} not pulled  (ollama pull {model})")
        except Exception:
            issues.append("  ✗  Ollama not reachable (ollama serve)")

    return len(issues) == 0, issues


# ── Runner ────────────────────────────────────────────────────────────────────

def run_recipe(recipe: dict, log_path: Path) -> tuple[bool, float]:
    cmd = recipe["args"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = datetime.now()
    try:
        with open(log_path, "w") as log_file:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, cwd=str(REPO_ROOT),
            )
            for line in (proc.stdout or []):
                log_file.write(line)
                sys.stdout.write(f"     | {line.rstrip()}\n")
            proc.wait()
            ok = proc.returncode == 0
    except Exception as e:
        print(f"     | ERROR: {e}")
        ok = False
    elapsed = (datetime.now() - start).total_seconds()
    return ok, elapsed


def run_recipe_parallel(recipe: dict, log_path: Path) -> dict:
    rid, name = recipe["id"], recipe["name"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = datetime.now()
    print(f"[{rid}] {name}  →  started")
    sys.stdout.flush()
    try:
        with open(log_path, "w") as lf:
            proc = subprocess.Popen(
                recipe["args"], stdout=lf, stderr=subprocess.STDOUT,
                text=True, cwd=str(REPO_ROOT),
            )
            proc.wait()
        ok = proc.returncode == 0
    except Exception as e:
        print(f"[{rid}] ERROR: {e}")
        ok = False
    elapsed = (datetime.now() - start).total_seconds()
    print(f"[{rid}] {name}  →  {'SUCCESS' if ok else 'FAILED'}  ({elapsed:.1f}s)")
    sys.stdout.flush()
    return {"id": rid, "name": name, "ok": ok, "elapsed": elapsed}


# ── Display ───────────────────────────────────────────────────────────────────

def print_list(recipes: list[dict]) -> None:
    print(f"\n{'ID':<6} {'Name':<28} {'Tier':<6} {'Status':<12} {'Category'}")
    print("-" * 72)
    for r in recipes:
        marker = MARKERS.get(r.get("approval_status", ""), "  ")
        active = "active" if r.get("is_active") else "inactive"
        tier   = r.get("tier", "-")
        print(f"{r['id']:<6} {r['name']:<28} {tier!s:<6} {active:<12} {r.get('category','')}")


def print_catalog(recipes: list[dict]) -> None:
    print(f"\n{'ID':<6} {'Name':<28} {'Tier':<5} {'Requires':<45} {'Status'}")
    print("-" * 100)
    for r in recipes:
        reqs   = ", ".join(r.get("requires", []))
        status = r.get("approval_status", "")
        tier   = r.get("tier", "-")
        print(f"{r['id']:<6} {r['name']:<28} {tier!s:<5} {reqs:<45} {status}")
        print(f"       {r['description']}")
        print()


# ── Main ──────────────────────────────────────────────────────────────────────

@click.command()
@click.argument("command", default="run",
                type=click.Choice(["run", "list", "catalog", "check"]))
@click.option("--ids",      default=None, help="Comma-separated recipe IDs or ranges (e.g. 50,52-54)")
@click.option("--tier",     default=None, help="Comma-separated tier numbers (1=Ollama, 2=OpenAI, 3=OpenRouter)")
@click.option("--category", default=None, help="Filter by category (e.g. multimodal)")
@click.option("--status",   default=None, help="Filter by approval status (new|approved|wip)")
@click.option("--all",      "include_all", is_flag=True, help="Include inactive recipes")
@click.option("--workers",  default=1, show_default=True, type=int,
              help="Parallel workers (1 = sequential)")
def main(command, ids, tier, category, status, include_all, workers) -> None:
    """SPL 3.0 Cookbook batch runner."""
    recipes  = load_catalog()
    id_set   = parse_id_filter(ids)    if ids   else set()
    tier_set = parse_tier_filter(tier) if tier  else set()

    filtered = apply_filters(
        recipes,
        category=category or "",
        status=status or "",
        tiers=tier_set,
        ids=id_set,
        include_inactive=include_all or bool(id_set) or bool(tier_set),
    )

    if command == "list":
        print_list(filtered)
        click.echo(f"\n{len(filtered)} recipe(s) shown")
        return

    if command == "catalog":
        print_catalog(filtered)
        return

    if command == "check":
        click.echo(f"\nChecking prerequisites for {len(filtered)} recipe(s)...\n")
        ok, issues = check_prerequisites(filtered)
        if issues:
            click.echo("\nIssues found:")
            for issue in issues:
                click.echo(issue)
            sys.exit(1)
        else:
            click.echo("\nAll prerequisites satisfied.")
        return

    # ── run ──────────────────────────────────────────────────────────────────
    if not filtered:
        click.echo("No recipes match the filter. Use --all to include inactive recipes.")
        sys.exit(0)

    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = COOKBOOK_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    click.echo(f"\n{'='*60}")
    click.echo(f"SPL 3.0 Cookbook — {len(filtered)} recipe(s)  [{ts}]")
    click.echo(f"{'='*60}\n")

    results: list[dict] = []

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    run_recipe_parallel,
                    r,
                    log_dir / f"{r['log']}_{ts}.md",
                ): r for r in filtered
            }
            for fut in as_completed(futures):
                results.append(fut.result())
    else:
        for r in filtered:
            rid, name = r["id"], r["name"]
            tier_label = TIER_LABELS.get(r.get("tier", 0), "")
            log_path = log_dir / f"{r['log']}_{ts}.md"
            click.echo(f"[{rid}] {name}  ({tier_label})")
            ok, elapsed = run_recipe(r, log_path)
            status_str = "SUCCESS" if ok else "FAILED"
            click.echo(f"[{rid}] {status_str}  ({elapsed:.1f}s)  log: {log_path.name}\n")
            results.append({"id": rid, "name": name, "ok": ok, "elapsed": elapsed})

    passed = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    total_s = sum(r["elapsed"] for r in results)

    click.echo(f"\n{'='*60}")
    click.echo(f"Summary: {len(passed)}/{len(results)} passed  ({total_s:.1f}s total)")
    if failed:
        click.echo(f"\nFailed:")
        for r in failed:
            click.echo(f"  [{r['id']}] {r['name']}")
    click.echo(f"{'='*60}\n")

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
