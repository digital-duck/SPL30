"""Internal helper: parse a .spl file and extract WORKFLOW definitions.

Uses the SPL 3.0 lexer + parser (which extends SPL 2.0).
Only WORKFLOW statements are registered; PROMPT statements, top-level
expressions, and IMPORT statements are handled transparently.

IMPORT resolution:
  When an IMPORT 'file.spl' statement is encountered, the referenced file
  is loaded recursively.  Circular imports are detected by tracking the
  set of files currently being loaded.
"""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger("spl.loader")


def load_workflows_from_file(
    path: Path,
    _loading: set[Path] | None = None,
) -> list:
    """Parse path and return a list of WorkflowDefinition objects.

    Handles IMPORT statements recursively.
    _loading is an internal set used to detect circular imports.
    """
    from spl3.registry import WorkflowDefinition

    try:
        from spl.lexer import Lexer
        from spl.ast_nodes import WorkflowStatement
    except ImportError as e:
        raise ImportError(
            "spl-llm 2.0 must be installed: pip install spl-llm>=2.0.0"
        ) from e

    from spl3.parser import SPL3Parser
    from spl3.ast_nodes import ImportStatement

    path = path.resolve()

    # Circular import detection
    if _loading is None:
        _loading = set()
    if path in _loading:
        _log.warning("Circular IMPORT detected — skipping %s", path)
        return []
    _loading.add(path)

    source = path.read_text(encoding="utf-8")
    tokens = Lexer(source).tokenize()
    program = SPL3Parser(tokens).parse()

    defns: list[WorkflowDefinition] = []

    for stmt in program.statements:
        if isinstance(stmt, ImportStatement):
            # Resolve import path relative to the importing file's directory
            import_path = (path.parent / stmt.path).resolve()
            if not import_path.exists():
                _log.error("IMPORT: file not found: %s (from %s)", import_path, path)
                continue
            imported = load_workflows_from_file(import_path, _loading=_loading)
            defns.extend(imported)
            _log.debug(
                "IMPORT: loaded %d workflow(s) from %s", len(imported), import_path.name
            )

        elif isinstance(stmt, WorkflowStatement):
            defns.append(WorkflowDefinition(
                name=stmt.name,
                source_file=str(path),
                ast_node=stmt,
                source_text=_extract_workflow_source(source, stmt.name),
            ))
            _log.debug("Loaded workflow '%s' from %s", stmt.name, path.name)

    _loading.discard(path)
    return defns


def _extract_workflow_source(source: str, name: str) -> str:
    """Best-effort extraction of the raw SPL source for a named WORKFLOW block."""
    lines = source.splitlines()
    start = None
    depth = 0
    result_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip().upper()
        if start is None:
            if stripped.startswith("WORKFLOW") and name.upper() in stripped:
                start = i
                depth = 0

        if start is not None:
            result_lines.append(line)
            depth += stripped.count("DO") + stripped.count("BEGIN")
            depth -= stripped.count("END")
            if depth <= 0 and len(result_lines) > 1:
                break

    return "\n".join(result_lines)
