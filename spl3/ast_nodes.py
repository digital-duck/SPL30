"""SPL 3.0 AST node additions over SPL 2.0.

New nodes:
  SetLiteral   — {a, b, c}  unordered unique collection literal
  ImportStatement — IMPORT 'file.spl'  multi-file workflow loading
  CallParallelStatement — CALL PARALLEL ... END  concurrent dispatch
"""

from __future__ import annotations
from dataclasses import dataclass, field

# Re-export SPL 2.0 nodes so callers can import from one place.
from spl.ast_nodes import Expression  # noqa: F401


@dataclass
class NoneLiteral(Expression):
    """NONE or NULL literal — first-class null value.

    SPL 2.0's Literal node only accepts str|int|float|bool values.
    NoneLiteral is a dedicated SPL 3.0 node that avoids the type clash
    and makes null intent explicit in the AST.

    At runtime evaluates to the empty string '' — consistent with
    state.get_var() returning '' for undefined variables.

    Usage:
        @result := NONE
        EVALUATE @score WHEN = NONE THEN ...  END
        INPUT: @threshold FLOAT DEFAULT NONE
    """


@dataclass
class SetLiteral(Expression):
    """{ expr, expr, ... } — unordered unique collection literal.

    Parsed when { } contains comma-separated elements with no colons:
      {'python', 'sql', 'linux'}  →  SetLiteral
      {'key': 'val'}              →  MapLiteral  (colon present)
      {}                          →  MapLiteral  (empty — MAP by default)

    At runtime serializes as a sorted, deduplicated JSON array:
      {'b', 'a', 'b'}  →  '["a", "b"]'
    """
    elements: list[Expression] = field(default_factory=list)


@dataclass
class ImportStatement:
    """IMPORT 'file.spl' — load workflow definitions from an external .spl file.

    Resolved at parse time relative to the current file.  All WORKFLOW
    definitions in the imported file are registered alongside the
    importing file's own definitions.

    Example:
        IMPORT 'lib/code_agents.spl'
        IMPORT '../shared/validators.spl'
    """
    path: str


@dataclass
class CallParallelBranch:
    """Single branch inside a CALL PARALLEL block.

    workflow_name : name of the workflow to call
    arguments     : positional argument expressions
    target_var    : caller's INTO @var binding
    """
    workflow_name: str
    arguments: list[Expression] = field(default_factory=list)
    target_var: str = ""


@dataclass
class CallParallelStatement:
    """CALL PARALLEL workflow_a(@x) INTO @a, workflow_b(@y) INTO @b END

    Dispatches multiple sub-workflows concurrently via asyncio.gather.
    The Hub routes each to an available node — same mechanism as
    existing multi-node task dispatch.

    All branches must complete (or fail) before execution continues.
    If any branch fails its WorkflowCompositionError propagates to the
    caller's EXCEPTION WHEN handler.
    """
    branches: list[CallParallelBranch] = field(default_factory=list)
