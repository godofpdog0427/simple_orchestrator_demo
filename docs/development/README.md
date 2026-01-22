# Development Documentation

This directory contains detailed development guides extracted from the main CLAUDE.md file for better organization and reduced context cost.

## Quick Index

### Core Documentation

- **[architecture.md](architecture.md)** - Architecture Deep Dive
  - Component overviews (LLM client, Tool system, Hook engine, etc.)
  - LLM integration with Anthropic API
  - Tool calling flow
  - Hook system lifecycle
  - Task management internals
  - Skill registry design
  - Subagent spawning mechanics

- **[implementation-status.md](implementation-status.md)** - Implementation Status
  - All phase implementation details (Phase 1 through 5B)
  - Checklists for each phase
  - Phase completion status
  - Technical specifications
  - Known limitations

- **[patterns.md](patterns.md)** - Development Patterns
  - How to add a new tool (class-based, decorator-based, YAML-based)
  - Creating SKILL.md files
  - Adding custom hooks
  - Using HITL for approvals
  - Task decomposition examples
  - Spawning subagents

### Reference Guides

- **[troubleshooting.md](troubleshooting.md)** - Troubleshooting Guide
  - Rate limit errors (429) and solutions
  - API key issues
  - Tool execution errors
  - LLM not using tools
  - Import errors
  - Task stuck issues
  - High token usage solutions

- **[testing.md](testing.md)** - Testing Guidelines
  - Unit testing patterns
  - Integration testing with LLM
  - Test writing examples
  - Coverage requirements

- **[git-workflow.md](git-workflow.md)** - Complete Git Workflow
  - Detailed branch strategy
  - Emergency recovery procedures
  - Full workflow examples
  - Creating commits
  - Creating pull requests
  - Common git operations

- **[configuration.md](configuration.md)** - Configuration Reference
  - Complete YAML schema
  - All configuration options
  - Environment variables
  - Hook configuration
  - Tool configuration
  - Subagent settings
  - Workspace settings (Phase 5B)

## Usage

When working on the codebase, consult the relevant guide:

### I want to...

- **Understand the architecture** → Read [`architecture.md`](architecture.md)
- **Check phase status** → Read [`implementation-status.md`](implementation-status.md)
- **Add a new feature** → Read [`patterns.md`](patterns.md)
- **Fix an error** → Read [`troubleshooting.md`](troubleshooting.md)
- **Write tests** → Read [`testing.md`](testing.md)
- **Use git properly** → Read [`git-workflow.md`](git-workflow.md)
- **Configure the orchestrator** → Read [`configuration.md`](configuration.md)

## File Sizes

```
 831 lines - architecture.md
 827 lines - implementation-status.md
 231 lines - patterns.md
 158 lines - troubleshooting.md
  54 lines - testing.md
  91 lines - git-workflow.md
  38 lines - configuration.md
────────
2230 lines total (extracted from original 2,486-line CLAUDE.md)
```

## Navigation

**Main Documentation**: See [`../../CLAUDE.md`](../../CLAUDE.md) for the streamlined entry point (490 lines).

**Project Root**: [`../..`](../..)
