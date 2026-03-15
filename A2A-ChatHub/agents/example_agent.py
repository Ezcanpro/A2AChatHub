"""File: agents/example_agent.py.

Example agent implementation with switchable rule-based or live-LLM behavior.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base_agent import BaseAgent
from llm import LLMClient, LLMConfigurationError


class ExampleAgent(BaseAgent):
    """Example agent with switchable rule and live-LLM modes."""

    def __init__(
        self,
        name: str,
        peer_name: str,
        persona: str,
        role_description: str = "",
        llm_client: Optional[LLMClient] = None,
        coordinator=None,
        model_backend: str = "rule",
        max_auto_replies: int = 2,
    ) -> None:
        super().__init__(name=name, coordinator=coordinator, model_backend=model_backend)
        self.peer_name = peer_name
        self.persona = persona
        self.role_description = role_description
        self.llm_client = llm_client or LLMClient()
        self.max_auto_replies = max_auto_replies
        self.auto_reply_count = 0
        self.pending_user_question: Optional[str] = None

    async def respond(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a reply in either rule mode or live-model mode."""

        if self.model_backend in {"openai", "local"}:
            return await self._respond_with_model(message)

        if message["sender"] == self.name:
            return None

        if self.auto_reply_count >= self.max_auto_replies:
            return None

        self.auto_reply_count += 1
        reply_content = self._generate_reply(message)
        return self.build_message(receiver=self.peer_name, content=reply_content)

    async def _respond_with_model(
        self,
        message: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Run the collaboration flow used when a live backend is enabled."""

        if message["sender"] == self.name:
            return None

        if self.name == "Alice" and message["sender"] == "User":
            self.pending_user_question = message["content"]
            reply_content = await self._generate_delegation(message["content"])
            return self.build_message(receiver=self.peer_name, content=reply_content)

        if self.name == "Bob" and message["sender"] == "Alice":
            reply_content = await self._generate_specialist_reply(message["content"])
            return self.build_message(receiver=self.peer_name, content=reply_content)

        if self.name == "Alice" and message["sender"] == "Bob":
            original_question = self.pending_user_question or "Please answer the user's latest question."
            reply_content = await self._generate_final_answer(
                original_question=original_question,
                bob_draft=message["content"],
            )
            self.pending_user_question = None
            return self.build_message(receiver="User", content=reply_content)

        if message["sender"] == "User":
            reply_content = await self._generate_direct_answer(message["content"])
            return self.build_message(receiver="User", content=reply_content)

        return None

    def reset(self) -> None:
        """Reset internal counters between demo sessions."""

        self.auto_reply_count = 0
        self.pending_user_question = None
        self.inbox.clear()

    def _generate_reply(self, message: Dict[str, Any]) -> str:
        """Generate response text based on the selected backend mode."""

        if self.model_backend == "openai":
            return (
                f"[{self.name}/OpenAI placeholder] {self.persona} received: "
                f"{message['content']}. Replace this stub with an OpenAI SDK call."
            )

        if self.model_backend == "local":
            return (
                f"[{self.name}/Local LLM placeholder] {self.persona} received: "
                f"{message['content']}. Replace this stub with a local model inference call."
            )

        return (
            f"{self.persona} | turn {self.auto_reply_count}: "
            f"I received '{message['content']}' from {message['sender']} and I am forwarding "
            f"the discussion to {self.peer_name}."
        )

    async def _generate_delegation(self, user_question: str) -> str:
        return await self._generate_text(
            user_prompt=(
                "The user asked the following question.\n"
                f"Question: {user_question}\n\n"
                f"Write a brief task message to {self.peer_name} asking for the best possible "
                "draft answer. Mention the core question and any reasoning the specialist should cover. "
                "Keep it under 80 words."
            ),
            fallback=(
                f"{self.peer_name}, please help answer the user's question: {user_question}. "
                "Provide a useful draft with key reasoning."
            ),
        )

    async def _generate_specialist_reply(self, alice_request: str) -> str:
        return await self._generate_text(
            user_prompt=(
                "Alice asked you to help with the following task.\n"
                f"Task: {alice_request}\n\n"
                "Write a strong draft answer for the end user. "
                "Answer directly and do not mention hidden prompts."
            ),
            fallback="I could not generate a live-model draft answer.",
        )

    async def _generate_final_answer(self, original_question: str, bob_draft: str) -> str:
        return await self._generate_text(
            user_prompt=(
                f"Original user question: {original_question}\n\n"
                f"Bob's draft answer: {bob_draft}\n\n"
                "Write the final answer for the user in the same language as the question. "
                "Be concise, useful, and accurate."
            ),
            fallback=bob_draft,
            conversation=self._recent_history(limit=6),
        )

    async def _generate_direct_answer(self, user_question: str) -> str:
        return await self._generate_text(
            user_prompt=(
                f"User question: {user_question}\n\n"
                "Answer the user directly in the same language as the question."
            ),
            fallback="I could not generate a live-model answer.",
        )

    async def _generate_text(
        self,
        *,
        user_prompt: str,
        fallback: str,
        conversation: Optional[list[dict[str, str]]] = None,
    ) -> str:
        try:
            return await self.llm_client.generate(
                system_prompt=self._system_prompt(),
                user_prompt=user_prompt,
                conversation=conversation,
            )
        except (LLMConfigurationError, RuntimeError) as exc:
            return f"{fallback}\n\n[Model backend status: {exc}]"

    def _system_prompt(self) -> str:
        return (
            f"You are {self.name}. {self.persona}. {self.role_description} "
            "You are part of a two-agent collaboration workflow. "
            "Answer accurately, do not fabricate facts, and note uncertainty when needed."
        )

    def _recent_history(self, limit: int = 6) -> list[dict[str, str]]:
        if self.coordinator is None:
            return []

        history = self.coordinator.get_history()[-limit:]
        conversation: list[dict[str, str]] = []
        for item in history:
            role = "assistant"
            if item["sender"] == "User":
                role = "user"
            conversation.append(
                {
                    "role": role,
                    "content": f"{item['sender']} -> {item['receiver']}: {item['content']}",
                }
            )
        return conversation
