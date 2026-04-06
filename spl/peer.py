"""Hub-to-Hub peering: the Internet of AI Agents.

Each Momagrid Hub is an autonomous compute domain — like an Autonomous
System (AS) in BGP terms. Hub-to-Hub peering connects these domains
across WAN, forming the 'Internet of AI Agents'.

Analogy map:
  BGP autonomous system  → Momagrid Hub + its GPU nodes
  BGP peering session    → HubPeeringSession (this module)
  Routing table          → PeeringTable (workflow name → peer Hub URL)
  Transit / next-hop     → peer_hub field on POST /tasks payload
  DNS resolution         → workflow name → Hub URL lookup

Peering Protocol:
  1. Hub A sends GET /peer/handshake to Hub B.
  2. Hub B responds with its workflow list, tier, and public key.
  3. Hub A adds Hub B to its peering table.
  4. When Hub A receives CALL for an unknown workflow, it routes to
     the peer that owns it via POST /tasks with peer_hub set.
  5. The target peer executes the workflow and returns the result.
     From the client's perspective: seamless, one task_id.

This is WAN deployment: Oracle Cloud free tier is the first public peer.
No protocol changes — just a peer_hub routing field on the existing
POST /tasks payload.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

_log = logging.getLogger("spl.peer")


@dataclass
class PeerInfo:
    """Metadata about a peer Hub, populated during peering handshake."""
    url: str
    workflows: list[str] = field(default_factory=list)
    tier: str = "SILVER"
    latency_ms: float = 0.0
    last_seen: float = field(default_factory=time.time)

    def is_stale(self, ttl_seconds: float = 300.0) -> bool:
        return (time.time() - self.last_seen) > ttl_seconds


class PeeringTable:
    """Routing table: workflow name → peer Hub URL.

    Analogous to a BGP routing table. Populated by peering handshakes
    and refreshed periodically.
    """

    def __init__(self) -> None:
        self._peers: dict[str, PeerInfo] = {}          # url → PeerInfo
        self._routes: dict[str, str] = {}              # workflow_name → peer_url

    def add_peer(self, info: PeerInfo) -> None:
        self._peers[info.url] = info
        for wf in info.workflows:
            self._routes[wf] = info.url
        _log.info(
            "Peering: added peer %s (%s workflows, tier=%s, latency=%.0fms)",
            info.url, len(info.workflows), info.tier, info.latency_ms,
        )

    def remove_peer(self, url: str) -> None:
        if url not in self._peers:
            return
        info = self._peers.pop(url)
        for wf in info.workflows:
            if self._routes.get(wf) == url:
                del self._routes[wf]
        _log.info("Peering: removed peer %s", url)

    def route(self, workflow_name: str) -> str | None:
        """Return the peer Hub URL that owns this workflow, or None."""
        return self._routes.get(workflow_name)

    def peers(self) -> list[PeerInfo]:
        return list(self._peers.values())

    def __len__(self) -> int:
        return len(self._peers)


class HubPeeringSession:
    """Manages the peering handshake with a remote Hub.

    Usage:
        session = HubPeeringSession(local_hub_url="http://localhost:8080")
        peer = await session.handshake("https://oracle-hub.momagrid.org")
        table.add_peer(peer)
    """

    def __init__(self, local_hub_url: str, timeout: float = 10.0) -> None:
        self.local_hub_url = local_hub_url
        self._timeout = timeout

    async def handshake(self, peer_url: str) -> PeerInfo:
        """Perform peering handshake with a remote Hub.

        GET /peer/handshake → {workflows, tier, latency_ms}
        """
        import httpx as _httpx

        peer_url = peer_url.rstrip("/")
        t0 = time.perf_counter()

        async with _httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{peer_url}/peer/handshake",
                params={"from": self.local_hub_url},
            )
            resp.raise_for_status()

        latency = (time.perf_counter() - t0) * 1000
        data = resp.json()

        info = PeerInfo(
            url=peer_url,
            workflows=data.get("workflows", []),
            tier=data.get("tier", "SILVER"),
            latency_ms=latency,
        )
        _log.info(
            "Peering handshake with %s: %d workflows, tier=%s, latency=%.0fms",
            peer_url, len(info.workflows), info.tier, latency,
        )
        return info

    async def refresh_all(self, table: PeeringTable) -> None:
        """Re-handshake all peers in the table to refresh workflow lists."""
        import asyncio
        peers = table.peers()
        results = await asyncio.gather(
            *[self.handshake(p.url) for p in peers],
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                _log.warning("Peering refresh failed for %s: %s", peers[i].url, result)
                if peers[i].is_stale():
                    table.remove_peer(peers[i].url)
            else:
                table.add_peer(result)
