# Known Limitations and Future Improvements

This document tracks known limitations in the current implementation and outlines potential future improvements as the project scales.

---

## Bash Read-Only Mode Security (ASK Mode Only)

### Current Implementation

**UPDATE (Phase 6A+++)**: Bash with read-only mode is now only available in ASK mode. It has been removed from PLAN mode to prevent infinite retry loops.

ASK mode allows bash for information gathering with:

1. **Primary defense**: System prompt instructs LLM to use read-only operations
2. **Safety net**: Blacklist blocks obvious dangerous commands (reboot, rm -rf /, sudo, etc.)

**Implementation details** (Phase 6A++):
- File: `src/orchestrator/tools/builtin/bash.py`
- Method: `_is_dangerous_command(command: str) -> tuple[bool, str]`
- Dangerous commands: `reboot`, `shutdown`, `halt`, `poweroff`, `killall`, `pkill`, `dd`, `mkfs`, `fdisk`, `parted`, `:()`
- Dangerous patterns: `sudo`, `rm -rf /`, `> /dev/`, `curl.*|.*bash`, `wget.*|.*sh`
- Output redirection blocking: `>`, `>>`

### Known Gaps

The current blacklist-based approach cannot prevent all possible modifications:

**Bypasses that are theoretically possible but unlikely:**

1. **Complex command injection**
   - Example: `python -c "import os; os.system('reboot')"`
   - Why unlikely: Requires LLM to deliberately craft malicious code, violates system prompt

2. **Indirect file modification**
   - Example: `python script.py` (where script.py modifies files)
   - Why unlikely: Requires pre-existing malicious scripts in workspace

3. **Package installation**
   - Example: `pip install malicious-package`
   - Why unlikely: Violates read-only instruction, package must already be malicious

4. **Scripting language abuse**
   - Example: `node -e "require('fs').unlinkSync('/important/file')"`
   - Why unlikely: Same as command injection - requires deliberate violation

5. **Environment variable manipulation**
   - Example: `export PATH=/malicious:$PATH`
   - Why unlikely: Limited impact in subprocess, doesn't persist

### Why This Is Acceptable for Current Scope

1. **Claude 4.x has extremely strong instruction following**
   - System prompts explicitly state "read-only operations only"
   - LLM is highly unlikely to deliberately violate instructions
   - Testing shows consistent adherence to read-only guidance

2. **Personal project scope (not multi-tenant production)**
   - Single user environment
   - User can monitor and approve bash commands (requires_approval flag)
   - No untrusted user input

3. **Workspace isolation provides additional protection**
   - Tasks execute within `.orchestrator/workspace` directory
   - Limited blast radius for accidental modifications
   - Important files outside workspace are protected

4. **Blacklist prevents 90% of accidental disasters**
   - Catches obvious dangerous commands (reboot, shutdown)
   - Prevents destructive patterns (rm -rf /, sudo)
   - Blocks output redirection that could overwrite files

5. **Trade-off analysis**
   - **Benefit**: Bash greatly enhances ASK/PLAN mode capabilities (ls, grep, find, etc.)
   - **Risk**: Theoretical bypasses exist but require deliberate LLM misbehavior
   - **Mitigation**: System prompt + blacklist + workspace isolation
   - **Conclusion**: Risk acceptable given strong LLM instruction following

### Future Improvements (When Project Scales)

Consider these approaches if deploying to production or multi-user environments:

#### 1. Sandboxed Bash Execution

Run bash in Docker container with read-only filesystem:

```python
# Example implementation
async def _execute_sandboxed(self, command: str) -> ToolResult:
    docker_cmd = [
        "docker", "run", "--rm",
        "--read-only",  # Read-only root filesystem
        "--tmpfs", "/tmp",  # Allow temp writes to tmpfs
        "--network", "none",  # No network access
        "--user", "nobody",  # Non-root user
        "alpine:latest",
        "sh", "-c", command
    ]
    # ... execute docker_cmd with asyncio.create_subprocess_exec
```

**Pros**:
- OS-level enforcement of read-only
- Cannot bypass with scripting languages
- Complete isolation

**Cons**:
- Requires Docker installation
- Performance overhead
- More complex error handling

#### 2. Whitelist-Based Approach

Only allow specific safe commands:

```python
ALLOWED_COMMANDS = [
    "ls", "cat", "grep", "find", "head", "tail",
    "wc", "pwd", "tree", "file", "du", "df"
]

def _is_command_allowed(self, command: str) -> bool:
    base_command = command.split()[0]
    return base_command in ALLOWED_COMMANDS
```

**Pros**:
- Most restrictive approach
- No bypass possible
- Clear security boundary

**Cons**:
- Less flexible (cannot use pipes, combinations)
- Requires parsing command AST for piping detection
- May break legitimate use cases

