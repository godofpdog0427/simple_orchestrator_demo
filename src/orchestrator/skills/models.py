"""Skill models and metadata parsing."""

import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class SkillMetadata(BaseModel):
    """
    Metadata extracted from SKILL.md frontmatter.

    Example frontmatter:
    ---
    name: code_edit
    description: "Edit existing code files with proper validation"
    tools_required: [file_read, file_write]
    tags: [coding, refactoring, editing]
    version: "1.0.0"
    priority: medium
    ---
    """

    name: str = Field(..., description="Unique skill identifier")
    description: str = Field(..., description="Brief skill description")
    tools_required: list[str] = Field(
        default_factory=list, description="List of required tool names"
    )
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    version: str = Field(default="1.0.0", description="Skill version")
    priority: str = Field(
        default="medium", description="Skill priority: low, medium, high"
    )

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """Validate priority value."""
        valid = ["low", "medium", "high"]
        if v.lower() not in valid:
            raise ValueError(f"Priority must be one of {valid}, got: {v}")
        return v.lower()


class Skill(BaseModel):
    """
    Complete skill definition including metadata and content.

    Attributes:
        metadata: Parsed frontmatter metadata
        content: Markdown content after frontmatter
        file_path: Path to SKILL.md file
    """

    metadata: SkillMetadata
    content: str = Field(..., description="Markdown skill instructions")
    file_path: Path = Field(..., description="Path to skill file")

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

    def __str__(self) -> str:
        """String representation."""
        return f"Skill({self.metadata.name})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"Skill(name={self.metadata.name!r}, "
            f"tools={self.metadata.tools_required}, "
            f"tags={self.metadata.tags})"
        )


def parse_skill_file(file_path: Path) -> Skill:
    """
    Parse SKILL.md file and extract metadata + content.

    Args:
        file_path: Path to SKILL.md file

    Returns:
        Skill object with parsed metadata and content

    Raises:
        ValueError: If file format is invalid
        FileNotFoundError: If file doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Skill file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")

    # Parse frontmatter (YAML between --- delimiters)
    frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if not match:
        raise ValueError(
            f"Invalid skill file format: {file_path}. "
            "Expected YAML frontmatter between --- delimiters."
        )

    frontmatter_yaml = match.group(1)
    skill_content = match.group(2).strip()

    # Parse YAML metadata
    try:
        metadata_dict = yaml.safe_load(frontmatter_yaml)
        if not isinstance(metadata_dict, dict):
            raise ValueError("Frontmatter must be a YAML dict")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter in {file_path}: {e}") from e

    # Validate metadata
    try:
        metadata = SkillMetadata(**metadata_dict)
    except Exception as e:
        raise ValueError(f"Invalid skill metadata in {file_path}: {e}") from e

    return Skill(metadata=metadata, content=skill_content, file_path=file_path)


def create_skill_template(
    name: str,
    description: str,
    tools_required: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
) -> str:
    """
    Create a template SKILL.md file content.

    Args:
        name: Skill name
        description: Skill description
        tools_required: List of required tools
        tags: List of tags

    Returns:
        SKILL.md template content
    """
    tools = tools_required or []
    tag_list = tags or []

    template = f"""---
name: {name}
description: "{description}"
tools_required: {tools}
tags: {tag_list}
version: "1.0.0"
priority: medium
---

# {name.replace('_', ' ').title()}

## Overview
Describe what this skill does and when to use it.

## When to Use
- Use case 1
- Use case 2
- Use case 3

## Process

### 1. Step One
Describe the first step of the process.

### 2. Step Two
Describe the second step.

### 3. Step Three
Describe the third step.

## Best Practices

### ✅ Do
- Best practice 1
- Best practice 2

### ❌ Don't
- Anti-pattern 1
- Anti-pattern 2

## Example Workflow

```
1. Tool invocation example
2. Next step
3. Final step
```

## Notes
Additional notes and considerations.
"""

    return template
