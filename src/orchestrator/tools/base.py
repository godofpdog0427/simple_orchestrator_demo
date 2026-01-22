"""Base classes for the tool system."""

import asyncio
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pydantic import BaseModel


class ToolParameter(BaseModel):
    """Tool parameter definition."""

    name: str
    type: str  # "string", "integer", "boolean", "object", "array"
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[list[Any]] = None  # Allowed values


class ToolDefinition(BaseModel):
    """Tool metadata and configuration."""

    name: str
    description: str
    parameters: list[ToolParameter]
    requires_approval: bool = False
    timeout_seconds: int = 60
    category: Optional[str] = None


@dataclass
class ToolResult:
    """Result from tool execution."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class Tool(ABC):
    """Base tool interface."""

    definition: ToolDefinition

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the tool.

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution result
        """
        pass

    def validate_params(self, **kwargs: Any) -> bool:
        """
        Validate tool parameters.

        Args:
            **kwargs: Parameters to validate

        Returns:
            bool: True if valid
        """
        # TODO: Implement parameter validation
        return True


def _python_type_to_json_type(annotation: Any) -> str:
    """Convert Python type annotation to JSON schema type."""
    if annotation == str:
        return "string"
    elif annotation == int:
        return "integer"
    elif annotation == float:
        return "number"
    elif annotation == bool:
        return "boolean"
    elif annotation == list or getattr(annotation, "__origin__", None) == list:
        return "array"
    elif annotation == dict or getattr(annotation, "__origin__", None) == dict:
        return "object"
    else:
        return "string"


def _extract_param_doc(func: Callable[..., Any], param_name: str) -> str:
    """Extract parameter description from function docstring."""
    # TODO: Parse docstring for parameter descriptions
    return f"Parameter: {param_name}"


def tool(
    name: str,
    requires_approval: bool = False,
    timeout_seconds: int = 60,
    category: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Tool]:
    """
    Decorator to convert a function into a Tool.

    Args:
        name: Tool name
        requires_approval: Whether tool requires human approval
        timeout_seconds: Execution timeout
        category: Tool category for grouping

    Returns:
        Decorated function as Tool
    """

    def decorator(func: Callable[..., Any]) -> Tool:
        # Extract parameters from function signature
        sig = inspect.signature(func)
        params = []

        for param_name, param in sig.parameters.items():
            params.append(
                ToolParameter(
                    name=param_name,
                    type=_python_type_to_json_type(param.annotation),
                    description=_extract_param_doc(func, param_name),
                    required=param.default is inspect.Parameter.empty,
                    default=None if param.default is inspect.Parameter.empty else param.default,
                )
            )

        # Create Tool wrapper
        class FunctionTool(Tool):
            definition = ToolDefinition(
                name=name,
                description=func.__doc__.split("\n")[0] if func.__doc__ else "",
                parameters=params,
                requires_approval=requires_approval,
                timeout_seconds=timeout_seconds,
                category=category,
            )

            async def execute(self, **kwargs: Any) -> ToolResult:
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(**kwargs)
                    else:
                        result = func(**kwargs)
                    return ToolResult(success=True, data=result)
                except Exception as e:
                    return ToolResult(success=False, error=str(e))

        return FunctionTool()

    return decorator
