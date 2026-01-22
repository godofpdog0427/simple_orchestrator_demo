## Architecture Deep Dive

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                           │
│  (click commands, interactive prompt, config loading)       │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Orchestrator Core                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Hook Engine │  │ Task Manager │  │ LLM Client   │      │
│  │ (lifecycle) │  │ (queue/deps) │  │ (Anthropic)  │      │
│  └─────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │Tool Registry│  │Skill Registry│  │Subagent Mgr  │      │
│  │(bash, file) │  │(SKILL.md)    │  │(spawning)    │      │
│  └─────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 1. LLM Integration (Anthropic)

**CRITICAL**: This orchestrator uses Anthropic's **native tool calling API**. Do NOT use text-based tool parsing.

#### Correct Tool Calling Flow

1. **Tool Registration**: Tools converted to Anthropic schema
   ```python
   {
       "name": "bash",
       "description": "Execute bash commands",
       "input_schema": {
           "type": "object",
           "properties": {
               "command": {"type": "string", "description": "..."}
           },
           "required": ["command"]
       }
   }
   ```

2. **API Call**: Tools passed via `tools` parameter
   ```python
   response = await client.messages.create(
       model="claude-3-5-sonnet-20241022",
       messages=conversation_history,
       tools=tool_schemas  # List of tool definitions
   )
   ```

3. **Response Handling**: Parse `stop_reason`
   - `stop_reason == "end_turn"`: Extract text content
   - `stop_reason == "tool_use"`: Process `tool_use` blocks

4. **Tool Execution**: Execute tools and return results
   ```python
   tool_results = []
   for block in response.content:
       if block.type == "tool_use":
           result = await execute_tool(block.name, block.input)
           tool_results.append({
               "type": "tool_result",
               "tool_use_id": block.id,  # CRITICAL: Match ID
               "content": str(result)
           })

   # Add as user message
   conversation_history.append({
       "role": "user",
       "content": tool_results
   })
   ```

#### Key Files

- `src/orchestrator/llm/client.py` - LLM abstraction layer
- `src/orchestrator/llm/providers/anthropic.py` - Anthropic provider (future)
- `src/orchestrator/core/orchestrator.py:_reasoning_loop()` - Main ReAct loop

#### Provider Abstraction (Future)

Currently only Anthropic is supported. Future providers:
- OpenAI (GPT-4)
- Google (Gemini)
- Local models (Ollama)

Each provider will implement `LLMProvider` ABC with standardized `chat()` interface.

### 2. Hook System

**Status**: Base classes implemented (Phase 1), engine not active yet (Phase 2).

#### Hook Lifecycle Events

| Event | When Triggered | Context Provided |
|-------|---------------|------------------|
| `orchestrator.start` | Orchestrator initialization | config |
| `orchestrator.stop` | Orchestrator shutdown | final_state |
| `task.created` | Task added to queue | task |
| `task.started` | Task execution begins | task, agent_context |
| `task.completed` | Task succeeds | task, result |
| `task.failed` | Task fails | task, error |
| `tool.before_execute` | Before tool runs | tool_name, input |
| `tool.after_execute` | After tool runs | tool_name, result |
| `tool.requires_approval` | Tool needs HITL | tool_name, input |
| `subagent.spawned` | Subagent created | parent_task, child_task |
| `subagent.completed` | Subagent finishes | parent_task, result |
| `llm.before_call` | Before LLM API call | messages, tools |
| `llm.after_call` | After LLM response | response, token_count |

#### Hook Priority

Hooks execute in priority order (lower number = higher priority):

```yaml
hooks:
  - name: logging_hook
    priority: 10
    events: ["*"]  # All events

  - name: hitl_approval
    priority: 50
    events: ["tool.requires_approval"]

  - name: metrics_collector
    priority: 100
    events: ["task.completed", "task.failed"]
```

#### Hook Results

