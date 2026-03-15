"""File: coordinator/coordinator.py.

Coordinator for routing, context storage, and JSON logging.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from protocol.websocket_protocol import EventBus, build_message, normalize_message

MessageCallback = Callable[[Dict[str, Any]], Any]


class Coordinator:
    """Central router for A2A messages."""

    def __init__(self, log_path: str = "logs/messages.json") -> None:
        self.agents: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.context: Dict[str, List[Dict[str, Any]]] = {}
        self.log_path = Path(log_path)
        self.event_bus = EventBus()
        self._prepare_log_file()

    def register_agent(self, agent: Any) -> None:
        """Register an agent instance with the coordinator."""

        agent.attach(self)
        self.agents[agent.name] = agent
        self.context.setdefault(agent.name, [])

    def reset_agents(self) -> None:
        """Reset registered agents if they implement a reset hook."""

        for agent in self.agents.values():
            reset = getattr(agent, "reset", None)
            if callable(reset):
                reset()

    def subscribe(self, event_name: str, callback: MessageCallback) -> None:
        """Subscribe a callback to coordinator events."""

        self.event_bus.subscribe(event_name, callback)

    async def handle_external_message(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Entry point for CLI or WebSocket clients."""

        return await self.route_message(message)

    async def route_message(
        self,
        message: Dict[str, Any],
        max_hops: int = 10,
    ) -> List[Dict[str, Any]]:
        """Route a message until no more automatic replies are produced."""

        queue: List[Dict[str, Any]] = [normalize_message(message)]
        routed_messages: List[Dict[str, Any]] = []
        hops = 0

        while queue and hops < max_hops:
            current = normalize_message(queue.pop(0))
            self._record_message(current)
            await self.event_bus.publish("message", current)
            routed_messages.append(current)

            receiver = current["receiver"]
            agent = self.agents.get(receiver)
            if agent is not None:
                reply = await agent.receive_message(current)
                if reply:
                    queue.append(normalize_message(reply))

            hops += 1

        if queue:
            await self.event_bus.publish(
                "warning",
                {
                    "sender": "Coordinator",
                    "receiver": "Console",
                    "content": f"Routing stopped after {max_hops} hops to avoid infinite loops.",
                },
            )

        return routed_messages

    async def send_user_message(
        self,
        content: str,
        receiver: str = "Alice",
        sender: str = "User",
    ) -> List[Dict[str, Any]]:
        """Helper for CLI-triggered user messages."""

        return await self.route_message(
            build_message(sender=sender, receiver=receiver, content=content)
        )

    def get_history(self) -> List[Dict[str, Any]]:
        """Return the full conversation history."""

        return list(self.history)

    def get_context(self, agent_name: str) -> List[Dict[str, Any]]:
        """Return messages addressed to a specific agent."""

        return list(self.context.get(agent_name, []))

    def _prepare_log_file(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.write_text("[]", encoding="utf-8")

    def _record_message(self, message: Dict[str, Any]) -> None:
        self.history.append(message)
        self.context.setdefault(message["receiver"], []).append(message)
        self._write_logs()

    def _write_logs(self) -> None:
        self.log_path.write_text(
            json.dumps(self.history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
