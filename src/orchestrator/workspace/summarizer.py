"""Task summarizer for generating concise LLM-based summaries."""

import logging
from typing import Any

from orchestrator.tasks.models import Task

logger = logging.getLogger(__name__)


class TaskSummarizer:
    """Generates task summaries using LLM."""

    def __init__(self, llm_client: Any):
        self.llm_client = llm_client

    async def generate_summary(
        self, task: Task, task_conversation: list[dict]
    ) -> str:
        """
        Generate 2-3 sentence summary of task execution.

        Args:
            task: The completed task
            task_conversation: List of conversation messages from reasoning loop

        Returns:
            Concise summary string
        """
        # Extract key information
        tools_used = self._extract_tools_used(task_conversation)
        reasoning_text = self._extract_reasoning(task_conversation)

        # Build summary prompt
        summary_prompt = f"""Summarize this task execution in 2-3 sentences.
Focus on what was accomplished, key decisions, and results.

Task: {task.description}
Status: {task.status.value}
Tools Used: {', '.join(tools_used) if tools_used else 'None'}

Reasoning:
{reasoning_text[:1000]}

Summary:"""

        try:
            # Call LLM with short response
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=200,
                temperature=0.3,  # More deterministic
            )

            summary = response.strip()
            logger.debug(f"Generated summary for task {task.id}: {summary}")
            return summary

        except Exception as e:
            logger.error(f"Error generating summary for task {task.id}: {e}")
            # Fallback: Return truncated task description
            return f"{task.description[:100]}... (Status: {task.status.value})"

    def _extract_tools_used(self, conversation: list[dict]) -> list[str]:
        """Extract list of tools used during task execution."""
        tools = set()
        for msg in conversation:
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tools.add(block.get("name", "unknown"))
        return list(tools)

    def _extract_reasoning(self, conversation: list[dict]) -> str:
        """Extract text reasoning blocks from conversation."""
        reasoning = []
        for msg in conversation:
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            reasoning.append(block.get("text", ""))
                elif isinstance(content, str):
                    reasoning.append(content)
        return "\n".join(reasoning)
