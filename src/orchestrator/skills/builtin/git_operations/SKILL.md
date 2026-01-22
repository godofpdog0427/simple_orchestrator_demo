---
name: git_operations
description: "Git workflow operations including commits, branches, and conflict resolution"
tools_required: [bash, file_read]
version: "1.0.0"
---

# Git Operations

## Overview
Safe and effective Git operations following best practices.

## When to Use
- Creating commits
- Managing branches
- Resolving conflicts
- Reviewing changes

## Common Operations

### Creating Commits

#### Best Practices
- Stage related changes together
- Write clear, descriptive commit messages
- Review changes before committing
- Keep commits atomic (one logical change)

#### Workflow
```bash
# 1. Check status
git status

# 2. Review changes
git diff

# 3. Stage files
git add <files>

# 4. Commit with message
git commit -m "type: brief description

Detailed explanation if needed"
```

#### Commit Message Format
```
type: brief description (50 chars max)

Detailed explanation (72 chars per line):
- What changed
- Why it changed
- Any breaking changes

Fixes #issue-number
```

**Types**: feat, fix, docs, style, refactor, test, chore

### Branch Management

#### Creating Branches
```bash
# Create feature branch
git checkout -b feature/description

# Create fix branch
git checkout -b fix/issue-description
```

#### Branch Naming
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation only
- `test/` - Test additions/changes

### Conflict Resolution

#### Process
1. **Identify conflicts**: `git status`
2. **Understand both sides**: Read conflicted sections
3. **Resolve carefully**: Keep necessary changes from both
4. **Test result**: Ensure functionality works
5. **Mark resolved**: `git add <file>`
6. **Complete merge**: `git commit`

#### Conflict Markers
```
<<<<<<< HEAD
Your changes
=======
Their changes
>>>>>>> branch-name
```

### Reviewing Changes

#### Before Commit
```bash
# See all changes
git diff

# See staged changes
git diff --staged

# See changes for specific file
git diff <file>
```

#### Commit History
```bash
# Recent commits
git log --oneline -10

# Detailed log
git log -p

# Graph view
git log --graph --oneline --all
```

## Safety Checks

### Before Committing
- [ ] Review all staged changes with `git diff --staged`
- [ ] Ensure no sensitive data (API keys, passwords)
- [ ] Check for debug code or console.logs
- [ ] Verify tests pass
- [ ] Check code style/linting

### Before Pushing
- [ ] Review commit messages
- [ ] Ensure commits are logical units
- [ ] Check you're on the correct branch
- [ ] Pull recent changes: `git pull --rebase`
- [ ] Verify tests still pass

### Before Merging
- [ ] Update from main: `git pull origin main`
- [ ] Resolve conflicts if any
- [ ] Run full test suite
- [ ] Code review completed
- [ ] CI/CD checks passing

## Common Mistakes to Avoid

### ❌ Don't
- Commit directly to main/master without PR
- Force push to shared branches
- Commit large binary files
- Mix unrelated changes in one commit
- Write vague commit messages ("fix stuff", "wip")
- Commit commented-out code
- Skip testing before commit

### ✅ Do
- Use feature branches
- Write descriptive commit messages
- Keep commits focused and atomic
- Review changes before staging
- Pull before push
- Use `.gitignore` for generated files
- Communicate before force-pushing

## Useful Commands

```bash
# Undo last commit (keep changes)
git reset --soft HEAD~1

# Discard uncommitted changes
git checkout -- <file>

# Stash changes temporarily
git stash
git stash pop

# Amend last commit
git commit --amend

# Interactive rebase (clean up history)
git rebase -i HEAD~3

# Cherry-pick specific commit
git cherry-pick <commit-hash>
```

## Emergency Procedures

### Accidentally Committed to Wrong Branch
```bash
git reset --soft HEAD~1  # Undo commit, keep changes
git stash                # Save changes
git checkout correct-branch
git stash pop           # Apply changes
git commit              # Commit to correct branch
```

### Need to Split a Commit
```bash
git reset HEAD~1        # Undo commit
git add -p              # Stage hunks interactively
git commit              # Commit first part
git add .               # Stage remaining
git commit              # Commit second part
```
