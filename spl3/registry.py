"""WorkflowRegistry: maps workflow names to their parsed definitions.

In SPL 3.0, CALL workflow_name(@args) INTO @var resolves through this
registry. Three registry backends are supported:

  1. LocalRegistry   — populated by parsing .spl files at startup
  2. HubRegistry     — Hub-backed via REST (see hub_registry.py)
  3. FederatedRegistry — queries local first, falls back to Hub peers

The registry is the 'workflow stack' in OS terms: shared memory that
the Hub maintains across call frames, analogous to a process table.

Usage:
    registry = LocalRegistry()
    registry.load_file("lib/code_agents.spl")
    registry.load_dir("cookbook/code_pipeline/")

    defn = registry.get("generate_code")   # WorkflowDefinition
    names = registry.list()                # ["generate_code", "review_code", ...]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger("spl.registry")


@dataclass
class WorkflowDefinition:
    """A parsed and registered SPL WORKFLOW definition.

    name:        workflow identifier (used by CALL)
    source_file: .spl file this was loaded from (for debugging)
    ast_node:    the parsed WorkflowStatement AST node (from spl3.ast_nodes)
    source_text: raw SPL source for the workflow block
    """
    name: str
    source_file: str
    ast_node: object       # spl.ast_nodes.WorkflowStatement
    source_text: str = ""


class RegistryError(Exception):
    pass


class LocalRegistry:
    """In-process workflow registry backed by parsed .spl files.

    Thread-safe for reads; writes should happen at startup before
    concurrent CALL resolution begins.
    """

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def register(self, defn: WorkflowDefinition) -> None:
        """Register a workflow definition. Overwrites on name collision."""
        if defn.name in self._workflows:
            _log.warning(
                "Registry: overwriting workflow '%s' (was from %s, now from %s)",
                defn.name,
                self._workflows[defn.name].source_file,
                defn.source_file,
            )
        self._workflows[defn.name] = defn
        _log.debug("Registry: registered '%s' from %s", defn.name, defn.source_file)

    def load_file(self, path: str | Path) -> int:
        """Parse a .spl file and register all WORKFLOW definitions found.

        Returns the number of workflows registered.
        """
        from spl3._loader import load_workflows_from_file
        path = Path(path)
        if not path.exists():
            raise RegistryError(f"File not found: {path}")
        defns = load_workflows_from_file(path)
        for defn in defns:
            self.register(defn)
        _log.info("Registry: loaded %d workflow(s) from %s", len(defns), path)
        return len(defns)

    def load_dir(self, directory: str | Path, pattern: str = "*.spl") -> int:
        """Recursively load all .spl files in a directory.

        Returns the total number of workflows registered.
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise RegistryError(f"Not a directory: {directory}")
        total = 0
        for spl_file in sorted(directory.rglob(pattern)):
            total += self.load_file(spl_file)
        return total

    # ------------------------------------------------------------------ #
    # Lookup                                                               #
    # ------------------------------------------------------------------ #

    def get(self, name: str) -> WorkflowDefinition:
        """Return the definition for a workflow name.

        Raises RegistryError if not found — CALL resolution failure.
        """
        if name not in self._workflows:
            known = ", ".join(sorted(self._workflows)) or "(none)"
            raise RegistryError(
                f"Unknown workflow '{name}'. "
                f"Registered workflows: {known}. "
                f"Use IMPORT or spl register to add it."
            )
        return self._workflows[name]

    def has(self, name: str) -> bool:
        return name in self._workflows

    def list(self) -> list[str]:
        return sorted(self._workflows)

    def __len__(self) -> int:
        return len(self._workflows)

    def __repr__(self) -> str:
        return f"LocalRegistry({self.list()})"


class FederatedRegistry:
    """Registry that queries local first, then Hub peers on miss.

    This is the default registry in Momagrid-connected deployments:
    - Locally-defined workflows resolve immediately (zero latency)
    - Unknown workflows route to the Hub's registry (peer resolution)

    In OS terms: local symbol table first, then shared library lookup.
    """

    def __init__(
        self,
        local: LocalRegistry,
        hub_registry=None,   # HubRegistry | None (from hub_registry.py)
    ) -> None:
        self._local = local
        self._hub = hub_registry

    def get(self, name: str) -> WorkflowDefinition:
        if self._local.has(name):
            return self._local.get(name)
        if self._hub is not None:
            return self._hub.get(name)
        raise RegistryError(
            f"Workflow '{name}' not found locally and no Hub registry configured."
        )

    def has(self, name: str) -> bool:
        return self._local.has(name) or (
            self._hub is not None and self._hub.has(name)
        )

    def list(self) -> list[str]:
        local = set(self._local.list())
        hub = set(self._hub.list()) if self._hub else set()
        return sorted(local | hub)