Hooks can:
- **Continue**: `HookResult(action="continue")`
- **Block**: `HookResult(action="block", reason="...")`
- **Modify**: `HookResult(action="continue", modified_context={...})`

#### Built-in Hooks (Phase 2)

1. **LoggingHook**: Logs all events to file
2. **HITLHook**: Prompts user for approval on critical operations
3. **MetricsHook**: Collects execution statistics
4. **CachingHook**: Caches tool results for deduplication

#### Custom Hook Example

```python
from orchestrator.hooks.base import Hook, HookContext, HookResult

class CustomValidationHook(Hook):
    name = "custom_validation"
    priority = 20
    events = ["task.started"]

    async def execute(self, context: HookContext) -> HookResult:
        task = context.data["task"]
        if not task.description:
            return HookResult(
                action="block",
                reason="Task must have description"
            )
        return HookResult(action="continue")
```

### 3. Task System

#### Task Model

```python
@dataclass
class Task:
    id: str
    title: str
    description: str
    status: TaskStatus  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    priority: TaskPriority  # LOW, NORMAL, HIGH, CRITICAL

    # Hierarchy (Phase 3)
    parent_id: Optional[str] = None
    subtasks: list[str] = field(default_factory=list)

    # Dependencies (Phase 3)
    depends_on: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)

    # Execution
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

#### Task Lifecycle

```
PENDING → IN_PROGRESS → COMPLETED
                     ↘ FAILED

If retry enabled: FAILED → PENDING (up to max_retries)
```

#### Phase 1: Simple Queue

- Tasks execute sequentially
- No hierarchy or dependencies
- `get_next_executable_task()` returns first PENDING task

#### Phase 3: Hierarchical Tasks

- Parent tasks spawn subtasks
- Subtasks execute before parent completes
- `get_next_executable_task()` respects:
  - Dependencies: All tasks in `depends_on` must be COMPLETED
  - Hierarchy: Subtasks execute before parent

#### Task Manager API

```python
class TaskManager:
    async def create_task(self, title: str, description: str, **kwargs) -> Task
    async def get_task(self, task_id: str) -> Optional[Task]
    async def update_task(self, task_id: str, **updates) -> Task
    async def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]
    async def get_next_executable_task(self) -> Optional[Task]

    # Hierarchy (Phase 3)
    async def create_subtask(self, parent_id: str, **kwargs) -> Task
    async def add_dependency(self, task_id: str, depends_on_id: str)
```

### 4. Tool System

#### Tool Registration Methods

##### 1. Class-Based (Complex Tools)

```python
from orchestrator.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

class DatabaseQueryTool(Tool):
    definition = ToolDefinition(
        name="database_query",
        description="Execute SQL query on database",
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="SQL query to execute",
                required=True
            ),
            ToolParameter(
                name="db_name",
                type="string",
                description="Database name",
                required=False,
                default="default"
            )
        ],
        requires_approval=True  # HITL for destructive queries
    )

    def __init__(self, connection_pool):
        self.pool = connection_pool

    async def execute(self, query: str, db_name: str = "default") -> ToolResult:
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetch(query)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

##### 2. Decorator-Based (Simple Functions)

```python
from orchestrator.tools.base import tool

@tool(name="word_count", requires_approval=False)
async def word_count(text: str) -> int:
    """Count words in the given text."""
    return len(text.split())

@tool(name="sentiment_analysis")
async def analyze_sentiment(text: str) -> dict:
    """Analyze sentiment of text."""
    # Tool implementation
    return {"sentiment": "positive", "score": 0.85}
```

##### 3. YAML-Based (User Extensions)

```yaml
# user_extensions/tools/custom.yaml
tools:
  - name: fetch_weather
    description: Fetch current weather for a location
    type: http_request
    parameters:
      - name: location
        type: string
        required: true
    config:
      method: GET
      url: "https://api.weather.com/v1/current?location={location}"
      headers:
        API-Key: "${WEATHER_API_KEY}"
    requires_approval: false
```

