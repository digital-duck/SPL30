"""Internal helper: parse a .spl file and extract WORKFLOW definitions.

Uses the SPL 2.0 lexer + parser. Only WORKFLOW statements are registered;
PROMPT statements and top-level expressions are ignored for registry purposes.
"""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger("spl3.loader")


def load_workflows_from_file(path: Path) -> list:
    """Parse path and return a list of WorkflowDefinition objects."""
    from spl3.registry import WorkflowDefinition

    try:
        from spl.lexer import Lexer
        from spl.parser import Parser
        from spl.ast_nodes import WorkflowStatement
    except ImportError as e:
        raise ImportError(
            "spl-llm 2.0 must be installed: pip install spl-llm>=2.0.0"
        ) from e

    source = path.read_text(encoding="utf-8")
    tokens = Lexer(source).tokenize()
    statements = Parser(tokens).parse()

    defns = []
    for stmt in statements:
        if isinstance(stmt, WorkflowStatement):
            defns.append(WorkflowDefinition(
                name=stmt.name,
                source_file=str(path),
                ast_node=stmt,
                source_text=_extract_workflow_source(source, stmt.name),
            ))
            _log.debug("Loaded workflow '%s' from %s", stmt.name, path.name)

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
            # Look for WORKFLOW <name> (case-insensitive)
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
