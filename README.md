# Simple Orchestrator

A lightweight CLI Agent Orchestrator for AI coding assistants. Built with Python, featuring hook-based extensibility, hierarchical task management, and human-in-the-loop control.

## Features

- **LLM Integration** - Anthropic Claude (direct API & Azure) with native tool calling
- **Extensible Tools** - Bash, file operations, web fetch, and custom tools
- **Hierarchical Tasks** - Task decomposition with dependency management
- **Skill System** - Auto-discovery of prompt-based skill instructions
- **Hook System** - Customizable lifecycle hooks for extensibility
- **HITL Support** - Human approval for critical operations
- **Workspace State** - Conversation memory across tasks
- **Streaming Display** - Real-time output with activity indicators

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/godofpdog0427/simple_orchestrator_demo.git
cd simple_orchestrator_demo

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Configuration

```bash
# Create environment file
cp .env.example .env

# Edit .env and add your API key
# For direct Anthropic API:
#   ANTHROPIC_API_KEY=sk-ant-xxxxx
#
# For Azure Anthropic:
#   AZURE_ANTHROPIC_API_KEY=your_azure_key
```

**Provider Configuration** (`config/default.yaml`):

```yaml
llm:
  provider: "anthropic"  # or "azure_anthropic"

  anthropic:
    model: "claude-sonnet-4-20250514"

  azure_anthropic:
    endpoint: "https://your-endpoint.azure.com/anthropic/"
    deployment_name: "claude-sonnet-4-5"
```

### Usage

```bash
# Interactive chat mode
orchestrator chat

# Test mode (isolated workspace)
orchestrator test

# Add a task
orchestrator task add "Analyze this code and suggest improvements"

# List skills
orchestrator skill list
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                           │
│  (click commands, interactive prompt, streaming display)    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Orchestrator Core                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Hook Engine │  │ Task Manager │  │ LLM Client   │       │
│  │ (lifecycle) │  │ (hierarchy)  │  │ (Anthropic)  │       │
│  └─────────────┘  └──────────────┘  └──────────────┘       │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │Tool Registry│  │Skill Registry│  │  Workspace   │       │
│  │  (bash,..) │  │ (SKILL.md)   │  │   (state)    │       │
│  └─────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `bash` | Execute shell commands (with approval) |
| `file_read` | Read file contents |
| `file_write` | Write/create files |
| `file_delete` | Delete files |
| `todo_list` | Track task progress |
| `task_decompose` | Break down complex tasks |
| `web_fetch` | Fetch web content |

## Built-in Skills

Skills are prompt-based instructions that guide the LLM:

- **code_edit** - Safe code modification patterns
- **code_review** - Code quality assessment
- **research** - Web research methodology
- **git_operations** - Git workflow best practices
- **file_management** - File organization patterns

## Project Structure

```
simple_orchestrator/
├── src/orchestrator/
│   ├── core/           # Orchestrator engine
│   ├── llm/            # LLM client (Anthropic/Azure)
│   ├── tools/          # Tool system
│   ├── tasks/          # Task management
│   ├── hooks/          # Hook engine
│   ├── skills/         # Skill registry
│   ├── workspace/      # State persistence
│   └── cli/            # CLI interface
├── tests/              # Unit & integration tests
├── config/             # Configuration files
└── docs/               # Documentation
```

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=orchestrator

# Linting
ruff check src/
black src/
mypy src/
```

## Documentation

- `CLAUDE.md` - Comprehensive developer guide
- `docs/development/` - Detailed documentation
  - `architecture.md` - System design
  - `patterns.md` - How to extend
  - `troubleshooting.md` - Common issues

## Requirements

- Python 3.11+
- Anthropic API key (or Azure Anthropic)

## License

MIT License - see [LICENSE](LICENSE) file.