#### Built-in Tools

1. **BashTool**: Execute shell commands
   - Safety: Blocked command patterns (rm -rf /, fork bombs)
   - Timeout: Configurable (default 30s)
   - Working directory tracking

2. **FileReadTool**: Read file contents
   - Size limit: Configurable (default 10MB)
   - Encoding: UTF-8 with fallback

3. **FileWriteTool**: Write/create files
   - Auto-create parent directories
   - Atomic writes (temp file + rename)

4. **FileDeleteTool**: Delete files/directories
   - Requires approval for directories
   - Safety checks (no system paths)

#### Tool Registry

```python
class ToolRegistry:
    def register(self, tool: Tool)
    def get(self, name: str) -> Optional[Tool]
    def list_tools(self) -> list[ToolDefinition]
    def to_anthropic_schema(self) -> list[dict]  # Convert to API format
```

#### Anthropic Schema Conversion

```python
def _convert_to_anthropic_schema(self, tool_def: ToolDefinition) -> dict:
    properties = {}
    required = []

    for param in tool_def.parameters:
        properties[param.name] = {
            "type": param.type,
            "description": param.description
        }
        if param.required:
            required.append(param.name)

    return {
        "name": tool_def.name,
        "description": tool_def.description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }
```

### 5. Skill System

#### Design Philosophy

**Skills are prompts, not code.** A SKILL.md file contains:
- **Instructions**: How to approach a task
- **Best practices**: Domain-specific guidelines
- **Examples**: Template usage patterns
- **Safety checks**: Common pitfalls to avoid

The LLM reads the skill and uses available tools to achieve the goal.

#### SKILL.md Format

```markdown
---
name: code_review
description: "Review code for bugs, style, and security issues"
tools_required: [file_read]
version: "1.0.0"
tags: [code, quality, security]
---

# Code Review

## Overview
Systematic code review focusing on correctness, security, style, and maintainability.

## When to Use
- Pull request review
- Security audit
- Code quality assessment

## Review Checklist

### 1. Correctness
- [ ] Logic errors or edge cases
- [ ] Null/undefined handling
- [ ] Type mismatches

### 2. Security
- [ ] SQL injection vulnerabilities
- [ ] XSS vulnerabilities
- [ ] Authentication checks

## Process
1. Read all changed files
2. Check each item in checklist
3. Document findings with severity levels
4. Suggest specific fixes

## Example Output
**File**: `auth.py:42`
**Severity**: High
**Issue**: Missing authentication check
**Fix**: Add `@require_auth` decorator
```

#### Built-in Skills

1. **code_edit**: Safe code modification patterns
2. **code_review**: Code quality assessment
3. **research**: Web research methodology
4. **git_operations**: Git workflow best practices
5. **file_management**: File organization patterns

#### Skill Auto-Discovery (Phase 4)

```python
class SkillRegistry:
    def __init__(self):
        self._skills = {}
        self._load_builtin_skills()
        self._load_user_skills()

    def _load_user_skills(self):
        """Auto-discover skills from user_extensions/skills/*/SKILL.md"""
        for skill_dir in Path("user_extensions/skills").glob("*/"):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skill = self._parse_skill(skill_file)
                self.register(skill)
```

#### Using Skills in Tasks

```python
# User creates task with skill hint
orchestrator task add "Review auth.py for security issues" --skill code_review

# Orchestrator injects skill instructions into system prompt
system_prompt = f"""
You are an AI assistant with access to tools.

Active Skill: Code Review
{skill_content}

Task: Review auth.py for security issues
"""
```

### 6. Subagent System (Phase 4)

#### Purpose

Delegate complex subtasks to isolated child agents with:
- Limited context (only parent task info)
- Resource constraints (token budget, time limit)
- Restricted tool access

#### Spawning Subagents

