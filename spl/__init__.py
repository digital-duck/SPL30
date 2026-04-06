"""SPL 3.0 — Momagrid as Compute OS.

New in 3.0 over SPL 2.0:
  - WorkflowRegistry: name → WorkflowDef mapping (local + Hub-backed)
  - WorkflowComposer: CALL workflow_name(@args) INTO @var
  - COMMIT status → EXCEPTION channel mapping
  - IMPORT directive for multi-file workflow loading
  - CALL PARALLEL for concurrent sub-workflow dispatch
  - Hub-to-Hub peering for WAN workflow routing
"""

__version__ = "3.0.0-alpha"

# ── Composite package: extend __path__ to include SPL20's spl/ ─────────────────
# SPL30's spl/ adds v3.0 modules (registry, composer, executor, …).
# SPL20's spl/ provides adapters, storage, lexer, ast_nodes, config, …
# Modules present in SPL30 shadow SPL20; modules absent in SPL30 fall through
# to SPL20 transparently — so `from spl.adapters.claude_cli import …` works.
from pathlib import Path as _Path
_spl20_spl = _Path(__file__).parent.parent.parent / "SPL20" / "spl"
if _spl20_spl.exists():
    __path__ = list(__path__) + [str(_spl20_spl)]
