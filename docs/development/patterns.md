## Important Patterns

### Adding a New Tool

#### Simple Function Tool

```python
# user_extensions/tools/my_tools.py

from orchestrator.tools.base import tool

@tool(name="count_lines", requires_approval=False)
async def count_lines(file_path: str) -> int:
    """Count lines in a file."""
    with open(file_path) as f:
        return len(f.readlines())
```

#### Class-Based Tool with State

```python
# user_extensions/tools/my_tools.py

from orchestrator.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

class GitStatusTool(Tool):
    definition = ToolDefinition(
        name="git_status",
        description="Get git repository status",
        parameters=[
            ToolParameter(
                name="repo_path",
                type="string",
                description="Path to git repository",
                required=False,
                default="."
            )
        ],
        requires_approval=False
    )

    async def execute(self, repo_path: str = ".") -> ToolResult:
        import subprocess
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            return ToolResult(success=True, data=result.stdout)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

# Register in user_extensions/__init__.py
from .tools.my_tools import GitStatusTool
def register_user_extensions(orchestrator):
    orchestrator.tool_registry.register(GitStatusTool())
```

### Creating a New Skill

```bash
# Create skill directory
mkdir -p user_extensions/skills/deployment

# Create SKILL.md
cat > user_extensions/skills/deployment/SKILL.md << 'EOF'
---
name: deployment
description: "Deploy applications to production safely"
tools_required: [bash, file_read]
version: "1.0.0"
tags: [devops, deployment, production]
---

# Deployment

## Overview
Safe deployment procedures for production environments.

## Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Database migrations prepared
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured

## Deployment Steps
1. Check current production status
2. Create backup
3. Run database migrations
4. Deploy new version
5. Verify deployment
6. Monitor for errors

## Rollback Procedure
If deployment fails:
1. Stop new version
2. Restore from backup
3. Roll back database migrations
4. Restart old version
5. Document failure for post-mortem
EOF
```

### Adding a Custom Hook

```python
# user_extensions/hooks/custom_hooks.py

from orchestrator.hooks.base import Hook, HookContext, HookResult

class SlackNotificationHook(Hook):
    name = "slack_notification"
    priority = 90
    events = ["task.completed", "task.failed"]

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def execute(self, context: HookContext) -> HookResult:
        import httpx

        task = context.data["task"]
        event = context.event

        message = {
            "text": f"Task {task.title} {event.split('.')[1]}",
            "attachments": [{
                "color": "good" if event == "task.completed" else "danger",
                "fields": [
                    {"title": "Task ID", "value": task.id, "short": True},
                    {"title": "Status", "value": task.status.value, "short": True}
                ]
            }]
        }

        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json=message)

        return HookResult(action="continue")

# Register in config/hooks.yaml
hooks:
  - name: slack_notification
    type: custom
    priority: 90
    enabled: true
    events: ["task.completed", "task.failed"]
    module: user_extensions.hooks.custom_hooks
    class: SlackNotificationHook
    config:
      webhook_url: "${SLACK_WEBHOOK_URL}"
```

### Using HITL for Critical Operations

```python
# Mark tool as requiring approval
class DestructiveTool(Tool):
    definition = ToolDefinition(
        name="delete_database",
        description="Permanently delete a database",
        parameters=[...],
        requires_approval=True  # <-- Triggers HITL
    )

    async def execute(self, db_name: str) -> ToolResult:
        # This will only execute after user approval
        ...
```

### Task Decomposition (Phase 3)

```python
# User creates high-level task
await task_manager.create_task(
    title="Migrate database to PostgreSQL",
    description="Migrate from MySQL to PostgreSQL"
)

# LLM decomposes into subtasks:
subtasks = [
    "Export MySQL schema",
    "Convert schema to PostgreSQL syntax",
    "Export MySQL data",
    "Transform data for PostgreSQL",
    "Import schema to PostgreSQL",
    "Import data to PostgreSQL",
    "Verify data integrity",
    "Update application configuration"
]

for i, subtask_title in enumerate(subtasks):
    await task_manager.create_subtask(
        parent_id=parent_task.id,
        title=subtask_title,
        depends_on=[subtasks[i-1].id] if i > 0 else []
    )
```

### Spawning a Subagent (Phase 4)

```python
# Parent task delegates to subagent
parent_task = await task_manager.get_task(task_id)

subtask = await task_manager.create_task(
    title="Research best PostgreSQL migration tools",
    description="Find and compare tools for MySQL to PostgreSQL migration"
)

subagent_handle = await subagent_manager.spawn(
    parent_task=parent_task,
    subtask=subtask,
    context={"domain": "database migration"},
    constraints={
        "max_tokens": 30000,
        "timeout_seconds": 180,
        "allowed_tools": ["web_fetch", "file_read"],
        "skill": "research"
    }
)

result = await subagent_handle.wait()
```

---