```python
class SubagentManager:
    async def spawn(
        self,
        parent_task: Task,
        subtask: Task,
        context: dict,
        constraints: dict
    ) -> SubagentHandle:
        """
        Spawn isolated subagent for subtask execution.

        Constraints:
            max_tokens: 50000 (default)
            timeout_seconds: 300 (default)
            allowed_tools: ["bash", "file_read"] (default: all)
            skill: Optional skill to load
        """
        subagent = Orchestrator(
            llm_client=self.llm_client,
            config={
                "max_tokens": constraints.get("max_tokens", 50000),
                "allowed_tools": constraints.get("allowed_tools")
            }
        )

        # Execute subtask in isolation
        result = await asyncio.wait_for(
            subagent.execute_task(subtask, context),
            timeout=constraints.get("timeout_seconds", 300)
        )

        return SubagentHandle(task_id=subtask.id, result=result)
```

#### Communication Rules

- **Parent → Child**: Only through task context (no direct calls)
- **Child → Parent**: Only through task result
- **Child ↔ Child**: No communication (isolated)

#### Resource Limits

```yaml
subagents:
  max_concurrent: 3  # Maximum parallel subagents
  default_constraints:
    max_tokens: 50000
    timeout_seconds: 300
    allowed_tools: ["bash", "file_read", "file_write"]
```

### 7. Human-in-the-Loop (HITL) (Phase 2)

#### Approval Workflow

1. Tool requires approval (`requires_approval=True`)
2. Hook `tool.requires_approval` triggered
3. HITL hook prompts user:
   ```
   Tool 'bash' requires approval:
   Command: rm -rf old_logs/

   Approve? [y/N]:
   ```
4. User response:
   - `y`: Execution continues
   - `n`: Execution blocked, alternative sought

#### Approval Levels

```yaml
hitl:
  approval_required:
    - tool_name: bash
      conditions:
        - pattern: "rm -rf.*"
        - pattern: "sudo.*"

    - tool_name: file_delete
      conditions:
        - target_is_directory: true

    - tool_name: database_query
      conditions:
        - query_type: ["DELETE", "DROP", "TRUNCATE"]
```

#### Auto-Approval (Advanced)

```python
class SmartHITLHook(Hook):
    async def execute(self, context: HookContext) -> HookResult:
        tool_name = context.data["tool_name"]
        tool_input = context.data["input"]

        # Check whitelist
        if self._is_whitelisted(tool_name, tool_input):
            return HookResult(action="continue")

        # Prompt user
        approved = await self._prompt_user(tool_name, tool_input)

        if approved:
            # Add to whitelist for future
            self._add_to_whitelist(tool_name, tool_input)
            return HookResult(action="continue")
        else:
            return HookResult(action="block", reason="User denied approval")
```

### 8. Configuration System

#### Configuration Files

```
config/
├── default.yaml       # Default configuration
├── hooks.yaml         # Hook definitions
├── schema.json        # JSON schema for validation
└── local.yaml         # Local overrides (gitignored)
```

#### Complete Configuration Schema

