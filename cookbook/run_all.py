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

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

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

def main() -> None:
    p = argparse.ArgumentParser(
        description="SPL 3.0 Cookbook batch runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("command", nargs="?", default="run",
                   choices=["run", "list", "catalog", "check"],
                   help="run (default) | list | catalog | check")
    p.add_argument("--ids",      help="Comma-separated recipe IDs or ranges (e.g. 50,52-54)")
    p.add_argument("--tier",     help="Comma-separated tier numbers to include (1=Ollama, 2=OpenAI, 3=OpenRouter, 4=all keys)")
    p.add_argument("--category", help="Filter by category (e.g. multimodal)")
    p.add_argument("--status",   help="Filter by approval status (new|approved|wip)")
    p.add_argument("--all",      action="store_true", help="Include inactive recipes")
    p.add_argument("--workers",  type=int, default=1,
                   help="Parallel workers (default 1 = sequential)")
    args = p.parse_args()

    recipes  = load_catalog()
    id_set   = parse_id_filter(args.ids)    if args.ids   else set()
    tier_set = parse_tier_filter(args.tier) if args.tier  else set()

    filtered = apply_filters(
        recipes,
        category=args.category or "",
        status=args.status or "",
        tiers=tier_set,
        ids=id_set,
        include_inactive=args.all or bool(id_set) or bool(tier_set),
    )

    if args.command == "list":
        print_list(filtered)
        print(f"\n{len(filtered)} recipe(s) shown")
        return

    if args.command == "catalog":
        print_catalog(filtered)
        return

    if args.command == "check":
        print(f"\nChecking prerequisites for {len(filtered)} recipe(s)...\n")
        ok, issues = check_prerequisites(filtered)
        if issues:
            print("\nIssues found:")
            for issue in issues:
                print(issue)
            sys.exit(1)
        else:
            print("\nAll prerequisites satisfied.")
        return

    # ── run ──────────────────────────────────────────────────────────────────
    if not filtered:
        print("No recipes match the filter. Use --all to include inactive recipes.")
        sys.exit(0)

    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = COOKBOOK_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print(f"SPL 3.0 Cookbook — {len(filtered)} recipe(s)  [{ts}]")
    print(f"{'='*60}\n")

    results: list[dict] = []

    if args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
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
            print(f"[{rid}] {name}  ({tier_label})")
            ok, elapsed = run_recipe(r, log_path)
            status = "SUCCESS" if ok else "FAILED"
            print(f"[{rid}] {status}  ({elapsed:.1f}s)  log: {log_path.name}\n")
            results.append({"id": rid, "name": name, "ok": ok, "elapsed": elapsed})

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    total_s = sum(r["elapsed"] for r in results)

    print(f"\n{'='*60}")
    print(f"Summary: {len(passed)}/{len(results)} passed  ({total_s:.1f}s total)")
    if failed:
        print(f"\nFailed:")
        for r in failed:
            print(f"  [{r['id']}] {r['name']}")
    print(f"{'='*60}\n")

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
