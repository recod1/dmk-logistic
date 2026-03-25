from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class NotificationRealtimeHub:
    """
    In-memory realtime hub for notification fan-out.
    Each process keeps its own websocket connections.
    """

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user_id, None)

    async def publish_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._connections.get(user_id, set()))

        dead: list[WebSocket] = []
        for socket in sockets:
            try:
                await socket.send_json(payload)
            except Exception:
                dead.append(socket)

        if dead:
            async with self._lock:
                current = self._connections.get(user_id)
                if not current:
                    return
                for socket in dead:
                    current.discard(socket)
                if not current:
                    self._connections.pop(user_id, None)

    async def publish_to_users(self, user_ids: list[int], payload: dict[str, Any]) -> None:
        unique_ids = sorted(set(user_ids))
        for user_id in unique_ids:
            await self.publish_to_user(user_id, payload)


notifications_realtime_hub = NotificationRealtimeHub()
