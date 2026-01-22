# CLAUDE.md

This file provides comprehensive guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Last Updated**: 2026-01-18
**Current Phase**: Phase 5B Complete → Phase 6 Planning

---

## ⚠️ CRITICAL: Git Branch Strategy

**READ THIS FIRST - MANDATORY RULES**

This project uses a strict branch strategy to prevent catastrophic data loss.

### Branch Structure

- **`main`** - Production-ready code. **PROTECTED BRANCH**
- **`dev`** - Development integration branch. **Default working branch**
- **`feature/*`** - Feature branches (created from `dev`)
- **`fix/*`** - Bug fix branches (created from `dev`)

### Branching Rules for Claude Code

**YOU MUST FOLLOW THESE RULES:**

1. **NEVER merge to `main`** - Only the human user can merge to `main`
2. **ALWAYS create feature branches from `dev`** - Never from `main`
3. **ALWAYS merge your changes to `dev`** - Never to `main`
4. **NEVER force push** - Especially not to `main` or `dev`
5. **ALWAYS work on feature branches** - Format: `feature/description` or `fix/description`

### Workflow for Claude Code

```bash
# 1. Start from dev branch
git checkout dev
git pull origin dev

# 2. Create feature branch
git checkout -b feature/your-feature-name

# 3. Make changes and commit
git add .
git commit -m "feat: your changes"

# 4. Push feature branch
git push -u origin feature/your-feature-name

# 5. Merge to dev (NEVER to main)
git checkout dev
git merge feature/your-feature-name
git push origin dev
```

### What You CAN Do

✅ Create feature branches from `dev`
✅ Commit to feature branches
✅ Merge feature branches to `dev`
✅ Push to `dev` branch
✅ Create pull requests (for review)

### What You CANNOT Do

❌ **Merge to `main`** (NEVER)
❌ **Force push to any branch**
❌ **Delete `main` or `dev` branches**
❌ **Create branches from `main`** (use `dev` instead)
❌ **Push directly to `main`**

### Emergency Recovery

If you accidentally work on the wrong branch:

```bash
# Save your work
git stash

# Switch to correct branch
git checkout dev
git checkout -b feature/your-feature

# Restore your work
git stash pop
```

**Full Git Workflow**: See [`docs/development/git-workflow.md`](docs/development/git-workflow.md)

---

## Project Overview

**Simple Orchestrator** is a lightweight CLI Agent Orchestrator designed for personal use with AI coding assistants. It provides a hook-based, extensible framework for managing complex multi-step tasks with LLM agents.

### Core Capabilities

- **Hook-based Lifecycle Management**: Intercept and customize behavior at key execution points
- **Hierarchical Task Management**: Break down complex tasks into subtasks with dependency tracking
- **Extensible Tool System**: Register custom tools via classes, decorators, or YAML configs
- **Subagent Spawning**: Delegate subtasks to specialized agents with resource constraints
- **Skill-based Instructions**: Prompt-based skills (SKILL.md files) guide LLM behavior
- **Workspace State**: Conversation memory enables continuity across tasks (Phase 5B)
- **Human-in-the-Loop (HITL)**: Approve critical operations before execution

### Technology Stack

- **Python 3.12** with asyncio for non-blocking execution
- **Anthropic Claude API** (native tool calling)
- **Rich** TUI library for terminal display
- **YAML** configuration with environment variable support

### Directory Structure

```
simple_orchestrator/
├── src/orchestrator/          # Core orchestrator code
│   ├── core/                  # Orchestrator, ReAct loop
│   ├── llm/                   # LLM client (Anthropic)
│   ├── tools/                 # Tool system
│   ├── tasks/                 # Task management
│   ├── hooks/                 # Hook engine
│   ├── skills/                # Skill registry
│   ├── subagents/             # Subagent manager
│   ├── workspace/             # Workspace state (Phase 5B)
│   └── cli/                   # CLI interface
├── tests/                     # Unit and integration tests
├── config/                    # Configuration files
├── docs/development/          # Detailed documentation
└── user_extensions/           # User-defined tools/hooks/skills
```

---

## Quick Start

### Setup

```bash
# Install dependencies
pip install -e ".[dev]"

# Create .env file
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Running

```bash
# Start orchestrator in interactive mode
orchestrator chat

# Test mode (isolated workspace)
orchestrator test

# Run with specific config
orchestrator start --config config/custom.yaml

# Add a task
orchestrator task add "Analyze code and suggest improvements"
```

### Development

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=orchestrator --cov-report=html

# Run integration tests only
pytest tests/integration/

# Linting and formatting
ruff check src/
black src/
mypy src/
```

---

## Core Architecture

### Design Principles

This orchestrator is built on proven AI agent design patterns:

