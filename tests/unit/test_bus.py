"""Tests for the in-process async event bus."""

from apron.bus.bus import EventBus
from apron.bus.events import IssueClaimed, IssueQueued, ReviewOpened


def make_queued(issue_id="i1"):
    return IssueQueued(issue_id=issue_id, task_id="t1", title="x", description="y")


async def test_subscriber_receives_published_event():
    bus = EventBus()
    received = []
    bus.subscribe(received.append)

    event = make_queued()
    await bus.publish(event)

    assert received == [event]


async def test_type_filter_only_delivers_matching_events():
    bus = EventBus()
    received = []
    bus.subscribe(received.append, event_types=IssueClaimed)

    await bus.publish(make_queued())
    claimed = IssueClaimed(issue_id="i1", worker_id="w1")
    await bus.publish(claimed)

    assert received == [claimed]


async def test_tuple_of_types_matches_any_of_them():
    bus = EventBus()
    received = []
    bus.subscribe(received.append, event_types=(IssueClaimed, ReviewOpened))

    claimed = IssueClaimed(issue_id="i1", worker_id="w1")
    opened = ReviewOpened(issue_id="i1", worker_id="w1", branch="issue/i1")
    await bus.publish(make_queued())
    await bus.publish(claimed)
    await bus.publish(opened)

    assert received == [claimed, opened]


async def test_all_subscribers_receive_the_event_in_subscribe_order():
    bus = EventBus()
    order = []
    bus.subscribe(lambda e: order.append("first"))
    bus.subscribe(lambda e: order.append("second"))

    await bus.publish(make_queued())

    assert order == ["first", "second"]


async def test_async_handlers_are_awaited():
    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event)

    bus.subscribe(handler)
    event = make_queued()
    await bus.publish(event)

    assert received == [event]


async def test_unsubscribe_stops_delivery():
    bus = EventBus()
    received = []
    subscription = bus.subscribe(received.append)

    await bus.publish(make_queued("i1"))
    subscription.unsubscribe()
    await bus.publish(make_queued("i2"))

    assert len(received) == 1
    subscription.unsubscribe()  # a second call is harmless


async def test_a_failing_handler_does_not_block_the_others():
    bus = EventBus()
    received = []

    def broken(event):
        raise RuntimeError("boom")

    bus.subscribe(broken)
    bus.subscribe(received.append)

    event = make_queued()
    await bus.publish(event)

    assert received == [event]
