"""File: main.py.

Project entry point for the A2A-ChatHub demo.
"""

from __future__ import annotations

import argparse
import asyncio

from agents import ExampleAgent
from coordinator import Coordinator
from frontend import ChatCLI
from llm import LLMClient
from protocol import WebSocketA2AServer


async def async_main() -> None:
    parser = argparse.ArgumentParser(description="A2A-ChatHub demo application")
    parser.add_argument(
        "--with-server",
        action="store_true",
        help="Start the optional WebSocket server in the background.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="WebSocket server host.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="WebSocket server port.",
    )
    parser.add_argument(
        "--demo-only",
        action="store_true",
        help="Run the built-in Alice/Bob demo once and exit.",
    )
    parser.add_argument(
        "--backend",
        choices=["rule", "openai", "local", "auto"],
        default="rule",
        help="Toggle between rule-based demo mode and live model mode.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the model name for a live backend.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the API base URL for a live backend.",
    )
    args = parser.parse_args()

    coordinator = Coordinator(log_path="logs/messages.json")
    llm_client = LLMClient.from_env(
        backend=args.backend,
        model=args.model,
        base_url=args.base_url,
    )

    alice = ExampleAgent(
        name="Alice",
        peer_name="Bob",
        persona="Alice is a planner who breaks tasks into milestones",
        role_description="Your job is to receive the user's request, coordinate with Bob when live mode is active, and produce the final answer for the user.",
        llm_client=llm_client,
        model_backend=llm_client.backend,
        max_auto_replies=2,
    )
    bob = ExampleAgent(
        name="Bob",
        peer_name="Alice",
        persona="Bob is an implementer who turns plans into concrete actions",
        role_description="Your job is to help Alice by drafting the most useful answer content for the user.",
        llm_client=llm_client,
        model_backend=llm_client.backend,
        max_auto_replies=2,
    )

    coordinator.register_agent(alice)
    coordinator.register_agent(bob)

    server = None
    if args.with_server:
        server = WebSocketA2AServer(
            host=args.host,
            port=args.port,
            on_message=coordinator.handle_external_message,
        )
        server.subscribe(
            "server_started",
            lambda message: print(f"[Server] {message['content']}"),
        )
        await server.start()
        coordinator.subscribe("message", server.push)

    cli = ChatCLI(
        coordinator=coordinator,
        default_receiver="Alice",
        backend_name=llm_client.backend,
        model_name=llm_client.model,
    )

    try:
        if args.demo_only:
            await cli.run_demo()
        else:
            await cli.start()
    finally:
        if server is not None:
            await server.stop()


if __name__ == "__main__":
    asyncio.run(async_main())