```yaml
# config/default.yaml

# LLM Provider Settings
llm:
  provider: anthropic  # anthropic, openai, google, local

  anthropic:
    model: claude-3-5-sonnet-20241022
    api_key_env: ANTHROPIC_API_KEY  # Read from env var
    max_tokens: 8192
    temperature: 0.7

  openai:  # Future
    model: gpt-4-turbo
    api_key_env: OPENAI_API_KEY

# Tool Configuration
tools:
  # Built-in tools
  bash:
    enabled: true
    timeout: 30
    blocked_commands:
      - "rm -rf /"
      - ":(){ :|:& };:"  # Fork bomb
      - "> /dev/sda"

  file_read:
    enabled: true
    max_file_size: 10485760  # 10 MB

  file_write:
    enabled: true
    create_dirs: true

  file_delete:
    enabled: true
    requires_approval: true

# Task Management
tasks:
  max_retries: 3
  retry_delay: 5  # seconds
  persistence_file: .orchestrator/tasks.json

# Subagent Settings (Phase 4)
subagents:
  enabled: false
  max_concurrent: 3
  default_constraints:
    max_tokens: 50000
    timeout_seconds: 300
    allowed_tools: ["bash", "file_read", "file_write"]

# Hook Settings (Phase 2)
hooks:
  enabled: false
  config_file: config/hooks.yaml

# HITL Settings (Phase 2)
hitl:
  enabled: false
  auto_approve_safe_tools: true
  approval_timeout: 300  # seconds

# Skill Settings
skills:
  builtin_path: src/orchestrator/skills/builtin
  user_path: user_extensions/skills
  auto_discover: true

# Memory Settings (Phase 5)
memory:
  enabled: false
  cross_session: false
  embeddings_provider: local  # local, openai
  vector_store: chroma

# Caching Settings (Phase 5)
cache:
  enabled: false
  tool_results: true
  llm_responses: false
  ttl: 3600  # seconds

# Logging
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  file: .orchestrator/orchestrator.log
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Persistence
persistence:
  state_file: .orchestrator/state.json
  auto_save: true
  save_interval: 60  # seconds
```

#### Hook Configuration

```yaml
# config/hooks.yaml

hooks:
  - name: logging_hook
    type: builtin  # builtin, custom, external
    priority: 10
    enabled: true
    events: ["*"]
    config:
      log_file: .orchestrator/hooks.log

  - name: hitl_approval
    type: builtin
    priority: 50
    enabled: true
    events: ["tool.requires_approval"]
    config:
      timeout: 300
      auto_approve_patterns:
        - tool: bash
          command_regex: "^ls.*"
        - tool: bash
          command_regex: "^cat (?!.*\\.env).*"  # cat anything except .env

  - name: metrics_collector
    type: builtin
    priority: 100
    enabled: true
    events:
      - task.completed
      - task.failed
      - tool.after_execute
    config:
      output_file: .orchestrator/metrics.json

  - name: custom_validator
    type: custom
    priority: 20
    enabled: true
    events: ["task.started"]
    module: user_extensions.hooks.validator
    class: CustomValidationHook
```

### 9. Error Handling & Retry

#### Three-Level Retry Configuration

```yaml
# Global defaults (lowest priority)
retry:
  max_retries: 3
  retry_delay: 5
  backoff_multiplier: 2.0  # Exponential backoff

# Tool-level overrides (medium priority)
tools:
  bash:
    max_retries: 2  # Less retries for bash

  file_read:
    max_retries: 5  # More retries for file ops

# Task-level overrides (highest priority)
# Set programmatically:
task = await task_manager.create_task(
    title="Critical sync",
    description="...",
    max_retries=10
)
```

#### Retry Logic

```python
async def execute_with_retry(
    self,
    task: Task,
    context: dict
) -> Any:
    max_retries = task.max_retries or self.config["retry"]["max_retries"]
    delay = self.config["retry"]["retry_delay"]
    multiplier = self.config["retry"]["backoff_multiplier"]

    for attempt in range(max_retries + 1):
        try:
            result = await self._reasoning_loop(task, context)
            return result
        except RetryableError as e:
            if attempt == max_retries:
                raise

            wait_time = delay * (multiplier ** attempt)
            logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
            await asyncio.sleep(wait_time)
        except FatalError:
            raise  # Don't retry fatal errors
```

#### Error Types

```python
class OrchestratorError(Exception):
    """Base error"""

class RetryableError(OrchestratorError):
    """Errors that can be retried (API timeouts, rate limits)"""

class FatalError(OrchestratorError):
    """Errors that should not be retried (invalid input, auth failures)"""

class ToolExecutionError(RetryableError):
    """Tool failed but may succeed on retry"""

class TaskValidationError(FatalError):
    """Task is invalid and cannot be executed"""
```

---

