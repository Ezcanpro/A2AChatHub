"""File: frontend/cli.py.

Simple CLI frontend for viewing multi-agent conversations.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict


class ChatCLI:
    """Terminal UI for the Alice/Bob demo."""

    def __init__(
        self,
        coordinator,
        default_receiver: str = "Alice",
        backend_name: str = "rule",
        model_name: str = "rule-based-demo",
    ) -> None:
        self.coordinator = coordinator
        self.default_receiver = default_receiver
        self.backend_name = backend_name
        self.model_name = model_name
        self.coordinator.subscribe("message", self._display_message)
        self.coordinator.subscribe("warning", self._display_warning)

    async def run_demo(self) -> None:
        """Run a built-in demo conversation."""

        self.coordinator.reset_agents()
        demo_prompt = "Hello Alice, please discuss the A2A project plan with Bob."
        print(
            "\n[Demo] Starting Alice and Bob conversation "
            f"(backend={self.backend_name}, model={self.model_name})...\n"
        )
        await self.coordinator.send_user_message(
            content=demo_prompt,
            receiver=self.default_receiver,
        )
        print("\n[Demo] Conversation complete. Logs are available in logs/messages.json.\n")

    async def start(self) -> None:
        """Start the interactive CLI loop."""

        await self.run_demo()
        if self.backend_name == "rule":
            print("Rule mode is active. The project will only demonstrate message flow.\n")
        else:
            print("Live model mode is active. User questions will be sent to the configured backend.\n")
        print("Interactive CLI started. Type a message, or type 'exit' to quit.\n")

        while True:
            user_input = await asyncio.to_thread(input, "You -> Alice: ")
            if user_input.strip().lower() in {"exit", "quit"}:
                print("CLI session ended.")
                return

            if not user_input.strip():
                continue

            self.coordinator.reset_agents()
            await self.coordinator.send_user_message(
                content=user_input,
                receiver=self.default_receiver,
            )
            print("")

    def _display_message(self, message: Dict[str, Any]) -> None:
        print(
            f"[{message['timestamp']}] {message['sender']} -> "
            f"{message['receiver']}: {message['content']}"
        )

    def _display_warning(self, message: Dict[str, Any]) -> None:
        print(f"[Warning] {message['content']}")
