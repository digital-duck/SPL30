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