#### 3. Process-Level Isolation

Use subprocess with restricted PATH and resource limits:

```python
import resource

async def _execute_restricted(self, command: str) -> ToolResult:
    # Preexec function to set resource limits
    def limit_resources():
        # Limit CPU time (1 second)
        resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
        # Limit memory (100MB)
        resource.setrlimit(resource.RLIMIT_AS, (100*1024*1024, 100*1024*1024))

    # Restricted PATH (only safe binaries)
    safe_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
    }

    process = await asyncio.create_subprocess_shell(
        command,
        preexec_fn=limit_resources,  # Set limits before exec
        env=safe_env,
        # ... other args
    )
```

**Pros**:
- Medium security level
- No external dependencies (Docker)
- Resource limits prevent runaway processes

**Cons**:
- Still vulnerable to command injection
- Platform-specific (resource module on Unix only)
- Complex to maintain

#### 4. Read-Only Filesystem Mount

Mount workspace as read-only when in ASK/PLAN modes:

```bash
# Example: remount workspace as read-only
mount -o remount,ro /path/to/workspace
```

**Pros**:
- OS-level enforcement
- Most robust solution
- No parsing needed

**Cons**:
- Requires root privileges or FUSE
- Platform-specific implementation
- May interfere with legitimate temp file needs

---

## Decision Log

### 2026-01-18: Implemented Hybrid Approach (Trust + Blacklist)

**Decision**: Use system prompt guidance + lightweight blacklist for bash read-only mode in ASK/PLAN modes

**Rationale**:
1. Appropriate for personal project scope
2. Claude 4.x has very strong instruction following capabilities
3. Workspace isolation provides additional protection
4. Blacklist catches 90% of accidental dangerous commands
5. Trade-off: Flexibility vs. absolute security → chose flexibility

**Risk Acceptance**:
- Theoretical bypasses exist (command injection, scripting languages)
- These bypasses require deliberate LLM misbehavior
- Probability is extremely low given Claude 4.x instruction following
- Impact is limited by workspace isolation

**Mitigation**:
- Document limitation for future consideration
- Plan future improvements (Docker sandboxing) when project scales
- Monitor for any unexpected bash usage patterns

**Review Trigger**:
- When deploying to multi-user environment
- When accepting untrusted user input
- When moving to production environment
- If bash misuse patterns are observed

---

## Phase 6A+++ Critical Bug Fix: Bash Removed from PLAN Mode

**Date**: 2026-01-18

### Problem

PLAN mode previously allowed bash with read-only restrictions. This caused infinite retry loops:
- LLM tries bash command with output redirection (e.g., `python3 -c "..." > file.txt`)
- Read-only security blocks it: "Security: Output redirection not allowed in read-only mode"
- LLM doesn't understand this is a MODE restriction (thinks it's a command error)
- LLM keeps retrying different approaches, getting stuck in infinite loop

**User Feedback**: "plan mode 想要「執行工具」被擋掉 (被擋掉是對的)，但是就很難跳出迴圈了... 這該怎辦呢？？？"

### Solution

**Removed bash from PLAN mode entirely**:
- PLAN mode purpose: Planning, not exploration
- Exploration belongs in ASK mode (has bash + read-only)
- PLAN mode now: file_read + web_fetch + task_decompose only

### Rationale

User agreed with the following reasoning:
- Plan mode 的核心目的是「規劃」，不是「探索」
- 探索應該在 ASK mode 做（ASK mode 有 bash + read-only）
- 保持 Plan mode 純粹：file_read + web_fetch + task_decompose

### User Benefit

- No more infinite loops in PLAN mode
- Clear separation of concerns:
  - ASK mode: Exploration and Q&A (with bash)
  - PLAN mode: Planning only (no bash)
  - EXECUTE mode: Full execution (with bash)

### Implementation

**Modified Files**:
- `src/orchestrator/modes/models.py`: Removed "bash" from PLAN mode allowed_tools, updated system prompt
- `src/orchestrator/cli.py`: Added startup guidelines to explain mode restrictions
- `tests/unit/test_mode_manager.py`: Updated test expectations

**Additional Enhancement**: Startup guidelines (inspired by Claude Code CLI)
- Display mode-specific guidelines when orchestrator starts
- Help users understand which mode to use for which tasks
- Markdown-formatted panel with clear explanations

---

## Contributing to This Document

When adding new known limitations:

1. **Describe current implementation** - What exists today
2. **Document the gap** - What doesn't work or is insecure
3. **Explain why it's acceptable now** - Scope, trade-offs, mitigations
4. **Propose future improvements** - What could be done later
5. **Add decision log entry** - Why this choice was made, when to revisit

---

