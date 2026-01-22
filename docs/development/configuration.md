## Configuration

### Main Configuration

Located at `config/default.yaml`. See complete schema in Architecture Deep Dive section.

Key settings:
- `llm.anthropic.model` - Claude model version
- `tools.bash.blocked_commands` - Safety patterns
- `tasks.max_retries` - Global retry limit
- `logging.level` - Verbosity

### Local Overrides

Create `config/local.yaml` (gitignored) for personal settings:

```yaml
llm:
  anthropic:
    max_tokens: 4096  # Override default
    temperature: 0.5

logging:
  level: DEBUG  # More verbose locally
```

### Environment Variables

Required:
- `ANTHROPIC_API_KEY` - Your Anthropic API key

Optional:
- `ORCHESTRATOR_CONFIG` - Path to custom config file
- `ORCHESTRATOR_LOG_LEVEL` - Override log level
- `ORCHESTRATOR_STATE_DIR` - State directory (default: `.orchestrator/`)

---

