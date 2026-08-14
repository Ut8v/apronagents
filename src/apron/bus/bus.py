"""In-process async event bus.

Producers publish events; subscribers receive the ones they asked for.
Handlers may be plain callables or coroutine functions. A failing handler is
logged and skipped so one broken subscriber can never stall the others.
"""

from __future__ import annotations

import inspect
import logging
from typing import Awaitable, Callable

from apron.bus.events import Event

log = logging.getLogger(__name__)

Handler = Callable[[Event], None | Awaitable[None]]


class Subscription:
    """A live link between the bus and one handler. Call ``unsubscribe`` to end it."""

    def __init__(
        self,
        bus: "EventBus",
        handler: Handler,
        event_types: tuple[type[Event], ...] | None,
    ) -> None:
        self._bus = bus
        self.handler = handler
        self.event_types = event_types

    def matches(self, event: Event) -> bool:
        return self.event_types is None or isinstance(event, self.event_types)

    def unsubscribe(self) -> None:
        self._bus._remove(self)


class EventBus:
    """The single coordination channel every organ reads from and writes to."""

    def __init__(self) -> None:
        self._subscriptions: list[Subscription] = []

    def subscribe(
        self,
        handler: Handler,
        event_types: type[Event] | tuple[type[Event], ...] | None = None,
    ) -> Subscription:
        """Register ``handler`` for ``event_types`` (subclasses included).

        With ``event_types`` omitted, the handler receives every event.
        """
        if event_types is not None and not isinstance(event_types, tuple):
            event_types = (event_types,)
        subscription = Subscription(self, handler, event_types)
        self._subscriptions.append(subscription)
        return subscription

    async def publish(self, event: Event) -> None:
        """Deliver ``event`` to every matching subscriber, in subscribe order."""
        for subscription in list(self._subscriptions):
            if not subscription.matches(event):
                continue
            try:
                result = subscription.handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                log.exception(
                    "subscriber %r failed on %s", subscription.handler, event.kind
                )

    def _remove(self, subscription: Subscription) -> None:
        try:
            self._subscriptions.remove(subscription)
        except ValueError:
            pass  # already unsubscribed
