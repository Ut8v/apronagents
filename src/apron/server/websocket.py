"""Fans bus events out to connected dashboards over WebSocket.

Every connection first receives a full state snapshot (so a late-joining
dashboard catches up from the store), then a live stream of events exactly
as they cross the bus."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from apron.server.routes import ServerContext, state_payload


def register_websocket(app: FastAPI, ctx: ServerContext) -> None:
    @app.websocket("/ws")
    async def live_feed(websocket: WebSocket) -> None:
        await websocket.accept()
        queue: asyncio.Queue = asyncio.Queue()
        subscription = ctx.bus.subscribe(queue.put_nowait)
        try:
            await websocket.send_json({"type": "snapshot", "state": state_payload(ctx)})
            while True:
                event = await queue.get()
                await websocket.send_json({"type": "event", "event": event.to_dict()})
        except WebSocketDisconnect:
            pass
        finally:
            subscription.unsubscribe()
