"""Hub-backed WorkflowRegistry.

The Momagrid Hub is the 'OS kernel' of the compute OS: it maintains a
workflow registry (name → definition) as shared memory across all
connected nodes and client sessions.

CALL workflow_name() in a client workflow routes to the Hub via the
existing POST /tasks protocol, extended with a 'type': 'workflow' field:

    POST /tasks
    {
      "type":     "workflow",          # NEW in SPL 3.0
      "workflow": "generate_code",
      "args":     {"spec": "..."},
      "model":    null,                # resolved by Hub from workflow def
      ...
    }

The Hub looks up the workflow in its registry, dispatches to an available
GPU node, and returns the OUTPUT via the existing GET /tasks/{id} response.
No new endpoints; no new infrastructure. One schema field extension.

Hub-to-Hub Peering (WAN):
    If the requested workflow is not registered on this Hub, the Hub
    queries its peer table and forwards the task to a peer Hub that
    owns the workflow — Hub-to-Hub routing, the 'internet' layer.

    POST /tasks
    {
      "type":      "workflow",
      "workflow":  "generate_code",
      "peer_hub":  "https://oracle-hub.momagrid.org",  # resolved by local Hub
      ...
    }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from spl3.registry import WorkflowDefinition, RegistryError

_log = logging.getLogger("spl3.hub_registry")


@dataclass
class HubPeer:
    """A peer Hub entry in the local Hub's routing table.

    Analogous to an entry in a BGP routing table / DNS record:
      url:       Hub endpoint (https://oracle-hub.momagrid.org)
      workflows: workflow names this peer owns (populated via peering handshake)
      latency_ms: last measured round-trip latency
      tier:      GOLD / SILVER / BRONZE (peer quality tier)
    """
    url: str
    workflows: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    tier: str = "SILVER"


class HubRegistry:
    """Queries the Momagrid Hub for remote workflow definitions.

    Used as the remote fallback in FederatedRegistry when a workflow
    is not found in the local registry.
    """

    def __init__(self, hub_url: str, timeout: float = 10.0) -> None:
        self.hub_url = hub_url.rstrip("/")
        self._timeout = timeout
        self._cache: dict[str, WorkflowDefinition] = {}

    def get(self, name: str) -> WorkflowDefinition:
        """Fetch a workflow definition from the Hub (with local cache)."""
        if name in self._cache:
            return self._cache[name]

        try:
            resp = httpx.get(
                f"{self.hub_url}/workflows/{name}",
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise RegistryError(
                    f"Workflow '{name}' not found on Hub at {self.hub_url}"
                ) from e
            raise RegistryError(
                f"Hub registry error for '{name}': {e}"
            ) from e
        except httpx.RequestError as e:
            raise RegistryError(
                f"Cannot reach Hub at {self.hub_url}: {e}"
            ) from e

        data = resp.json()
        defn = WorkflowDefinition(
            name=name,
            source_file=f"{self.hub_url}/workflows/{name}",
            ast_node=None,       # parsed lazily on first CALL
            source_text=data.get("source", ""),
        )
        self._cache[name] = defn
        _log.debug("HubRegistry: fetched '%s' from %s", name, self.hub_url)
        return defn

    def has(self, name: str) -> bool:
        if name in self._cache:
            return True
        try:
            self.get(name)
            return True
        except RegistryError:
            return False

    def list(self) -> list[str]:
        """List all workflows registered on this Hub."""
        try:
            resp = httpx.get(
                f"{self.hub_url}/workflows",
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return sorted(resp.json().get("workflows", []))
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            _log.warning("HubRegistry.list() failed: %s", e)
            return sorted(self._cache)

    def register(self, name: str, source: str) -> None:
        """Push a workflow definition to the Hub registry.

        Called by `spl3 register` CLI to populate the Hub's workflow table.
        """
        try:
            resp = httpx.post(
                f"{self.hub_url}/workflows",
                json={"name": name, "source": source},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            _log.info("HubRegistry: registered '%s' on Hub at %s", name, self.hub_url)
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            raise RegistryError(
                f"Failed to register '{name}' on Hub: {e}"
            ) from e