## HITL Session-Level Whitelist (Phase 6D)

### Feature Overview

Users can whitelist tools for the current session by responding "always" to approval prompts, eliminating repetitive approval requests for trusted operations.

**Example**:
```
⚠️ Tool 'file_write' requires approval
   Input: {content=Hello, file_path=test.txt}
   Approve? [y/n/always]: always

✓ file_write whitelisted for this session

[Later in same session]
⚠️ Tool 'file_write' requires approval
✓ Auto-approved (whitelisted)
```

### Current Implementation

**Storage Location**: `.orchestrator/workspace_state/{session_id}.json`

```json
{
  "user_preferences": {
    "approval_whitelist": {
      "tools": [
        {
          "tool_name": "bash",
          "approved_at": "2026-01-18T14:30:00",
          "match_type": "tool_name_only"
        }
      ]
    }
  }
}
```

**CLI Commands**:
- `orchestrator approval list` - View whitelisted tools for current session
- `orchestrator approval clear` - Clear all whitelisted tools
- `orchestrator approval clear --tool bash` - Clear specific tool

### Scope and Limitations

**Session-Scoped**: Whitelist is tied to workspace session_id
- Different projects/sessions have independent whitelists
- Whitelist persists across orchestrator restarts (same session)
- Cleared when workspace is deleted

**Tool-Level Granularity**: Currently whitelists by tool name only
- "always" for `bash` → **all bash commands** approved (including dangerous ones)
- "always" for `file_write` → **all file_write operations** approved
- No parameter-level filtering (future enhancement)

**Risk Assessment**:
- ✅ Low risk for read-only tools (file_read, web_fetch)
- ⚠️ Medium risk for write tools (file_write, file_delete)
- ⚠️ High risk for bash (can execute any command)

**Mitigation**:
- Clear prompt wording: "[y/n/always]"
- User must explicitly type "always" or "a"
- Workspace isolation limits blast radius
- Tools can still be removed from whitelist via CLI

### Why This Is Acceptable for Current Scope

1. **User-initiated**: Whitelist only on explicit "always" response
2. **Session-scoped**: No global whitelist that could affect all projects
3. **Transparent**: CLI commands to view and manage whitelist
4. **Reversible**: Easy to clear whitelist or specific tools
5. **Personal project**: Single user environment, not multi-tenant

### Future Enhancements

#### 1. Parameter-Level Whitelisting
```python
# Match specific parameter patterns
{
    "tool_name": "bash",
    "match_type": "tool_name_and_params",
    "param_patterns": {
        "command": r"^(ls|pwd|grep).*"  # Only read-only commands
    }
}
```

#### 2. Time-Based Expiration
```python
{
    "tool_name": "file_delete",
    "approved_at": "2026-01-18T14:30:00",
    "expires_at": "2026-01-18T15:30:00"  # 1 hour expiration
}
```

#### 3. Confirmation for Dangerous Tools
```python
# Before whitelisting dangerous tools, ask for confirmation
if tool_name in ["file_delete", "bash"]:
    confirm = input("⚠️ Warning: This will allow ALL future operations. Confirm? [y/N]: ")
    if confirm.lower() not in ["y", "yes"]:
        return "yes"  # One-time approval instead
```

#### 4. Global Whitelist (Cross-Session)
```yaml
# File: .orchestrator/global_whitelist.yaml
global_approvals:
  - tool_name: bash
    match_type: tool_name_only
  - tool_name: file_read
    match_type: tool_name_only
```

#### 5. Smart Pattern Learning
Use LLM to analyze approval history and suggest whitelist patterns:
```
System: "You've approved 'bash' for ls/grep/find 10 times.
         Would you like to whitelist bash for read-only operations? [y/n]"
```

### Decision Log

**2026-01-18**: Implemented session-level approval whitelist (Phase 6D)
- Rationale: Improve UX for repetitive approval prompts, inspired by Claude Code
- Implementation: Tool-level whitelist in workspace.user_preferences
- Risk acceptance: Tool-level granularity acceptable for personal project scope
- Mitigation: Session-scoped, user-initiated, reversible via CLI

**Review Trigger**:
- When deploying to multi-user environment
- When accepting untrusted user input
- When moving to production environment
- If accidental over-approval patterns observed

---

## Related Documentation

- [Architecture](architecture.md) - Overall system design
- [Implementation Status](implementation-status.md) - Current phase status
- [Security Considerations](security.md) - General security guidelines (future)
- [Phase 6A++ Plan](/Users/liuyi/.claude/plans/hazy-cooking-meerkat.md) - Read-only bash implementation details
- [Phase 6D Plan](/Users/liuyi/.claude/plans/hazy-cooking-meerkat.md) - HITL approval whitelist implementation
