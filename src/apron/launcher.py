"""Process supervisor: boots the organs, wires them to the shared bus, and
shuts them down cleanly.

Phase 1 scope: the launcher builds the nervous system (bus + store) and wires
the store to the bus. The organs themselves (orchestrator, workers, merge
controller, server) are attached in later phases.
"""

from __future__ import annotations

import asyncio
import logging

from apron.bus.bus import EventBus
from apron.bus.store import StateStore
from apron.config import Settings

log = logging.getLogger(__name__)


class Launcher:
    """Owns the process tree for one Apron run."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bus = EventBus()
        self.store = StateStore(settings.db_path or ":memory:")
        # Every event that happens is journaled, so a late-joining dashboard
        # can always catch up from the store instead of asking an organ.
        self._store_subscription = self.bus.subscribe(self.store.record)

    async def start(self) -> None:
        """Boot the organs. Nothing to boot yet beyond the bus wiring."""
        log.info(
            "apron launcher ready (mode=%s, workers=%d)",
            self.settings.mode,
            self.settings.worker_count,
        )

    async def stop(self) -> None:
        """Shut everything down cleanly."""
        self._store_subscription.unsubscribe()
        self.store.close()
        log.info("apron launcher stopped")


def launch(settings: Settings) -> None:
    """Run one full Apron session, blocking until it finishes."""

    async def _run() -> None:
        launcher = Launcher(settings)
        try:
            await launcher.start()
        finally:
            await launcher.stop()

    asyncio.run(_run())
