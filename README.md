# Simple Orchestrator

A lightweight CLI Agent Orchestrator for AI coding assistants with hook-based extensibility, hierarchical task management, and human-in-the-loop control.

## Features

- 🤖 **LLM Integration** - Anthropic Claude with native tool calling
- 🛠️ **Extensible Tools** - Bash, file operations, and custom tools
- 📋 **Task Management** - Queue-based task execution
- 📚 **Skill System** - Prompt-based skill instructions
- 🎣 **Hook System** - Customizable lifecycle hooks (Phase 2)
- ✋ **HITL Support** - Human approval for critical operations (Phase 2)

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/godofpdog/simple_orchestrator.git
cd simple_orchestrator

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install
pip install -e ".[dev]"
```

### Setup

```bash
# Create .env file
cp .env.example .env

# Edit .env and add your API key
# ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### Usage

```bash
# Interactive mode
orchestrator chat

# Single task
orchestrator task add "Analyze this code and suggest improvements"
```

## Architecture

```
CLI → Orchestrator → [LLM Client, Tool Registry, Task Manager]
                   ↓
            [Bash, File Ops, Custom Tools]
```

## Phase 1 Status ✅

Current implementation includes:
- CLI with interactive mode
- Anthropic Claude integration
- Basic task management
- Built-in tools (bash, file_read, file_write, file_delete)
- 5 built-in skills (code_edit, code_review, research, git_operations, file_management)

## Documentation

- `CLAUDE.md` - Developer guide for Claude Code
- `config/default.yaml` - Configuration reference
- `src/orchestrator/skills/builtin/` - Built-in skill examples

## License

MIT