1. **Async-First**: All I/O operations use `async/await` for non-blocking execution
2. **Hook-Driven Extensibility**: Every key action triggers lifecycle hooks
3. **Declarative Tools**: Tools describe capabilities; LLM decides usage
4. **Prompt-Based Skills**: Skills are instructions (SKILL.md), not code workflows
5. **Subagent Isolation**: Child agents have limited context and resource budgets
6. **Human Oversight**: Critical operations require explicit approval (HITL)

### Two-Layer State System (Phase 5B)

```
┌─────────────────────────────────────────────────────────┐
│                    Workspace Layer                      │
│  (Long-term context, retained across tasks)            │
│                                                          │
│  - workspace_conversation: list[Message]                │
│  - task_summaries: deque[TaskSummary] (max 10)         │
│  - user_preferences: dict                               │
│                                                          │
│  Persisted in: .orchestrator/workspace_state/{id}.json  │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                     Task Layer                          │
│  (Short-term execution context)                         │
│                                                          │
│  - conversation_history: list[dict]                     │
│  - Current task goal and tool results                   │
│                                                          │
│  Lifecycle: Created per task, cleaned after completion  │
└─────────────────────────────────────────────────────────┘
```

### Key Components

- **Orchestrator Core**: Main execution engine with ReAct loop
- **LLM Client**: Anthropic provider with native tool calling API
- **Tool Registry**: Manages builtin and custom tools
- **Hook Engine**: Lifecycle event management
- **Task Manager**: Hierarchical task queue with dependency resolution
- **Skill Registry**: Auto-discovers and injects SKILL.md files
- **Subagent Manager**: Spawns isolated child agents
- **Workspace Manager**: Persists conversation state (Phase 5B)

**Detailed Architecture**: See [`docs/development/architecture.md`](docs/development/architecture.md)

---

## Development Workflow

### Before Writing Code

1. **Read relevant documentation:**
   - **Architecture** → [`docs/development/architecture.md`](docs/development/architecture.md)
   - **Current phase status** → [`docs/development/implementation-status.md`](docs/development/implementation-status.md)
   - **How to add features** → [`docs/development/patterns.md`](docs/development/patterns.md)
   - **Git workflow** → [`docs/development/git-workflow.md`](docs/development/git-workflow.md)

2. **Check current phase status** in `implementation-status.md`

3. **Follow testing guidelines** in [`docs/development/testing.md`](docs/development/testing.md)

### When You Encounter Issues

- See [`docs/development/troubleshooting.md`](docs/development/troubleshooting.md)
- Check logs in `.orchestrator/logs/orchestrator.log`

### Adding New Features

**Before implementing:**
- Read relevant section in [`docs/development/patterns.md`](docs/development/patterns.md):
  - Adding a new tool
  - Creating a skill
  - Adding a custom hook
  - Using HITL for approval
  - Task decomposition
  - Spawning subagents

---

## Critical Rules (Always Apply)

### Code Changes

- ✅ **Read files before editing** - Never propose changes to code you haven't read
- ✅ **Write tests for new features** - Unit tests required
- ✅ **Update documentation if architecture changes** - Keep CLAUDE.md in sync
- ❌ **Never modify production data** - Use test environments
- ❌ **Never skip hooks** (--no-verify, --no-gpg-sign)
- ❌ **Never create files unless necessary** - Always prefer editing existing files

### Tool Usage

- Use specialized tools (Read/Edit/Write) instead of bash commands for file operations
- Use Task tool with Explore agent for complex searches
- Use TodoWrite tool to track multi-step tasks
- NEVER use bash echo/printf to communicate with user - output text directly

### Testing

- Unit tests required for all new features
- Integration tests for LLM-based features (when API key available)
- Manual E2E testing before merging to dev
- Run full test suite: `pytest --cov=orchestrator`

### Git Commits

- Follow conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Add co-author line: `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`
- Create commits only when requested by user
- NEVER use `git commit --amend` unless explicitly requested

---

## Current Implementation Status

### Completed Phases

- ✅ **Phase 1**: Core Foundation (Orchestrator loop, LLM client, basic tools)
- ✅ **Phase 2**: Hook System & HITL (Hook engine, approval workflow)
- ✅ **Phase 2.5**: TodoList Tool (Progress tracking hotfix)
- ✅ **Phase 2.6**: Rich CLI Display & Streaming Output (UX improvements)
- ✅ **Phase 2.7**: API Rate Limit Handling (Exponential backoff)
- ✅ **Phase 3**: Task Hierarchy & Dependencies (Topological sort, cycle detection)
- ✅ **Phase 3.5**: Workspace Isolation (Isolated working directory)
- ✅ **Phase 4A**: Skill Registry (Auto-discovery, tag-based matching)
- ✅ **Phase 4B**: Subagent System (Resource-constrained delegation)
- ✅ **Phase 5A**: Tool Result Caching (TTL-based, LRU eviction)
- ✅ **Phase 5B**: Workspace State & Memory (Conversation continuity, task summaries)

