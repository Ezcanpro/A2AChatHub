"""File: protocol/websocket_protocol.py.

Defines the A2A message schema and lightweight WebSocket helpers.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

try:
    import websockets
except ImportError:  # pragma: no cover - depends on local environment
    websockets = None

Message = Dict[str, str]
MessageHandler = Callable[[Message], Any]


def _ensure_websockets_installed() -> None:
    if websockets is None:
        raise RuntimeError(
            "The 'websockets' package is required for WebSocket server/client usage. "
            "Install dependencies with: pip install -r requirements.txt"
        )


def build_message(sender: str, receiver: str, content: str) -> Message:
    """Create a protocol-compliant JSON message."""

    return {
        "sender": sender,
        "receiver": receiver,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": content,
    }


def normalize_message(message: Dict[str, Any]) -> Message:
    """Normalize arbitrary mappings into the required wire format."""

    return {
        "sender": str(message.get("sender", "")),
        "receiver": str(message.get("receiver", "")),
        "timestamp": str(
            message.get("timestamp") or datetime.now(timezone.utc).isoformat()
        ),
        "content": str(message.get("content", "")),
    }


class EventBus:
    """Simple event bus with sync and async subscriber support."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[MessageHandler]] = {}

    def subscribe(self, event_name: str, callback: MessageHandler) -> None:
        self._subscribers.setdefault(event_name, []).append(callback)

    async def publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        for callback in self._subscribers.get(event_name, []):
            result = callback(payload)
            if inspect.isawaitable(result):
                await result


class WebSocketA2AServer:
    """A2A WebSocket server with event subscription and message push support."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        on_message: Optional[Callable[[Message], Awaitable[Any]]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.on_message = on_message
        self.event_bus = EventBus()
        self._server = None
        self._clients: Set[Any] = set()

    def subscribe(self, event_name: str, callback: MessageHandler) -> None:
        self.event_bus.subscribe(event_name, callback)

    async def start(self) -> None:
        _ensure_websockets_installed()
        self._server = await websockets.serve(self._handler, self.host, self.port)
        await self.event_bus.publish(
            "server_started",
            build_message(
                sender="WebSocketServer",
                receiver="Console",
                content=f"WebSocket server started at ws://{self.host}:{self.port}",
            ),
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            await self.event_bus.publish(
                "server_stopped",
                build_message(
                    sender="WebSocketServer",
                    receiver="Console",
                    content="WebSocket server stopped.",
                ),
            )

    async def push(self, message: Dict[str, Any]) -> None:
        """Push a message to all connected clients."""

        _ensure_websockets_installed()
        if not self._clients:
            return

        payload = json.dumps(normalize_message(message), ensure_ascii=False)
        stale_clients: List[Any] = []
        for client in self._clients:
            try:
                await client.send(payload)
            except Exception:
                stale_clients.append(client)

        for client in stale_clients:
            self._clients.discard(client)

    async def _handler(self, websocket: Any) -> None:
        self._clients.add(websocket)
        try:
            async for raw_message in websocket:
                message = normalize_message(json.loads(raw_message))
                await self.event_bus.publish("message_received", message)
                if self.on_message is not None:
                    await self.on_message(message)
        finally:
            self._clients.discard(websocket)


class WebSocketA2AClient:
    """A2A WebSocket client with subscription support."""

    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.event_bus = EventBus()
        self._connection = None
        self._listener_task: Optional[asyncio.Task[Any]] = None

    def subscribe(self, event_name: str, callback: MessageHandler) -> None:
        self.event_bus.subscribe(event_name, callback)

    async def connect(self) -> None:
        _ensure_websockets_installed()
        self._connection = await websockets.connect(self.uri)
        self._listener_task = asyncio.create_task(self._listen())
        await self.event_bus.publish(
            "connected",
            build_message(
                sender="WebSocketClient",
                receiver="Console",
                content=f"Connected to {self.uri}",
            ),
        )

    async def disconnect(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task

        if self._connection is not None:
            await self._connection.close()
            await self.event_bus.publish(
                "disconnected",
                build_message(
                    sender="WebSocketClient",
                    receiver="Console",
                    content=f"Disconnected from {self.uri}",
                ),
            )

    async def send_message(self, message: Dict[str, Any]) -> None:
        _ensure_websockets_installed()
        if self._connection is None:
            raise RuntimeError("WebSocket client is not connected.")

        await self._connection.send(
            json.dumps(normalize_message(message), ensure_ascii=False)
        )
        await self.event_bus.publish("message_sent", normalize_message(message))

    async def _listen(self) -> None:
        if self._connection is None:
            return

        async for raw_message in self._connection:
            message = normalize_message(json.loads(raw_message))
            await self.event_bus.publish("message_received", message)
