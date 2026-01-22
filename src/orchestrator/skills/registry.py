"""Skill registry for auto-discovery and management."""

import logging
from pathlib import Path
from typing import Optional

from orchestrator.skills.models import Skill, parse_skill_file

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Registry for skill discovery, indexing, and retrieval.

    Automatically discovers SKILL.md files in configured directories
    and provides search/filtering capabilities.
    """

    def __init__(self, config: dict) -> None:
        """
        Initialize skill registry.

        Args:
            config: Skill configuration with paths and settings
        """
        self.config = config
        self.skills: dict[str, Skill] = {}
        self._tag_index: dict[str, list[str]] = {}  # tag -> [skill_names]
        self._tool_index: dict[str, list[str]] = {}  # tool -> [skill_names]

    async def initialize(self) -> None:
        """Initialize and discover skills."""
        logger.info("Initializing skill registry...")

        if not self.config.get("enabled", True):
            logger.info("Skill system disabled")
            return

        # Discover skills from configured paths
        if self.config.get("auto_discover", True):
            await self._discover_all_skills()

        logger.info(f"Skill registry initialized with {len(self.skills)} skills")

    async def _discover_all_skills(self) -> None:
        """Discover skills from all configured directories."""
        # Built-in skills
        builtin_path = self.config.get(
            "builtin_path", "src/orchestrator/skills/builtin"
        )
        await self._discover_skills_in_directory(Path(builtin_path))

        # User skills
        user_path = self.config.get("user_path", "user_extensions/skills")
        if Path(user_path).exists():
            await self._discover_skills_in_directory(Path(user_path))

    async def _discover_skills_in_directory(self, directory: Path) -> None:
        """
        Discover skills in a directory.

        Searches for SKILL.md files in:
        - directory/SKILL.md
        - directory/*/SKILL.md (subdirectories)

        Args:
            directory: Directory to search
        """
        if not directory.exists():
            logger.warning(f"Skill directory does not exist: {directory}")
            return

        skill_files = []

        # Find all SKILL.md files
        skill_files.extend(directory.glob("SKILL.md"))
        skill_files.extend(directory.glob("*/SKILL.md"))

        for skill_file in skill_files:
            try:
                skill = parse_skill_file(skill_file)
                self.register(skill)
            except Exception as e:
                logger.error(f"Failed to load skill from {skill_file}: {e}")

    def register(self, skill: Skill) -> None:
        """
        Register a skill.

        Args:
            skill: Skill to register
        """
        skill_name = skill.metadata.name

        if skill_name in self.skills:
            logger.warning(f"Overwriting existing skill: {skill_name}")

        self.skills[skill_name] = skill

        # Update tag index
        for tag in skill.metadata.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if skill_name not in self._tag_index[tag]:
                self._tag_index[tag].append(skill_name)

        # Update tool index
        for tool in skill.metadata.tools_required:
            if tool not in self._tool_index:
                self._tool_index[tool] = []
            if skill_name not in self._tool_index[tool]:
                self._tool_index[tool].append(skill_name)

        logger.info(f"Registered skill: {skill_name}")

    def unregister(self, name: str) -> None:
        """
        Unregister a skill.

        Args:
            name: Skill name to unregister
        """
        if name not in self.skills:
            logger.warning(f"Skill not found: {name}")
            return

        skill = self.skills[name]

        # Remove from tag index
        for tag in skill.metadata.tags:
            if tag in self._tag_index:
                self._tag_index[tag] = [
                    s for s in self._tag_index[tag] if s != name
                ]

        # Remove from tool index
        for tool in skill.metadata.tools_required:
            if tool in self._tool_index:
                self._tool_index[tool] = [
                    s for s in self._tool_index[tool] if s != name
                ]

        del self.skills[name]
        logger.info(f"Unregistered skill: {name}")

    def get(self, name: str) -> Optional[Skill]:
        """
        Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill or None if not found
        """
        return self.skills.get(name)

    def list_all(self) -> list[Skill]:
        """
        List all registered skills.

        Returns:
            List of skills sorted by name
        """
        return sorted(self.skills.values(), key=lambda s: s.metadata.name)

    def search_by_tags(self, tags: list[str]) -> list[Skill]:
        """
        Search skills by tags.

        Args:
            tags: List of tags to search for

        Returns:
            List of skills matching ANY of the tags
        """
        skill_names = set()
        for tag in tags:
            if tag in self._tag_index:
                skill_names.update(self._tag_index[tag])

        return [self.skills[name] for name in skill_names if name in self.skills]

    def search_by_tools(self, tools: list[str]) -> list[Skill]:
        """
        Search skills by required tools.

        Args:
            tools: List of tool names

        Returns:
            List of skills that require ANY of the tools
        """
        skill_names = set()
        for tool in tools:
            if tool in self._tool_index:
                skill_names.update(self._tool_index[tool])

        return [self.skills[name] for name in skill_names if name in self.skills]

    def search_by_keywords(self, keywords: list[str]) -> list[Skill]:
        """
        Search skills by keywords in name/description.

        Args:
            keywords: List of keywords to search

        Returns:
            List of skills matching ANY keyword
        """
        matches = []

        for skill in self.skills.values():
            text = f"{skill.metadata.name} {skill.metadata.description}".lower()

            for keyword in keywords:
                if keyword.lower() in text:
                    matches.append(skill)
                    break  # Avoid duplicates

        return matches

    def get_skills_for_task(
        self, task_description: str, available_tools: list[str]
    ) -> list[Skill]:
        """
        Get recommended skills for a task.

        Matches based on:
        1. Keywords in task description
        2. Available tools matching skill requirements

        Args:
            task_description: Task description
            available_tools: List of available tool names

        Returns:
            List of recommended skills, sorted by priority
        """
        # Extract potential keywords from task description
        words = task_description.lower().split()
        keywords = [w.strip(".,!?;:") for w in words if len(w) > 3]

        # Search by keywords
        keyword_matches = self.search_by_keywords(keywords)

        # Search by tools
        tool_matches = self.search_by_tools(available_tools)

        # Combine and deduplicate
        all_matches = {skill.metadata.name: skill for skill in keyword_matches}
        all_matches.update({skill.metadata.name: skill for skill in tool_matches})

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_skills = sorted(
            all_matches.values(),
            key=lambda s: priority_order.get(s.metadata.priority, 999),
        )

        return sorted_skills

    def get_statistics(self) -> dict:
        """
        Get registry statistics.

        Returns:
            Dictionary with registry stats
        """
        return {
            "total_skills": len(self.skills),
            "tags": len(self._tag_index),
            "tools_indexed": len(self._tool_index),
            "skills_by_priority": {
                "high": len([s for s in self.skills.values() if s.metadata.priority == "high"]),
                "medium": len([s for s in self.skills.values() if s.metadata.priority == "medium"]),
                "low": len([s for s in self.skills.values() if s.metadata.priority == "low"]),
            },
        }
