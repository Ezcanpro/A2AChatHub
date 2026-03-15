"""File: agents/base_agent.py.

Base abstractions for A2A-compatible agents.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from protocol.websocket_protocol import build_message

if TYPE_CHECKING:
    from coordinator.coordinator import Coordinator


class BaseAgent:
    """Base class for all agents in the project.

    Subclasses should override :meth:`respond` to implement custom behavior.
    """

    def __init__(
        self,
        name: str,
        coordinator: Optional["Coordinator"] = None,
        model_backend: str = "rule",
        system_prompt: str = "",
    ) -> None:
        self.name = name
        self.coordinator = coordinator
        self.model_backend = model_backend
        self.system_prompt = system_prompt
        self.inbox: List[Dict[str, Any]] = []

    def attach(self, coordinator: "Coordinator") -> None:
        """Attach the agent to a coordinator."""

        self.coordinator = coordinator

    def build_message(self, receiver: str, content: str) -> Dict[str, str]:
        """Create a protocol-compliant message."""

        return build_message(sender=self.name, receiver=receiver, content=content)

    async def send_message(self, receiver: str, content: str) -> List[Dict[str, Any]]:
        """Send a message through the coordinator."""

        if self.coordinator is None:
            raise RuntimeError(f"Agent '{self.name}' is not attached to a coordinator.")

        message = self.build_message(receiver=receiver, content=content)
        return await self.coordinator.route_message(message)

    async def receive_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Receive a message and optionally return an automatic response."""

        self.inbox.append(message)
        return await self.respond(message)

    async def respond(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Produce a response message.

        Override this in subclasses. Returning ``None`` means no reply.
        """

        return None
