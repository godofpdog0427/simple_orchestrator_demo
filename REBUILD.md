# 專案重建指南

專案檔案已被 `/clear` 清除。以下是重建步驟：

## 已完成
✅ pyproject.toml, .gitignore, LICENSE, .env.example
✅ 目錄結構
✅ config/default.yaml, config/hooks.yaml, config/schema.json
✅ src/orchestrator/__init__.py

## 需要重建的核心檔案

所有程式碼都在此 Claude Code 對話記錄中。請讓 Claude Code 繼續完成以下檔案：

### 1. CLI & Core
- [ ] src/orchestrator/cli.py
- [ ] src/orchestrator/core/orchestrator.py
- [ ] src/orchestrator/core/__init__.py

### 2. LLM Client
- [ ] src/orchestrator/llm/client.py
- [ ] src/orchestrator/llm/__init__.py

### 3. Tasks
- [ ] src/orchestrator/tasks/models.py
- [ ] src/orchestrator/tasks/manager.py
- [ ] src/orchestrator/tasks/__init__.py

### 4. Tools
- [ ] src/orchestrator/tools/base.py
- [ ] src/orchestrator/tools/registry.py
- [ ] src/orchestrator/tools/builtin/bash.py
- [ ] src/orchestrator/tools/builtin/file_ops.py
- [ ] src/orchestrator/tools/builtin/__init__.py
- [ ] src/orchestrator/tools/__init__.py

### 5. Hooks
- [ ] src/orchestrator/hooks/base.py
- [ ] src/orchestrator/hooks/__init__.py

### 6. Skills (5個 SKILL.md)
- [ ] src/orchestrator/skills/builtin/code_edit/SKILL.md
- [ ] src/orchestrator/skills/builtin/code_review/SKILL.md
- [ ] src/orchestrator/skills/builtin/research/SKILL.md
- [ ] src/orchestrator/skills/builtin/git_operations/SKILL.md
- [ ] src/orchestrator/skills/builtin/file_management/SKILL.md

### 7. 文檔
- [ ] CLAUDE.md
- [ ] README.md

### 8. 其他 __init__.py
- [ ] src/orchestrator/subagents/__init__.py
- [ ] src/orchestrator/skills/__init__.py
- [ ] src/orchestrator/hooks/builtin/__init__.py
- [ ] src/orchestrator/llm/providers/__init__.py

## 快速恢復指令

請要求 Claude Code：「請繼續完成 REBUILD.md 中列出的所有檔案，所有程式碼都在此對話記錄中，請逐一用 Write 工具建立」