### Next Phase

**Phase 6**: Mode System (Ask/Plan/Execute modes with session management)

**Full Implementation Details**: See [`docs/development/implementation-status.md`](docs/development/implementation-status.md)

---

## Documentation Index

### Detailed Documentation (`docs/development/`)

- **[`architecture.md`](docs/development/architecture.md)** - Architecture deep dive, component design, LLM integration details
- **[`implementation-status.md`](docs/development/implementation-status.md)** - All phase implementation details and checklists
- **[`patterns.md`](docs/development/patterns.md)** - How to add tools, skills, hooks, subagents
- **[`troubleshooting.md`](docs/development/troubleshooting.md)** - Common issues and solutions (rate limits, API keys, tool errors)
- **[`testing.md`](docs/development/testing.md)** - Testing strategies, unit/integration test examples
- **[`git-workflow.md`](docs/development/git-workflow.md)** - Complete git workflow reference and emergency recovery
- **[`configuration.md`](docs/development/configuration.md)** - Full configuration schema and options

### Quick References

- **Anthropic API Docs**: https://docs.anthropic.com/
- **ReAct Paper**: https://arxiv.org/abs/2210.03629
- **BDI Architecture**: https://en.wikipedia.org/wiki/Belief-desire-intention_model
- **Project Issues**: https://github.com/godofpdog/simple_orchestrator/issues

---

## Configuration

Configuration is loaded from `config/default.yaml` with optional overrides in `config/local.yaml`.

### Key Configuration Sections

```yaml
llm:
  provider: anthropic
  anthropic:
    model: claude-sonnet-4-20250514
    max_tokens: 8192
    temperature: 0.7

workspace:  # Phase 5B
  enabled: true
  workspace_dir: ".orchestrator/workspace_state"
  max_task_summaries: 10

tools:
  bash:
    enabled: true
    requires_approval: true
    blocked_commands: ["rm -rf /", "mkfs", ...]

  file_read:
    enabled: true
    max_file_size_mb: 10

hooks:
  enabled: true
  directories: ["./user_extensions/hooks"]

skills:
  enabled: true
  builtin_path: "src/orchestrator/skills/builtin"
  user_path: "user_extensions/skills"

subagents:
  enabled: true
  max_concurrent: 3
  default_constraints:
    max_tokens: 50000
    timeout_seconds: 300

cache:  # Phase 5A
  enabled: true
  ttl: 3600
  max_entries: 1000
```

**Full Configuration Reference**: See [`docs/development/configuration.md`](docs/development/configuration.md)

---

## Common Tasks

### Run Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_tools.py

# With coverage
pytest --cov=orchestrator --cov-report=html

# Integration tests (requires API key)
export ANTHROPIC_API_KEY=sk-ant-xxx
pytest tests/integration/
```

### Check Code Quality

```bash
# Linting
ruff check src/

# Formatting
black src/

# Type checking
mypy src/
```

### Manage Workspace

```bash
# List all workspace sessions
orchestrator workspace list

# Delete specific workspace
orchestrator workspace delete <session-id>

# Purge old workspaces
orchestrator workspace purge --older-than 30
```

---

## Troubleshooting

### Rate Limit Errors (429)

**Symptom**: `HTTP/1.1 429 Too Many Requests`

**Solution**: Automatic retry with exponential backoff (Phase 2.7). Check your Anthropic usage tier at https://console.anthropic.com/settings/limits

### API Key Not Found

**Symptom**: `ANTHROPIC_API_KEY environment variable not set`

**Solution**:
1. Check `.env` file exists: `ls -la .env`
2. Verify key is set: `grep ANTHROPIC_API_KEY .env`
3. No quotes: `ANTHROPIC_API_KEY=sk-ant-xxx` (not `"sk-ant-xxx"`)
4. Restart shell or `source .venv/bin/activate`

### Tool Not Found

**Symptom**: `Tool 'my_tool' not found in registry`

**Solution**:
1. Check tool is registered: `orchestrator tool list`
2. Verify enabled in config: `tools.my_tool.enabled: true`
3. Check registration in `ToolRegistry._register_builtin_tools()`

**More Solutions**: See [`docs/development/troubleshooting.md`](docs/development/troubleshooting.md)

---

## License & Contributing

MIT License - see LICENSE file

**Contributing Guidelines**: See [`docs/development/git-workflow.md`](docs/development/git-workflow.md)

---

**Note**: This is the main entry point. For detailed information on specific topics, consult the documentation in `docs/development/`.
